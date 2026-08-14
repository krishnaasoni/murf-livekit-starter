import logging

from livekit.agents import Agent, RunContext, function_tool, tts

import scheme_data

logger = logging.getLogger("scheme_specialist")

SPECIALIST_PROMPT = """
IDENTITY:
You are "Samer" (Sam), the male "Government Scheme Specialist" for MoneyMitra.

CORE PURPOSE & SCOPE:
Your SINGLE and ONLY responsibility is to assist callers with government financial scheme eligibility, scheme benefits, and official required document checklists for:
- PM Mudra Loan (Pradhan Mantri Mudra Yojana)
- PM Kisan (Pradhan Mantri Kisan Samman Nidhi)
- PM SVANidhi (PM Street Vendor's AtmaNirbhar Nidhi)
- Stand-Up India
- Atal Pension Yojana (APY)

BOUNDARIES & STRICT RULES:
1. Do NOT handle general budgeting advice, savings tips, EMI calculations, opt-out requests, or human escalation requests.
2. If the user asks about anything outside government scheme eligibility, benefits, or documents (e.g. general budgeting, opt-out, human help), state clearly that you will connect them back to the main MoneyMitra assistant for help with that request.
3. Use the `check_scheme_eligibility` tool whenever evaluating eligibility or fetching document checklists.
4. Always mention that details are based on official policy as of August 2026.
5. Keep your tone polite, professional, clear, and encouraging. Mirror the caller's language (Hindi, English, or Hindi-English).
"""


class SchemeSpecialist(Agent):
    def __init__(
        self,
        shared_state: dict,
        initial_query: str = "",
        tts_instance: tts.TTS | None = None,
    ) -> None:
        self.shared_state = shared_state
        self.initial_query = initial_query
        kwargs = {"instructions": SPECIALIST_PROMPT}
        if tts_instance is not None:
            kwargs["tts"] = tts_instance
        super().__init__(**kwargs)

    async def on_enter(self) -> None:
        """Called automatically when handoff occurs and the specialist takes over."""
        await self.session.generate_reply()

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
            f"[SchemeSpecialist] Checking eligibility: scheme='{scheme_name}', age={age}, income={annual_income}"
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
            logger.error(
                f"[SchemeSpecialist] Error accessing scheme eligibility data: {err}"
            )
            return (
                f"SYSTEM TIMEOUT / API ERROR: I could not reach the official scheme server right now "
                f"due to a network connection issue ({err}). Please tell the user out loud: "
                f"'I'm sorry, I couldn't fetch real-time scheme details because the server timed out. "
                f"Please try again in a few moments.'"
            )

        data_as_of = res.get("data_as_of", "August 2026")
        if res.get("status") == "UNKNOWN_SCHEME":
            return f"[Data as of {data_as_of}]: {res['message']}"

        # Mark objective as successfully achieved upon valid eligibility/checklist output
        self.shared_state["objective_achieved"] = True

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
