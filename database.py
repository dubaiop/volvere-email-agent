"""
SQLite database for logging processed emails.
"""

import sqlite3
from datetime import datetime

DB_FILE = "emails.db"


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                client_name TEXT NOT NULL,
                sender TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                reply TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )
        """)
        conn.commit()


def log_email(client_id: str, client_name: str, email_data: dict, reply: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO processed_emails
                (client_id, client_name, sender, subject, body, reply, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            client_name,
            email_data["sender"],
            email_data["subject"],
            email_data["body"],
            reply,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        conn.commit()


def get_all_emails(limit: int = 100) -> list[dict]:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM processed_emails
            ORDER BY processed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_stats() -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        total = conn.execute("SELECT COUNT(*) FROM processed_emails").fetchone()[0]
        clients = conn.execute(
            "SELECT client_name, COUNT(*) as count FROM processed_emails GROUP BY client_name"
        ).fetchall()
    return {
        "total": total,
        "by_client": [{"name": r[0], "count": r[1]} for r in clients],
    }
