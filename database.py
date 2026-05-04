"""
Database using PostgreSQL (via Railway) for persistent storage.
Falls back to SQLite for local development.
"""

import os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL", "")

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
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_memory (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
            conn.commit()
    else:
        with _conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT, agent_id TEXT, role TEXT,
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


def already_processed(client_id: str, sender: str, body: str) -> bool:
    """Returns True if this exact email body was already processed in the last 24 hours."""
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM processed_emails
                    WHERE client_id = %s AND sender = %s AND body = %s
                    AND processed_at::timestamp > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """, (client_id, sender, body))
                return cur.fetchone() is not None
    else:
        with _conn() as conn:
            row = conn.execute("""
                SELECT 1 FROM processed_emails
                WHERE client_id = ? AND sender = ? AND body = ?
                AND processed_at > datetime('now', '-24 hours')
                LIMIT 1
            """, (client_id, sender, body)).fetchone()
            return row is not None


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


def save_agent_message(session_id: str, agent_id: str, role: str, content: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_memory (session_id, agent_id, role, content, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session_id, agent_id, role, content, now))
            conn.commit()
    else:
        with _conn() as conn:
            conn.execute("""
                INSERT INTO agent_memory (session_id, agent_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, agent_id, role, content, now))
            conn.commit()


def get_agent_history(session_id: str, agent_id: str, limit: int = 30) -> list[dict]:
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT role, content FROM agent_memory
                    WHERE session_id = %s AND agent_id = %s
                    ORDER BY created_at ASC LIMIT %s
                """, (session_id, agent_id, limit))
                rows = cur.fetchall()
    else:
        with _conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT role, content FROM agent_memory
                WHERE session_id = ? AND agent_id = ?
                ORDER BY created_at ASC LIMIT ?
            """, (session_id, agent_id, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_setting(key: str, default: str = "") -> str:
    try:
        if DATABASE_URL:
            with _conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
                    row = cur.fetchone()
                    return row[0] if row else default
        else:
            with _conn() as conn:
                row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
                return row[0] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str):
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (key, value))
            conn.commit()
    else:
        with _conn() as conn:
            conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
