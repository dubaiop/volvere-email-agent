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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS outbound_emails (
                        id SERIAL PRIMARY KEY,
                        from_persona TEXT NOT NULL,
                        from_name TEXT NOT NULL,
                        to_email TEXT NOT NULL,
                        to_name TEXT,
                        subject TEXT NOT NULL,
                        body TEXT NOT NULL,
                        sent_at TEXT NOT NULL,
                        touch_number INTEGER DEFAULT 1,
                        full_sequence TEXT,
                        next_follow_up_at TEXT
                    )
                """)
                for col in [
                    "ALTER TABLE outbound_emails ADD COLUMN IF NOT EXISTS touch_number INTEGER DEFAULT 1",
                    "ALTER TABLE outbound_emails ADD COLUMN IF NOT EXISTS full_sequence TEXT",
                    "ALTER TABLE outbound_emails ADD COLUMN IF NOT EXISTS next_follow_up_at TEXT",
                ]:
                    try:
                        cur.execute(col)
                    except Exception:
                        pass
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS outbound_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_persona TEXT, from_name TEXT,
                    to_email TEXT, to_name TEXT,
                    subject TEXT, body TEXT, sent_at TEXT,
                    touch_number INTEGER DEFAULT 1,
                    full_sequence TEXT,
                    next_follow_up_at TEXT
                )
            """)
            for col_sql in [
                "ALTER TABLE outbound_emails ADD COLUMN touch_number INTEGER DEFAULT 1",
                "ALTER TABLE outbound_emails ADD COLUMN full_sequence TEXT",
                "ALTER TABLE outbound_emails ADD COLUMN next_follow_up_at TEXT",
            ]:
                try:
                    conn.execute(col_sql)
                except Exception:
                    pass
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


def log_outbound(from_persona: str, from_name: str, to_email: str, to_name: str,
                 subject: str, body: str, full_sequence: str = "", next_follow_up_at: str = "") -> int:
    """Returns the inserted row id so callers can reference it for follow-ups."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO outbound_emails
                        (from_persona, from_name, to_email, to_name, subject, body, sent_at,
                         touch_number, full_sequence, next_follow_up_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s) RETURNING id
                """, (from_persona, from_name, to_email, to_name, subject, body, now,
                      full_sequence or None, next_follow_up_at or None))
                row_id = cur.fetchone()[0]
            conn.commit()
        return row_id
    else:
        with _conn() as conn:
            cur = conn.execute("""
                INSERT INTO outbound_emails
                    (from_persona, from_name, to_email, to_name, subject, body, sent_at,
                     touch_number, full_sequence, next_follow_up_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (from_persona, from_name, to_email, to_name, subject, body, now,
                  full_sequence or None, next_follow_up_at or None))
            conn.commit()
            return cur.lastrowid


def get_due_followups() -> list[dict]:
    """Return outbound emails whose next_follow_up_at is due and have remaining touches."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM outbound_emails
                    WHERE next_follow_up_at IS NOT NULL
                      AND next_follow_up_at <= %s
                      AND touch_number < 5
                      AND full_sequence IS NOT NULL
                    ORDER BY next_follow_up_at ASC
                """, (now,))
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    else:
        with _conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM outbound_emails
                WHERE next_follow_up_at IS NOT NULL
                  AND next_follow_up_at <= ?
                  AND touch_number < 5
                  AND full_sequence IS NOT NULL
                ORDER BY next_follow_up_at ASC
            """, (now,)).fetchall()
            return [dict(r) for r in rows]


def update_touch(record_id: int, touch_number: int, next_follow_up_at: str = ""):
    """Update touch number and next follow-up date after a follow-up is sent."""
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE outbound_emails
                    SET touch_number = %s, next_follow_up_at = %s
                    WHERE id = %s
                """, (touch_number, next_follow_up_at or None, record_id))
            conn.commit()
    else:
        with _conn() as conn:
            conn.execute("""
                UPDATE outbound_emails
                SET touch_number = ?, next_follow_up_at = ?
                WHERE id = ?
            """, (touch_number, next_follow_up_at or None, record_id))
            conn.commit()


def get_outbound_emails(limit: int = 100) -> list[dict]:
    if DATABASE_URL:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM outbound_emails ORDER BY sent_at DESC LIMIT %s", (limit,))
                return [dict(r) for r in cur.fetchall()]
    else:
        with _conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM outbound_emails ORDER BY sent_at DESC LIMIT ?", (limit,)).fetchall()
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
