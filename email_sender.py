"""
Sends a reply email to the original sender.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_reply(client_config: dict, original_email: dict, reply_body: str) -> None:
    """
    Sends reply_body as an email to the original sender.
    """
    sender = client_config["email_address"]
    recipient = _extract_address(original_email["sender"])
    subject = f"Re: {original_email['subject']}"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(reply_body, "plain"))

    with smtplib.SMTP(client_config["smtp_server"], client_config["smtp_port"]) as server:
        server.starttls()
        server.login(sender, client_config["email_password"])
        server.sendmail(sender, recipient, msg.as_string())

    print(f"  Reply sent to {recipient}")


def _extract_address(sender_field: str) -> str:
    """Extracts plain email address from 'Name <email>' format."""
    if "<" in sender_field and ">" in sender_field:
        return sender_field.split("<")[1].strip(">").strip()
    return sender_field.strip()
