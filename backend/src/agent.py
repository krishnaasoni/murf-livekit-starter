import logging
import os
import sys

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Ensure src module directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import db
from prompt import SYSTEM_PROMPT

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    @function_tool
    async def lookup_caller(self, context: RunContext, search_term: str) -> str:
        """Look up a caller's saved history and facts from the SQLite database by name or user_id.

        Args:
            search_term: Name or user_id of the caller to look up (e.g. 'Ramesh').
        """
        logger.info(f"Looking up caller profile for: '{search_term}'")
        profile = db.lookup_caller(search_term)
        if not profile:
            return f"No caller record found for '{search_term}'."

        return (
            f"Found caller record for '{profile['name']}' (ID: {profile['user_id']}): "
            f"Language='{profile['language_preference']}', "
            f"Last Topic='{profile['last_topic']}', "
            f"Facts={profile['facts']}, "
            f"Last Interaction='{profile['last_interaction']}'"
        )

    @function_tool
    async def save_caller_info(
        self,
        context: RunContext,
        name: str,
        user_consent: bool,
        last_topic: str = "",
        language_preference: str = "Hindi-English",
        schemes_checked: str = "",
        eligibility_status: str = "",
        user_id: str = "",
    ) -> str:
        """Save or update caller information in the SQLite database ONLY if user_consent is True.

        HARD RULE: If user_consent is False, caller data will NOT be saved.

        Args:
            name: Caller's name.
            user_consent: Set to True ONLY if caller explicitly granted permission to save info.
            last_topic: Primary topic or scheme discussed (e.g. 'PM Mudra Loan').
            language_preference: Preferred language register (e.g. 'Hindi-English').
            schemes_checked: Financial schemes inquired about.
            eligibility_status: General eligibility advice provided.
            user_id: Optional caller ID.
        """
        if not user_consent:
            logger.warning(
                f"Save caller info blocked for '{name}': User declined consent."
            )
            return "Consent declined by user. Information was NOT saved into database."

        facts = {}
        if schemes_checked:
            facts["schemes_checked"] = schemes_checked
        if eligibility_status:
            facts["eligibility_status"] = eligibility_status

        profile = db.save_caller(
            user_id=user_id or name,
            name=name,
            language_preference=language_preference,
            facts=facts,
            last_topic=last_topic,
        )

        return (
            f"Successfully saved profile for {profile['name']}. "
            f"Last Topic: '{last_topic}', Saved Facts: {profile['facts']}."
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    db.init_db()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Ensure SQLite DB is initialized
    db.init_db()

    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),
        tts=murf.TTS(
            voice="hi-IN-anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
