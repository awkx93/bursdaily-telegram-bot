import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "seen_articles.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS seen (url TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )


def is_seen(url: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT 1 FROM seen WHERE url = ?", (url,)).fetchone()
        return row is not None


def mark_seen(url: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO seen (url) VALUES (?)", (url,))
