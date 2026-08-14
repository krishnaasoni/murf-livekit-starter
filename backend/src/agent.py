import json
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
from scheme_specialist import SchemeSpecialist

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self, shared_state: dict | None = None) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.shared_state = (
            shared_state if shared_state is not None else {"objective_achieved": False}
        )

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
    async def transfer_to_scheme_specialist(
        self, context: RunContext, user_query: str = ""
    ) -> Agent:
        """Use this when the user needs detailed help with a government scheme's
        eligibility, benefits, or required documents.

        Args:
            user_query: The caller's question or specific scheme requested (e.g. 'PM Mudra Loan documents checklist').
        """
        await context.session.say(
            "Main aapko hamare scheme specialist Samer se connect kar rahi hoon."
        )
        session_tts = getattr(context.session, "tts", None)
        http_sess = getattr(session_tts, "_session", None) if session_tts else None

        specialist_tts = murf.TTS(
            voice="hi-IN-samer",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
            http_session=http_sess,
        )
        return SchemeSpecialist(
            shared_state=self.shared_state,
            initial_query=user_query,
            tts_instance=specialist_tts,
        )

    @function_tool
    async def opt_out_caller(
        self,
        context: RunContext,
        user_id: str = "",
        reason: str = "User requested stop",
    ) -> str:
        """Record caller opt-out preference so they are removed from future outbound calls.

        Call this tool IMMEDIATELY when the caller says 'stop', 'opt out', 'don't call me', 'remove my number', or similar request.

        Args:
            user_id: Caller's name or user_id (optional).
            reason: Reason given for opting out.
        """
        logger.info(f"Processing opt-out for caller '{user_id}': reason='{reason}'")
        res = db.opt_out_caller(user_id=user_id or "current_caller", reason=reason)
        return (
            f"Successfully registered opt-out preference for {res['name']}. "
            f"Fact recorded: opted_out=True. Inform caller politely that they have been removed from future calls."
        )

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        caller_name: str,
        reason_category: str,
        what_happened: str,
        what_agent_checked: str,
        user_consent: bool,
        urgency: str = "HIGH",
        language: str = "Hindi-English",
        preferred_followup: str = "Phone Call",
        user_id: str = "",
    ) -> str:
        """Create a human help / escalation request when caller reports fraud or requires human decision making.

        CRITICAL CONSENT RULE: You MUST ask the caller for explicit permission before calling this tool.
        If user_consent is False, the request will NOT be saved.

        DO NOT include passwords, OTPs, PINs, or account numbers in what_happened or what_agent_checked.

        Args:
            caller_name: Name of the caller needing help.
            reason_category: Category e.g. 'Fraud/Security Incident' or 'Decision Beyond AI Scope'.
            what_happened: Short summary of the incident or request (no PINs/OTPs/account numbers).
            what_agent_checked: Details already verified by agent (scheme status, transaction check, etc.).
            user_consent: Set to True ONLY if caller explicitly granted permission to create request.
            urgency: Priority level ('HIGH' for fraud, 'NORMAL' for decision).
            language: Preferred language of caller (e.g. 'Hindi-English', 'Hindi').
            preferred_followup: Preferred contact method (e.g. 'Phone Call', 'SMS', 'Email').
            user_id: Caller ID or identifier (optional).
        """
        logger.info(
            f"Human escalation request initiated for '{caller_name}': "
            f"category='{reason_category}', consent={user_consent}, urgency='{urgency}'"
        )
        if not user_consent:
            return (
                "Escalation cancelled: Caller did not give consent to share details with human support. "
                "Politely inform the caller that no escalation request was created."
            )

        res = db.create_escalation_record(
            caller_name=caller_name,
            reason_category=reason_category,
            what_happened=what_happened,
            what_agent_checked=what_agent_checked,
            user_consent=user_consent,
            urgency=urgency,
            language=language,
            preferred_followup=preferred_followup,
            user_id=user_id or caller_name,
        )

        if not res.get("success"):
            return f"Failed to create human escalation request: {res.get('error')}"

        # Mark objective as achieved upon successful escalation ticket creation
        self.shared_state["objective_achieved"] = True

        return (
            f"Successfully created Human Escalation Request Ticket {res['ticket_code']} (#{res['id']}) for {res['caller_name']}. "
            f"Category: '{res['reason_category']}', Urgency: '{res['urgency']}', Follow-up: '{res['preferred_followup']}'. "
            f"INSTRUCTION TO AGENT: Inform the caller that their request has been registered and a human specialist "
            f"will contact them via {res['preferred_followup']}."
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

    shared_state = {"objective_achieved": False}
    assistant = Assistant(shared_state=shared_state)

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
        agent=assistant,
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

    caller_name = os.getenv("OUTBOUND_CALLER_NAME", "Krishna")
    if ctx.room.metadata:
        try:
            meta = json.loads(ctx.room.metadata)
            if "target_name" in meta:
                caller_name = meta["target_name"]
        except Exception:
            pass

    # Record analytics outcome when room disconnects
    recorded_analytics = False

    def _on_disconnected(reason=None):
        nonlocal recorded_analytics
        if not recorded_analytics:
            recorded_analytics = True
            outcome = (
                "SUCCESS" if shared_state["objective_achieved"] else "FAILED"
            )
            db.record_call_analytics(caller_id=caller_name, outcome=outcome)

    ctx.room.on("disconnected", _on_disconnected)

    # Determine connection channel (SIP Outbound Call vs Browser WebRTC)
    is_sip = any(
        p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        for p in ctx.room.remote_participants.values()
    ) or ctx.room.name.startswith("outbound-")

    profile = db.lookup_caller(caller_name)

    if is_sip:
        # Outbound SIP call compliance opening (exact 2 sentences)
        await session.say(
            f"Namaste {caller_name} ji, main MoneyMitra Financial Assistance se bol rahi hoon — "
            "aapki pre-approved PM Mudra Loan subsidy ki submission deadline 15 August 2026 ko khatam ho rahi hai. "
            "Agar aap aage se aisi reminder calls nahi chahte, toh aap abhi 'stop' bolein ya keh dein ki mujhe calls mat karo."
        )
    elif profile:
        # Returning user browser greeting
        await session.say(
            f"Namaste {profile['name']} ji! Main MoneyMitra Voice Agent hoon. "
            "MoneyMitra mein aapka swagat hai, aaj main aapki kya sahayata kar sakti hoon?"
        )
    else:
        # New user browser greeting
        await session.say(
            "Namaste! Main MoneyMitra Voice Agent hoon. "
            "Kya main aapka shubh naam jaan sakti hoon taaki main aapki sahayata kar sakoon?"
        )


if __name__ == "__main__":
    cli.run_app(server)
