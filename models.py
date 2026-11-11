from __future__ import annotations

from collections.abc import Generator
from contextlib import closing
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent / "items.db"

VALID_TYPES = ("lost", "found")
VALID_CATEGORIES = (
    "Smart Card / ID",
    "Keys",
    "Electronics / Audio",
    "Stationery / Drafter",
    "Cycle / Other",
)
VALID_LOCATIONS = (
    "Central Library",
    "LT / LP Complex",
    "Hostel Area",
    "COS / Sports",
    "Other",
)
VALID_STATUSES = ("open", "resolved")


def _sql_in_list(values: tuple[str, ...]) -> str:
    """Format a tuple of string constants into a SQL IN (...) literal list."""
    escaped = (value.replace("'", "''") for value in values)
    return ", ".join(f"'{value}'" for value in escaped)


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection to the items database."""
    target_path = Path(db_path) if db_path is not None else DB_PATH
    conn = sqlite3.connect(target_path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection for FastAPI request dependencies."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Initialize the SQLite database schema and indexes without seed data."""
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK (type IN ({_sql_in_list(VALID_TYPES)})),
            title TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ({_sql_in_list(VALID_CATEGORIES)})),
            location TEXT NOT NULL CHECK (location IN ({_sql_in_list(VALID_LOCATIONS)})),
            date_reported TEXT NOT NULL,
            description TEXT,
            image_filename TEXT,
            contact_phone TEXT NOT NULL,
            status TEXT DEFAULT 'open' CHECK (status IN ({_sql_in_list(VALID_STATUSES)})),
            manage_token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_items_filter
        ON items (type, status, category, location);
    """

    with closing(get_connection(db_path)) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(create_table_sql)
        conn.execute(create_index_sql)
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")

