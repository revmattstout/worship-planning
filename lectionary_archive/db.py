"""SQLite schema and connection helper for the lectionary archive database."""
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "lectionary.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS weeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    series_name TEXT,
    series_url TEXT,
    theme_title TEXT,
    liturgical_name TEXT,
    sunday_date TEXT,
    teaser TEXT,
    colors TEXT,
    date_published TEXT,
    date_modified TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS scripture_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id INTEGER NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
    reference TEXT NOT NULL,
    reading_type TEXT,
    url TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id INTEGER NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
    page_type TEXT NOT NULL,
    title TEXT,
    url TEXT UNIQUE NOT NULL,
    body_html TEXT,
    body_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_weeks_sunday_date ON weeks(sunday_date);
CREATE INDEX IF NOT EXISTS idx_scripture_refs_week ON scripture_refs(week_id);
CREATE INDEX IF NOT EXISTS idx_pages_week ON pages(week_id);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    title,
    body_text,
    series_name,
    liturgical_name,
    scripture,
    page_type UNINDEXED,
    sunday_date UNINDEXED,
    url UNINDEXED,
    week_id UNINDEXED
);
"""


def connect(db_path=DEFAULT_DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def rebuild_search_index(conn):
    """Rebuild the FTS5 index from weeks/pages/scripture_refs. Safe to re-run any time."""
    conn.execute("DELETE FROM search_index")
    rows = conn.execute(
        """
        SELECT
            p.title, p.body_text, w.series_name, w.liturgical_name,
            (SELECT group_concat(reference, ', ') FROM scripture_refs sr WHERE sr.week_id = w.id) AS scripture,
            p.page_type, w.sunday_date, p.url, w.id
        FROM pages p
        JOIN weeks w ON w.id = p.week_id
        """
    ).fetchall()
    conn.executemany(
        """
        INSERT INTO search_index
            (title, body_text, series_name, liturgical_name, scripture, page_type, sunday_date, url, week_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
