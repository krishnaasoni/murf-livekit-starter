import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import db
from agent import Assistant


@pytest.mark.asyncio
async def test_opt_out_caller_db(tmp_path):
    """Test opt-out caller persistence in SQLite database."""
    test_db = str(tmp_path / "test_caller.db")
    db.init_db(db_path=test_db)

    res = db.opt_out_caller(
        user_id="Ramesh", reason="User requested stop", db_path=test_db
    )
    assert res["name"] == "Ramesh"
    assert res["facts"]["opted_out"] is True
    assert res["facts"]["opt_out_reason"] == "User requested stop"

    profile = db.lookup_caller("Ramesh", db_path=test_db)
    assert profile is not None
    assert profile["facts"]["opted_out"] is True


@pytest.mark.asyncio
async def test_opt_out_function_tool():
    """Test calling Assistant.opt_out_caller tool."""
    assistant = Assistant()
    tool_output = await assistant.opt_out_caller(
        context=None,
        user_id="Ramesh",
        reason="Does not want outbound calls",
    )

    assert "Successfully registered opt-out preference" in tool_output
    assert "opted_out=True" in tool_output
