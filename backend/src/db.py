import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger("agent.db")

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_DB_PATH = os.path.join(DB_DIR, "caller_memory.db")

# Sensitive key terms that MUST NOT be stored (Financial Privacy Guardrails)
FORBIDDEN_FACT_KEYS = {
    "account",
    "account_number",
    "otp",
    "pin",
    "pan",
    "aadhaar",
    "adhar",
    "card",
    "cvv",
    "password",
    "ssn",
}


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Ensure parent directory exists and return a SQLite connection."""
    abs_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    conn = sqlite3.connect(abs_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database schema."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS caller_profiles (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    language_preference TEXT DEFAULT 'Hindi-English',
                    facts TEXT DEFAULT '{}',
                    last_topic TEXT DEFAULT '',
                    last_interaction TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS human_escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    caller_name TEXT NOT NULL,
                    reason_category TEXT NOT NULL,
                    what_happened TEXT NOT NULL,
                    what_agent_checked TEXT DEFAULT '',
                    urgency TEXT DEFAULT 'NORMAL',
                    language TEXT DEFAULT 'Hindi-English',
                    preferred_followup TEXT DEFAULT 'Phone Call',
                    status TEXT DEFAULT 'OPEN',
                    created_at TEXT NOT NULL
                );
                """
            )
        logger.info("SQLite database initialized successfully.")
    finally:
        conn.close()


def sanitize_facts(facts: dict) -> dict:
    """Remove any sensitive financial identifiers from facts dictionary."""
    if not isinstance(facts, dict):
        return {}

    sanitized = {}
    for key, value in facts.items():
        key_lower = str(key).lower().strip()
        # Skip forbidden financial identity keys
        if any(forbidden in key_lower for forbidden in FORBIDDEN_FACT_KEYS):
            logger.warning(f"Sanitized and ignored forbidden sensitive key: {key}")
            continue
        sanitized[key] = value

    return sanitized


def sanitize_text(text: str) -> str:
    """Redact passwords, OTPs, PINs, card numbers, and account numbers from summary text."""
    if not text:
        return ""
    import re

    pattern = r"(?i)\b(pin|otp|cvv|password|passcode|account|card|aadhaar|adhar|pan)\b(?:\s*(?:is|was|number|no|#|code|=|:))*\s*([a-zA-Z0-9_-]{3,20})"

    def _replace(match):
        keyword = match.group(1)
        return f"{keyword}: [REDACTED]"

    return re.sub(pattern, _replace, text)


