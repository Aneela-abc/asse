"""
Database connection manager and schema executor.

Supports SQLite with:
- WAL mode
- Foreign key enforcement
- Busy timeout
- Row factory
- Automatic database directory creation
- Schema loading
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
    Returns database path.

    If DB_PATH environment variable is set,
    that path will be used.

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

    Configuration:
    - Row factory enabled
    - Foreign keys enabled
    - WAL journal mode
    - Busy timeout enabled
    """

    db_path = get_db_path()

    # Create data directory if it does not exist
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        timeout=10,
    )

    # Return rows as dictionary-like sqlite3.Row objects
    conn.row_factory = sqlite3.Row

    # Enable foreign key constraints
    conn.execute(
        "PRAGMA foreign_keys = ON;"
    )

    # Enable WAL mode for better concurrent access
    conn.execute(
        "PRAGMA journal_mode = WAL;"
    )

    # Wait up to 10 seconds when database is busy
    conn.execute(
        "PRAGMA busy_timeout = 10000;"
    )

    # Reduce synchronous write overhead while
    # maintaining good durability with WAL
    conn.execute(
        "PRAGMA synchronous = NORMAL;"
    )

    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database():
    """
    Initialize database tables using schema.sql.

    Also makes sure the job_state table exists.
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

        conn.executescript(schema_sql)

        # ----------------------------------------------------
        # Make sure background-job state table exists.
        #
        # This prevents:
        # sqlite3.OperationalError:
        # no such table: job_state
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()

    # --------------------------------------------------------
    # Seed initial data
    # --------------------------------------------------------

    from .seed import seed_initial_data

    seed_initial_data()