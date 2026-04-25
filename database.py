"""
Database using PostgreSQL (via Railway) for persistent storage.
Falls back to SQLite for local development.
"""

import os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def _conn():
        return psycopg2.connect(DATABASE_URL, sslmode="require")
else:
    import sqlite3

    def _conn():
        return sqlite3.connect("emails.db")


def init_db():
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS processed_emails (
                        id SERIAL PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        client_name TEXT NOT NULL,
                        sender TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        body TEXT NOT NULL,
                        reply TEXT NOT NULL,
                        processed_at TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_memory (
                        id SERIAL PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        sender TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
            conn.commit()
    else:
        with _conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT, client_name TEXT, sender TEXT,
                    subject TEXT, body TEXT, reply TEXT, processed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT, sender TEXT, role TEXT,
                    content TEXT, created_at TEXT
                )
            """)
            conn.commit()


def log_email(client_id: str, client_name: str, email_data: dict, reply: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO processed_emails
                        (client_id, client_name, sender, subject, body, reply, processed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (client_id, client_name, email_data["sender"],
                      email_data["subject"], email_data["body"], reply, now))
                cur.execute("""
                    INSERT INTO conversation_memory (client_id, sender, role, content, created_at)
                    VALUES (%s, %s, 'user', %s, %s)
                """, (client_id, email_data["sender"], email_data["body"], now))
                cur.execute("""
                    INSERT INTO conversation_memory (client_id, sender, role, content, created_at)
                    VALUES (%s, %s, 'assistant', %s, %s)
                """, (client_id, email_data["sender"], reply, now))
            conn.commit()
    else:
        with _conn() as conn:
            conn.execute("""
                INSERT INTO processed_emails
                    (client_id, client_name, sender, subject, body, reply, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (client_id, client_name, email_data["sender"],
                  email_data["subject"], email_data["body"], reply, now))
            conn.execute("INSERT INTO conversation_memory (client_id, sender, role, content, created_at) VALUES (?, ?, 'user', ?, ?)",
                        (client_id, email_data["sender"], email_data["body"], now))
            conn.execute("INSERT INTO conversation_memory (client_id, sender, role, content, created_at) VALUES (?, ?, 'assistant', ?, ?)",
                        (client_id, email_data["sender"], reply, now))
            conn.commit()


def get_conversation_history(client_id: str, sender: str, limit: int = 10) -> list[dict]:
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT role, content FROM conversation_memory
                    WHERE client_id = %s AND sender = %s
                    ORDER BY created_at DESC LIMIT %s
                """, (client_id, sender, limit))
                rows = cur.fetchall()
    else:
        with _conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT role, content FROM conversation_memory
                WHERE client_id = ? AND sender = ?
                ORDER BY created_at DESC LIMIT ?
            """, (client_id, sender, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def get_all_emails(limit: int = 100) -> list[dict]:
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM processed_emails ORDER BY processed_at DESC LIMIT %s", (limit,))
                return [dict(r) for r in cur.fetchall()]
    else:
        with _conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM processed_emails ORDER BY processed_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]


def get_stats() -> dict:
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM processed_emails")
                total = cur.fetchone()[0]
                cur.execute("SELECT client_name, COUNT(*) FROM processed_emails GROUP BY client_name")
                clients = cur.fetchall()
    else:
        with _conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM processed_emails").fetchone()[0]
            clients = conn.execute("SELECT client_name, COUNT(*) FROM processed_emails GROUP BY client_name").fetchall()
    return {
        "total": total,
        "by_client": [{"name": r[0], "count": r[1]} for r in clients],
    }
