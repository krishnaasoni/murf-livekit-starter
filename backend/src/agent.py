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
import scheme_data
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

    @function_tool
    async def check_scheme_eligibility(
        self,
        context: RunContext,
        scheme_name: str,
        age: int | None = None,
        annual_income: float | None = None,
        occupation: str = "",
        category: str = "",
        requested_loan_amount: float | None = None,
    ) -> str:
        """Check caller eligibility and retrieve the official document checklist for Indian financial schemes.

        Use this tool WHENEVER the user asks if they qualify for a loan or financial scheme, asks what documents
        are needed for a scheme, or inquires about government schemes (such as PM Mudra Loan, PM Kisan, PM SVANidhi, Stand-Up India, Atal Pension Yojana).

        Args:
            scheme_name: Name or type of financial scheme (e.g. 'PM Mudra', 'PM Kisan', 'PM SVANidhi', 'Stand-Up India', 'Atal Pension').
            age: Caller's age in years (optional).
            annual_income: Caller's annual income in INR (optional).
            occupation: Caller's profession/business (e.g. 'shopkeeper', 'farmer', 'vendor', 'artisan').
            category: Caller's category or gender if relevant (e.g. 'woman', 'SC/ST', 'general').
            requested_loan_amount: Requested loan amount in INR (optional).
        """
        logger.info(
            f"Checking scheme eligibility for: scheme='{scheme_name}', age={age}, income={annual_income}"
        )
        try:
            res = await scheme_data.evaluate_scheme_eligibility(
                scheme_name=scheme_name,
                age=age,
                annual_income=annual_income,
                occupation=occupation,
                category=category,
                requested_loan_amount=requested_loan_amount,
            )
        except Exception as err:
            logger.error(f"Error accessing scheme eligibility data: {err}")
            # Step 4: Handle failure path out loud
            return (
                f"SYSTEM TIMEOUT / API ERROR: I could not reach the official scheme server right now "
                f"due to a network connection issue ({err}). Please tell the user out loud: "
                f"'I'm sorry, I couldn't fetch real-time scheme details because the server timed out. "
                f"Please try again in a few moments.'"
            )

        # Step 5: Say when the data is from
        data_as_of = res.get("data_as_of", "August 2026")
        if res.get("status") == "UNKNOWN_SCHEME":
            return f"[Data as of {data_as_of}]: {res['message']}"

        docs_list = "\n".join([f"- {d}" for d in res.get("documents", [])])
        reasons_list = " None" if not res.get("reasons") else "; ".join(res["reasons"])
        tier = f" ({res['tier_info']})" if res.get("tier_info") else ""

        return (
            f"[Official Policy Data as of: {data_as_of}]\n"
            f"Scheme: {res['scheme_name']}{tier}\n"
            f"Eligibility Status: {res['status']}\n"
            f"Benefit: {res.get('benefit', '')}\n"
            f"Notes/Restrictions: {reasons_list}\n"
            f"Required Document Checklist:\n{docs_list}\n"
            f"INSTRUCTION TO AGENT: State clearly to the caller that the data is as of {data_as_of}, "
            f"inform them of their eligibility status, and read out the required document checklist."
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
