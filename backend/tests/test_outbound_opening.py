import pytest
from livekit.agents import AgentSession, inference, llm

from agent import Assistant


def _llm() -> llm.LLM:
    return inference.LLM(model="openai/gpt-4.1-mini")


@pytest.mark.asyncio
async def test_outbound_opening_compliance() -> None:
    """Evaluation of outbound call opening compliance (Who is calling, Why, and How to stop calls in first two sentences)."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        # Simulate user picking up the call and saying hello
        result = await session.run(user_input="Hello, who is this?")

        # Evaluate opening response for mandatory compliance criteria
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                The response must state:
                1. Who is calling (MoneyMitra Financial Assistance / Assistant) and Why (scheme submission deadline / pre-approved PM Mudra loan deadline).
                2. Explicit instructions on how to stop future calls (e.g. 'say stop', 'opt out', or stop calls instruction).

                The statement should open clearly in the first two sentences explaining identity, call purpose, and the stop/opt-out option.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_outbound_opt_out_handling() -> None:
    """Evaluation of agent handling user opt-out / stop request during outbound call."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        # User requests to stop calls
        result = await session.run(user_input="Stop calling me. Remove my number.")

        await (
            result.expect.next_event()
            .is_function_call(name="opt_out_caller")
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                The agent acknowledges the user's opt-out request, calls the opt_out_caller tool, and confirms out loud that the user has been removed from future outbound call lists.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_outbound_scheme_deadline_help() -> None:
    """Evaluation of agent providing document checklist for pre-approved scheme deadline."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        # User asks what documents are needed before the deadline
        result = await session.run(
            user_input="What documents do I need to submit for PM Mudra Loan before the deadline?"
        )

        await (
            result.expect.next_event()
            .is_function_call(name="check_scheme_eligibility")
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                The agent calls check_scheme_eligibility for PM Mudra Loan, states when the policy data is from, and provides the required document checklist clearly out loud.
                """,
            )
        )

        result.expect.no_more_events()