def lookup_caller(search_term: str, db_path: str = DEFAULT_DB_PATH) -> dict | None:
    """Look up a caller profile by user_id or name (case-insensitive)."""
    init_db(db_path)
    if not search_term or not search_term.strip():
        return None

    term = search_term.strip()
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, name, language_preference, facts, last_topic, last_interaction
            FROM caller_profiles
            WHERE LOWER(user_id) = LOWER(?) OR LOWER(name) = LOWER(?)
            LIMIT 1;
            """,
            (term, term),
        )
        row = cursor.fetchone()
        if not row:
            return None

        facts_dict = {}
        if row["facts"]:
            try:
                facts_dict = json.loads(row["facts"])
            except json.JSONDecodeError:
                facts_dict = {}

        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "language_preference": row["language_preference"],
            "facts": facts_dict,
            "last_topic": row["last_topic"],
            "last_interaction": row["last_interaction"],
        }
    finally:
        conn.close()


def save_caller(
    user_id: str,
    name: str,
    language_preference: str = "Hindi-English",
    facts: dict | None = None,
    last_topic: str = "",
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """Save or update a caller profile in SQLite.

    Sanitizes facts to remove sensitive identifiers before saving.
    """
    init_db(db_path)
    clean_user_id = (user_id or name or "user_101").strip().lower()
    clean_name = (name or "Caller").strip()
    clean_facts = sanitize_facts(facts or {})
    timestamp = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO caller_profiles (
                    user_id, name, language_preference, facts, last_topic, last_interaction
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    clean_user_id,
                    clean_name,
                    language_preference,
                    json.dumps(clean_facts),
                    last_topic,
                    timestamp,
                ),
            )
        logger.info(f"Saved profile for caller '{clean_name}' (ID: {clean_user_id}).")
        return {
            "user_id": clean_user_id,
            "name": clean_name,
            "language_preference": language_preference,
            "facts": clean_facts,
            "last_topic": last_topic,
            "last_interaction": timestamp,
        }
    finally:
        conn.close()


def opt_out_caller(
    user_id: str, reason: str = "User requested stop", db_path: str = DEFAULT_DB_PATH
) -> dict:
    """Record caller opt-out preference so they are removed from future outbound calls."""
    init_db(db_path)
    existing = lookup_caller(user_id, db_path=db_path) or {}
    facts = existing.get("facts", {})
    facts["opted_out"] = True
    facts["opt_out_reason"] = reason
    facts["opt_out_timestamp"] = datetime.now(timezone.utc).isoformat()
    return save_caller(
        user_id=user_id,
        name=existing.get("name", user_id),
        language_preference=existing.get("language_preference", "Hindi-English"),
        facts=facts,
        last_topic="Opt-Out Request",
        db_path=db_path,
    )


def create_escalation_record(
    caller_name: str,
    reason_category: str,
    what_happened: str,
    what_agent_checked: str,
    user_consent: bool,
    urgency: str = "HIGH",
    language: str = "Hindi-English",
    preferred_followup: str = "Phone Call",
    user_id: str = "",
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """Record a human escalation request in SQLite after sanitizing sensitive data.

    HARD RULE: If user_consent is False, escalation is rejected and NOT created.
    """
    init_db(db_path)
    if not user_consent:
        logger.warning(
            f"Escalation request rejected for '{caller_name}': User consent was False."
        )
        return {
            "success": False,
            "error": "User consent denied. Human escalation request was NOT created.",
        }

    clean_user_id = (user_id or caller_name or "user_101").strip().lower()
    clean_caller_name = (caller_name or "Caller").strip()
    clean_what_happened = sanitize_text(what_happened)
    clean_what_agent_checked = sanitize_text(what_agent_checked)
    clean_urgency = urgency.upper().strip() if urgency else "NORMAL"
    if clean_urgency not in ("HIGH", "URGENT", "NORMAL", "LOW"):
        clean_urgency = "NORMAL"

    timestamp = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO human_escalations (
                    user_id, caller_name, reason_category, what_happened,
                    what_agent_checked, urgency, language, preferred_followup, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?);
                """,
                (
                    clean_user_id,
                    clean_caller_name,
                    reason_category,
                    clean_what_happened,
                    clean_what_agent_checked,
                    clean_urgency,
                    language,
                    preferred_followup,
                    timestamp,
                ),
            )
            record_id = cursor.lastrowid
        logger.info(
            f"Created escalation ticket #{record_id} for '{clean_caller_name}'."
        )
        return {
            "success": True,
            "id": record_id,
            "user_id": clean_user_id,
            "caller_name": clean_caller_name,
            "reason_category": reason_category,
            "what_happened": clean_what_happened,
            "what_agent_checked": clean_what_agent_checked,
            "urgency": clean_urgency,
            "language": language,
            "preferred_followup": preferred_followup,
            "status": "OPEN",
            "created_at": timestamp,
        }
    finally:
        conn.close()


def get_escalations(
    status: str | None = None, db_path: str = DEFAULT_DB_PATH
) -> list[dict]:
    """Retrieve human escalation requests from SQLite database."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if status:
            cursor.execute(
                """
                SELECT id, user_id, caller_name, reason_category, what_happened,
                       what_agent_checked, urgency, language, preferred_followup, status, created_at
                FROM human_escalations
                WHERE LOWER(status) = LOWER(?)
                ORDER BY id DESC;
                """,
                (status,),
            )
        else:
            cursor.execute(
                """
                SELECT id, user_id, caller_name, reason_category, what_happened,
                       what_agent_checked, urgency, language, preferred_followup, status, created_at
                FROM human_escalations
                ORDER BY id DESC;
                """
            )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def resolve_escalation(escalation_id: int, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Mark an escalation request as RESOLVED."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE human_escalations SET status = 'RESOLVED' WHERE id = ?;",
                (escalation_id,),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()
