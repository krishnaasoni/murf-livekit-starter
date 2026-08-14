import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import scheme_data
from scheme_specialist import SchemeSpecialist


@pytest.mark.asyncio
async def test_evaluate_scheme_eligibility_mudra():
    """Test evaluation of PM Mudra scheme with age, loan amount, and doc checklist."""
    res = await scheme_data.evaluate_scheme_eligibility(
        scheme_name="PM Mudra",
        age=28,
        occupation="shopkeeper",
        requested_loan_amount=200000,
    )

    assert res["status"] == "ELIGIBLE"
    assert "PMMY" in res["scheme_name"] or "MUDRA" in res["scheme_name"]
    assert "Kishore" in res["tier_info"]
    assert res["data_as_of"] == "10 August 2026 (Official Policy Circular)"
    assert len(res["documents"]) >= 3
    assert any("Identity Proof" in doc for doc in res["documents"])


@pytest.mark.asyncio
async def test_evaluate_scheme_eligibility_ineligible_age():
    """Test scheme evaluation when applicant age is outside limits (e.g., APY max age 40)."""
    res = await scheme_data.evaluate_scheme_eligibility(
        scheme_name="Atal Pension Yojana",
        age=45,
    )

    assert res["status"] == "PARTIALLY_ELIGIBLE_OR_INELIGIBLE"
    assert len(res["reasons"]) > 0
    assert any("Maximum age limit" in reason for reason in res["reasons"])


@pytest.mark.asyncio
async def test_evaluate_unknown_scheme():
    """Test handling of unknown scheme query."""
    res = await scheme_data.evaluate_scheme_eligibility(
        scheme_name="Unknown Mega Scheme",
    )

    assert res["status"] == "UNKNOWN_SCHEME"
    assert "not found" in res["message"].lower()


@pytest.mark.asyncio
async def test_agent_tool_success():
    """Test calling SchemeSpecialist.check_scheme_eligibility function tool."""
    shared_state = {"objective_achieved": False}
    specialist = SchemeSpecialist(shared_state=shared_state)
    tool_output = await specialist.check_scheme_eligibility(
        context=None,
        scheme_name="PM Kisan",
        occupation="farmer",
        annual_income=250000,
    )

    # Step 5 check: data timestamp is included
    assert "Official Policy Data as of:" in tool_output
    assert "10 August 2026" in tool_output
    assert "Required Document Checklist:" in tool_output
    assert "Aadhaar Card" in tool_output
    assert shared_state["objective_achieved"] is True


@pytest.mark.asyncio
async def test_agent_tool_failure_path_out_loud(monkeypatch):
    """Step 4 test: Verify failure path out loud when network/API times out."""

    async def mock_timeout(*args, **kwargs):
        raise TimeoutError("Government Scheme Portal server connection timed out.")

    monkeypatch.setattr(scheme_data, "evaluate_scheme_eligibility", mock_timeout)

    shared_state = {"objective_achieved": False}
    specialist = SchemeSpecialist(shared_state=shared_state)
    tool_output = await specialist.check_scheme_eligibility(
        context=None,
        scheme_name="PM Mudra",
    )

    # Must contain clear out-loud instructions for the spoken agent response
    assert "SYSTEM TIMEOUT / API ERROR" in tool_output
    assert "out loud" in tool_output.lower()
    assert "server timed out" in tool_output.lower()
