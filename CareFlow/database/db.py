"""
Database connection manager and schema executor.
Supports SQLite with WAL mode, foreign key enforcement, and explicit table schema loading.
"""
import os
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / 'data' / 'healthcare.db'
SCHEMA_PATH = Path(__file__).resolve().parent / 'schema.sql'


def get_db_path() -> Path:
    env_path = os.getenv('DB_PATH')
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def get_db() -> sqlite3.Connection:
    """Returns a configured SQLite database connection with row factory and pragmas."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.execute('PRAGMA busy_timeout = 5000;')
    return conn


def init_database():
    """Initializes tables using schema.sql and runs initial data seeding."""
    conn = get_db()
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    # Import seed here to avoid circular dependencies
    from .seed import seed_initial_data
    seed_initial_data()
