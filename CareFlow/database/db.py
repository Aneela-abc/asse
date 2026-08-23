"""
CareFlow SQLite database manager.

This version is designed for Streamlit Cloud where the SQLite database may
start as a brand-new empty file.  Every connection makes sure that the core
CareFlow tables exist before application code queries them.

Features:
- WAL mode
- Foreign-key enforcement
- Busy timeout
- Row factory
- Automatic database directory creation
- Automatic core-schema initialization
- Automatic runtime/job tables
- Safe migrations for older databases
- Optional schema.sql execution when present
"""

import os
import sqlite3
from pathlib import Path


# ============================================================
# PATH CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "healthcare.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


# ============================================================
# DATABASE PATH
# ============================================================

def get_db_path() -> Path:
    """Return the SQLite database path."""

    env_path = os.getenv("DB_PATH")

    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path

    return DEFAULT_DB_PATH


# ============================================================
# BASIC SCHEMA HELPERS
# ============================================================

def table_exists(
    conn: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name=?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_columns(
    conn: sqlite3.Connection,
    table_name: str,
):
    """Return a set of column names for a table."""

    if not table_exists(conn, table_name):
        return set()

    rows = conn.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return {row["name"] for row in rows}


def _add_missing_columns(
    conn: sqlite3.Connection,
    table_name: str,
    columns: dict,
):
    """Add safe missing columns to an existing table."""

    existing = get_columns(conn, table_name)

    for column, definition in columns.items():
        if column in existing:
            continue

        try:
            conn.execute(
                f'ALTER TABLE "{table_name}" '
                f'ADD COLUMN "{column}" {definition}'
            )
        except sqlite3.OperationalError:
            # A concurrent initialization may have added it already.
            pass


# ============================================================
# CORE CAREFLOW TABLES
# ============================================================

def ensure_core_schema(conn: sqlite3.Connection):
    """
    Ensure the core CareFlow application tables exist.

    This is the important Streamlit Cloud fix.  A fresh SQLite database must
    have users/doctors/appointments/google_tokens before services.py starts
    querying them.

    schema.sql is executed first when available, then the CREATE TABLE IF NOT
    EXISTS statements below act as a defensive fallback for a fresh or older
    database.
    """

    # --------------------------------------------------------
    # Use the project's schema.sql when it exists.
    # --------------------------------------------------------

    if SCHEMA_PATH.exists():
        try:
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            if schema_sql.strip():
                conn.executescript(schema_sql)
        except sqlite3.Error:
            # Do not prevent the fallback schema from running.  This is
            # especially useful when an old schema.sql contains an optional
            # migration that SQLite cannot apply to a fresh database.
            pass

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    _add_missing_columns(
        conn,
        "users",
        {
            "name": "TEXT",
            "email": "TEXT",
            "password_hash": "TEXT",
            "role": "TEXT DEFAULT 'patient'",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # DOCTORS
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS doctors (
            user_id TEXT PRIMARY KEY,
            specialization TEXT NOT NULL DEFAULT 'General Medicine',
            working_days TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri',
            start_time TEXT NOT NULL DEFAULT '09:00',
            end_time TEXT NOT NULL DEFAULT '17:00',
            slot_minutes INTEGER NOT NULL DEFAULT 30,
            leave_days TEXT NOT NULL DEFAULT '[]'
        )
        """
    )

    _add_missing_columns(
        conn,
        "doctors",
        {
            "specialization": "TEXT DEFAULT 'General Medicine'",
            "working_days": "TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri'",
            "start_time": "TEXT DEFAULT '09:00'",
            "end_time": "TEXT DEFAULT '17:00'",
            "slot_minutes": "INTEGER DEFAULT 30",
            "leave_days": "TEXT DEFAULT '[]'",
        },
    )

    # --------------------------------------------------------
    # APPOINTMENTS
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            doctor_id TEXT NOT NULL,
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'CONFIRMED',
            hold_until TEXT,
            symptoms TEXT,
            previsit_summary TEXT,
            doctor_notes TEXT,
            prescription TEXT,
            postvisit_summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    _add_missing_columns(
        conn,
        "appointments",
        {
            "patient_id": "TEXT",
            "doctor_id": "TEXT",
            "start_at": "TEXT",
            "end_at": "TEXT",
            "status": "TEXT DEFAULT 'CONFIRMED'",
            "hold_until": "TEXT",
            "symptoms": "TEXT",
            "previsit_summary": "TEXT",
            "doctor_notes": "TEXT",
            "prescription": "TEXT",
            "postvisit_summary": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # GOOGLE TOKENS
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS google_tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            expires_at INTEGER,
            scope TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )

    _add_missing_columns(
        conn,
        "google_tokens",
        {
            "access_token": "TEXT",
            "refresh_token": "TEXT",
            "expires_at": "INTEGER",
            "scope": "TEXT",
            "updated_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # Helpful indexes
    # --------------------------------------------------------

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_start "
        "ON appointments(doctor_id, start_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_appointments_patient "
        "ON appointments(patient_id, start_at)"
    )


# ============================================================
# RUNTIME TABLES
# ============================================================

def ensure_job_state_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def ensure_notifications_table(conn: sqlite3.Connection):
    if not table_exists(conn, "notifications"):
        conn.execute(
            """
            CREATE TABLE notifications (
                id TEXT PRIMARY KEY,
                appointment_id TEXT,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'email',
                status TEXT NOT NULL DEFAULT 'QUEUED',
                attempts INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL DEFAULT '{}',
                next_attempt_at TEXT,
                created_at TEXT NOT NULL,
                last_error TEXT
            )
            """
        )
        return

    _add_missing_columns(
        conn,
        "notifications",
        {
            "appointment_id": "TEXT",
            "user_id": "TEXT",
            "type": "TEXT",
            "channel": "TEXT DEFAULT 'email'",
            "status": "TEXT DEFAULT 'QUEUED'",
            "attempts": "INTEGER DEFAULT 0",
            "payload": "TEXT DEFAULT '{}'",
            "next_attempt_at": "TEXT",
            "created_at": "TEXT",
            "last_error": "TEXT",
        },
    )


def ensure_medication_reminders_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS medication_reminders (
            id TEXT PRIMARY KEY,
            appointment_id TEXT,
            patient_id TEXT,
            medication_text TEXT,
            frequency_hours INTEGER,
            created_at TEXT,
            active INTEGER DEFAULT 1,
            next_run_at TEXT
        )
        """
    )


def ensure_calendar_events_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            appointment_id TEXT,
            provider TEXT,
            external_event_id TEXT,
            status TEXT,
            metadata TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )


# ============================================================
# ALL REQUIRED TABLES
# ============================================================

def ensure_all_tables(conn: sqlite3.Connection):
    """Create/repair every table required by the CareFlow app."""

    ensure_core_schema(conn)
    ensure_job_state_table(conn)
    ensure_notifications_table(conn)
    ensure_medication_reminders_table(conn)
    ensure_calendar_events_table(conn)

    conn.commit()


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db() -> sqlite3.Connection:
    """
    Create and return a configured SQLite connection.

    The core schema is initialized immediately so services.py can safely run
    queries such as SELECT * FROM users on a fresh Streamlit Cloud database.
    """

    db_path = get_db_path()

    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except sqlite3.Error:
        pass

    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    # IMPORTANT: initialize the schema before returning the connection.
    ensure_all_tables(conn)

    return conn


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_database():
    """
    Initialize the database and optionally seed initial data.

    This function is safe to call during local setup or deployment.
    """

    conn = get_db()
    conn.close()

    try:
        from .seed import seed_initial_data
        seed_initial_data()
    except ImportError:
        # Seed module is optional.
        pass


# ============================================================
# REPAIR DATABASE
# ============================================================

def repair_database():
    """Repair an existing CareFlow database without deleting data."""

    conn = get_db()
    try:
        ensure_all_tables(conn)
    finally:
        conn.close()


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

def database_health() -> dict:
    """Return basic database information for debugging."""

    conn = get_db()

    try:
        db_path = get_db_path()

        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
            """
        ).fetchall()

        table_names = [row["name"] for row in tables]

        return {
            "database_path": str(db_path),
            "database_exists": db_path.exists(),
            "tables": table_names,
            "users_columns": sorted(get_columns(conn, "users")),
            "doctors_columns": sorted(get_columns(conn, "doctors")),
            "appointments_columns": sorted(
                get_columns(conn, "appointments")
            ),
            "google_tokens_columns": sorted(
                get_columns(conn, "google_tokens")
            ),
            "notifications_columns": sorted(
                get_columns(conn, "notifications")
            ),
        }

    finally:
        conn.close()