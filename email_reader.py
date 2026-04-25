"""
Reads unread emails from a client's inbox.
"""

import imaplib
import email
from email.header import decode_header


def fetch_unread_emails(client_config: dict) -> list[dict]:
    """
    Connects to the client's inbox and returns a list of unread emails.
    Each email is a dict with: uid, subject, sender, body.
    """
    mail = imaplib.IMAP4_SSL(client_config["imap_server"])
    mail.login(client_config["email_address"], client_config["email_password"])
    mail.select("inbox")

    _, uids = mail.search(None, "UNSEEN")
    email_list = []

    for uid in uids[0].split():
        _, msg_data = mail.fetch(uid, "(RFC822)")
        mail.store(uid, '+FLAGS', '\\Seen')  # explicitly mark as read
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        subject = _decode_header(msg["Subject"])
        sender = msg.get("From", "")
        body = _extract_body(msg)

        email_list.append({
            "uid": uid,
            "subject": subject,
            "sender": sender,
            "body": body,
        })

    mail.logout()
    return email_list


def _decode_header(value: str) -> str:
    if not value:
        return ""
    decoded, encoding = decode_header(value)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or "utf-8", errors="replace")
    return decoded


def _extract_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
    return body.strip()
