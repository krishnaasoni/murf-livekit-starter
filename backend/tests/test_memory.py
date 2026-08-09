import os
import sys
import tempfile

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import db


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_caller_memory.db")
        db.init_db(db_path=db_path)
        yield db_path


def test_init_and_save_caller(temp_db):
    """Test saving caller info and looking up caller record."""
    saved = db.save_caller(
        user_id="user_123",
        name="Ramesh",
        language_preference="Hindi-English",
        facts={"schemes_checked": "PM Mudra Loan", "eligibility": "Eligible"},
        last_topic="PM Mudra Loan eligibility",
        db_path=temp_db,
    )

    assert saved["name"] == "Ramesh"
    assert saved["user_id"] == "user_123"
    assert saved["facts"]["schemes_checked"] == "PM Mudra Loan"

    # Lookup test
    found = db.lookup_caller("Ramesh", db_path=temp_db)
    assert found is not None
    assert found["name"] == "Ramesh"
    assert found["last_topic"] == "PM Mudra Loan eligibility"


def test_financial_privacy_sanitization(temp_db):
    """Test that sensitive financial identity keys (account number, OTP, PIN) are sanitized out."""
    sensitive_facts = {
        "schemes_checked": "PM Kisan",
        "account_number": "1234567890",
        "otp": "998877",
        "pin": "1234",
        "pan_number": "ABCDE1234F",
        "aadhaar": "999988887777",
    }

    saved = db.save_caller(
        user_id="user_456",
        name="Suresh",
        facts=sensitive_facts,
        db_path=temp_db,
    )

    # Sensitive keys should be stripped
    assert "account_number" not in saved["facts"]
    assert "otp" not in saved["facts"]
    assert "pin" not in saved["facts"]
    assert "pan_number" not in saved["facts"]
    assert "aadhaar" not in saved["facts"]
    # Non-sensitive facts preserved
    assert saved["facts"]["schemes_checked"] == "PM Kisan"


def test_lookup_nonexistent_caller(temp_db):
    """Test looking up a caller that does not exist in DB."""
    found = db.lookup_caller("UnknownPerson", db_path=temp_db)
    assert found is None
