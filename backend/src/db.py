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


def lookup_caller(search_term: str, db_path: str = DEFAULT_DB_PATH) -> dict | None:
    """Look up a caller profile by user_id or name (case-insensitive)."""
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
