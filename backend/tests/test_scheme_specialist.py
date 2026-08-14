import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
from agent import Assistant
from scheme_specialist import SchemeSpecialist


class MockSession:
    def __init__(self):
        self.said_messages = []

    async def say(self, message: str):
        self.said_messages.append(message)

    async def generate_reply(self, **kwargs):
        pass


class MockContext:
    def __init__(self):
        self.session = MockSession()


@pytest.mark.asyncio
async def test_assistant_transfer_to_scheme_specialist():
    """Test Assistant transferring to SchemeSpecialist via tool call."""
    shared_state = {"objective_achieved": False}
    assistant = Assistant(shared_state=shared_state)
    ctx = MockContext()

    specialist = await assistant.transfer_to_scheme_specialist(context=ctx)

    assert isinstance(specialist, SchemeSpecialist)
    assert specialist.shared_state is shared_state
    assert len(ctx.session.said_messages) == 1
    assert "scheme specialist" in ctx.session.said_messages[0].lower()


class MockActivity:
    def __init__(self):
        self.session = MockSession()


@pytest.mark.asyncio
async def test_scheme_specialist_on_enter():
    """Test SchemeSpecialist on_enter seamlessly calls generate_reply without extra spoken intro."""
    shared_state = {"objective_achieved": False}
    specialist = SchemeSpecialist(shared_state=shared_state)
    mock_activity = MockActivity()
    object.__setattr__(specialist, "_activity", mock_activity)

    await specialist.on_enter()

    # Expect no extra spoken intro line to preserve seamless conversation flow
    assert len(mock_activity.session.said_messages) == 0


@pytest.mark.asyncio
async def test_scheme_specialist_eligibility_achieves_objective():
    """Test that valid scheme evaluation in SchemeSpecialist sets shared_state objective_achieved to True."""
    shared_state = {"objective_achieved": False}
    specialist = SchemeSpecialist(shared_state=shared_state)

    res = await specialist.check_scheme_eligibility(
        context=None,
        scheme_name="PM Mudra",
        requested_loan_amount=50000,
    )

    assert "Official Policy Data" in res
    assert shared_state["objective_achieved"] is True
