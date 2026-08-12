import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import db
from agent import Assistant


@pytest.mark.asyncio
async def test_create_escalation_record_db(tmp_path):
    """Test creating and retrieving human escalation record in SQLite DB."""
    test_db = str(tmp_path / "test_escalation.db")
    db.init_db(db_path=test_db)

    res = db.create_escalation_record(
        caller_name="Ramesh Kumar",
        reason_category="Fraud/Security Incident",
        what_happened="Reported suspicious debit of Rs 15,000 on card.",
        what_agent_checked="Checked caller profile and recent transaction status.",
        user_consent=True,
        urgency="HIGH",
        language="Hindi-English",
        preferred_followup="Phone Call",
        user_id="ramesh_101",
        db_path=test_db,
    )

    assert res["success"] is True
    assert res["caller_name"] == "Ramesh Kumar"
    assert res["urgency"] == "HIGH"
    assert res["status"] == "OPEN"

    records = db.get_escalations(db_path=test_db)
    assert len(records) == 1
    assert records[0]["caller_name"] == "Ramesh Kumar"
    assert records[0]["reason_category"] == "Fraud/Security Incident"

    # Test resolving escalation
    resolved = db.resolve_escalation(res["id"], db_path=test_db)
    assert resolved is True
    open_records = db.get_escalations(status="OPEN", db_path=test_db)
    assert len(open_records) == 0


@pytest.mark.asyncio
async def test_escalation_consent_enforcement(tmp_path):
    """Test that escalation request is REJECTED when user_consent is False."""
    test_db = str(tmp_path / "test_consent.db")
    db.init_db(db_path=test_db)

    res = db.create_escalation_record(
        caller_name="Sunita Devi",
        reason_category="Decision Beyond AI Scope",
        what_happened="Requested late fee waiver.",
        what_agent_checked="Verified account standing.",
        user_consent=False,  # User declined permission
        urgency="NORMAL",
        db_path=test_db,
    )

    assert res["success"] is False
    assert "User consent denied" in res["error"]

    # Verify database has zero records
    records = db.get_escalations(db_path=test_db)
    assert len(records) == 0


@pytest.mark.asyncio
async def test_escalation_privacy_sanitization(tmp_path):
    """Test that sensitive identifiers (PIN, OTP, account numbers) are scrubbed from text."""
    test_db = str(tmp_path / "test_privacy.db")
    db.init_db(db_path=test_db)

    res = db.create_escalation_record(
        caller_name="Amit Shah",
        reason_category="Fraud/Security Incident",
        what_happened="Caller said PIN is 4321 and OTP: 987654 was sent.",
        what_agent_checked="Verified account number 123456789012.",
        user_consent=True,
        urgency="HIGH",
        db_path=test_db,
    )

    assert res["success"] is True
    # Verify PIN and OTP were redacted
    assert "4321" not in res["what_happened"]
    assert "987654" not in res["what_happened"]
    assert "[REDACTED]" in res["what_happened"]
    # Verify account number was redacted
    assert "123456789012" not in res["what_agent_checked"]
    assert "[REDACTED]" in res["what_agent_checked"]


@pytest.mark.asyncio
async def test_assistant_create_escalation_tool():
    """Test invoking the Assistant.create_escalation function tool."""
    assistant = Assistant()
    tool_output = await assistant.create_escalation(
        context=None,
        caller_name="Pooja Sharma",
        reason_category="Decision Beyond AI Scope",
        what_happened="Requested 1.5% interest rate discount on PM Mudra loan.",
        what_agent_checked="Checked PM Mudra eligibility (Approved). Requires underwriter approval.",
        user_consent=True,
        urgency="NORMAL",
        language="Hindi",
        preferred_followup="SMS",
        user_id="pooja_303",
    )

    assert "Successfully created Human Escalation Request Ticket" in tool_output
    assert "Pooja Sharma" in tool_output
    assert "Follow-up: 'SMS'" in tool_output

    # Test consent declined path
    declined_output = await assistant.create_escalation(
        context=None,
        caller_name="Pooja Sharma",
        reason_category="Fraud/Security Incident",
        what_happened="Suspicious activity",
        what_agent_checked="Checked logs",
        user_consent=False,
    )
    assert "Escalation cancelled: Caller did not give consent" in declined_output
