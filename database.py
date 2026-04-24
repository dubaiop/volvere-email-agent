"""
SQLite database for logging processed emails and conversation memory.
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
        # Conversation memory per agent + sender
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                role TEXT NOT NULL,        -- 'user' or 'assistant'
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def log_email(client_id: str, client_name: str, email_data: dict, reply: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        # Log for dashboard
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
            now,
        ))
        # Save to conversation memory
        conn.execute("""
            INSERT INTO conversation_memory (client_id, sender, role, content, created_at)
            VALUES (?, ?, 'user', ?, ?)
        """, (client_id, email_data["sender"], email_data["body"], now))

        conn.execute("""
            INSERT INTO conversation_memory (client_id, sender, role, content, created_at)
            VALUES (?, ?, 'assistant', ?, ?)
        """, (client_id, email_data["sender"], reply, now))

        conn.commit()


def get_conversation_history(client_id: str, sender: str, limit: int = 10) -> list[dict]:
    """Returns the last N messages between this agent and this sender."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT role, content FROM conversation_memory
            WHERE client_id = ? AND sender = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (client_id, sender, limit)).fetchall()
    # Reverse so oldest is first (Claude expects chronological order)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


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
