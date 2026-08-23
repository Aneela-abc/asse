"""
Database connection manager and schema executor.

CareFlow SQLite database support:
- WAL mode
- Foreign key enforcement
- Busy timeout
- Row factory
- Automatic database directory creation
- Automatic schema initialization
- Automatic job_state creation
- Safe notification table migration
"""

import os
import sqlite3
from pathlib import Path


# ============================================================
# PATH CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = ROOT_DIR / "data" / "healthcare.db"

SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schema.sql"
)


# ============================================================
# DATABASE PATH
# ============================================================

def get_db_path() -> Path:
    """
    Return the SQLite database path.

    If DB_PATH environment variable is set,
    that path is used.

    Otherwise:
        data/healthcare.db
    """

    env_path = os.getenv("DB_PATH")

    if env_path:
        return Path(env_path)

    return DEFAULT_DB_PATH


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db() -> sqlite3.Connection:
    """
    Create and return a configured SQLite connection.
    """

    db_path = get_db_path()

    # Create database directory
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        timeout=30,
    )

    # Dictionary-like rows
    conn.row_factory = sqlite3.Row

    # Foreign keys
    conn.execute(
        "PRAGMA foreign_keys = ON;"
    )

    # WAL mode
    try:
        conn.execute(
            "PRAGMA journal_mode = WAL;"
        )
    except sqlite3.Error:
        pass

    # Busy timeout
    conn.execute(
        "PRAGMA busy_timeout = 30000;"
    )

    # Good balance between durability and performance
    conn.execute(
        "PRAGMA synchronous = NORMAL;"
    )

    return conn


# ============================================================
# CHECK TABLE EXISTS
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


# ============================================================
# GET TABLE COLUMNS
# ============================================================

def get_columns(
    conn: sqlite3.Connection,
    table_name: str,
):
    """
    Return a set containing the columns of a table.
    """

    if not table_exists(conn, table_name):
        return set()

    rows = conn.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


# ============================================================
# JOB STATE TABLE
# ============================================================

def ensure_job_state_table(
    conn: sqlite3.Connection,
):
    """
    Ensure background-job state table exists.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


# ============================================================
# NOTIFICATION TABLE MIGRATION
# ============================================================

def ensure_notifications_table(
    conn: sqlite3.Connection,
):
    """
    Ensure notifications table exists and contains
    all columns required by services.py.

    This is intentionally defensive so an older
    healthcare.db does not break the application.
    """

    # --------------------------------------------------------
    # If notifications table does not exist,
    # create it.
    # --------------------------------------------------------

    if not table_exists(conn, "notifications"):

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
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

    # --------------------------------------------------------
    # Existing table.
    # Check for missing columns.
    # --------------------------------------------------------

    columns = get_columns(
        conn,
        "notifications",
    )

    migrations = {
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
    }

    for column, definition in migrations.items():

        if column not in columns:

            try:

                conn.execute(
                    f"""
                    ALTER TABLE notifications
                    ADD COLUMN "{column}" {definition}
                    """
                )

            except sqlite3.OperationalError:
                # Ignore a migration if SQLite says the
                # column already exists.
                pass


# ============================================================
# MEDICATION REMINDER TABLE
# ============================================================

def ensure_medication_reminders_table(
    conn: sqlite3.Connection,
):
    """
    Ensure medication reminder table exists.
    """

    if not table_exists(
        conn,
        "medication_reminders",
    ):

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS medication_reminders (
                id TEXT PRIMARY KEY,
                appointment_id TEXT,
                patient_id TEXT NOT NULL,
                medication_text TEXT NOT NULL,
                frequency_hours REAL NOT NULL DEFAULT 24,
                start_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                next_run_at TEXT NOT NULL
            )
            """
        )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_database():
    """
    Initialize the CareFlow database.

    Steps:
    1. Open database.
    2. Load schema.sql.
    3. Create job_state.
    4. Repair notifications table.
    5. Create medication reminders if missing.
    6. Commit changes.
    7. Seed initial data.
    """

    conn = get_db()

    try:

        # ----------------------------------------------------
        # Load main schema
        # ----------------------------------------------------

        if not SCHEMA_PATH.exists():

            raise FileNotFoundError(
                f"Database schema not found: {SCHEMA_PATH}"
            )

        with open(
            SCHEMA_PATH,
            "r",
            encoding="utf-8",
        ) as f:

            schema_sql = f.read()

        if schema_sql.strip():

            conn.executescript(
                schema_sql
            )

        # ----------------------------------------------------
        # Required tables
        # ----------------------------------------------------

        ensure_job_state_table(
            conn
        )

        ensure_notifications_table(
            conn
        )

        ensure_medication_reminders_table(
            conn
        )

        # ----------------------------------------------------
        # Commit all changes
        # ----------------------------------------------------

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()

    # --------------------------------------------------------
    # Seed initial data
    # --------------------------------------------------------

    try:

        from .seed import seed_initial_data

        seed_initial_data()

    except Exception:
        # Do not silently break database initialization
        # if seed data is already present or unavailable.
        raise


# ============================================================
# REPAIR DATABASE
# ============================================================

def repair_database():
    """
    Repair an existing CareFlow database without deleting data.

    Useful after deploying a new version of the application.
    """

    conn = get_db()

    try:

        # Make sure core tables exist
        if SCHEMA_PATH.exists():

            with open(
                SCHEMA_PATH,
                "r",
                encoding="utf-8",
            ) as f:

                schema_sql = f.read()

            if schema_sql.strip():

                conn.executescript(
                    schema_sql
                )

        # Repair required tables
        ensure_job_state_table(
            conn
        )

        ensure_notifications_table(
            conn
        )

        ensure_medication_reminders_table(
            conn
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

def database_health() -> dict:
    """
    Return basic database information.
    Useful for debugging Streamlit Cloud.
    """

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

        table_names = [
            row["name"]
            for row in tables
        ]

        notification_columns = sorted(
            get_columns(
                conn,
                "notifications",
            )
        )

        return {
            "database_path": str(db_path),
            "database_exists": db_path.exists(),
            "tables": table_names,
            "notifications_columns":
                notification_columns,
        }

    finally:

        conn.close()