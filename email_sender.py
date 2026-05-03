"""
Sends reply emails via Gmail SMTP using the agent's app password.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_reply(client_config: dict, original_email: dict, reply_body: str) -> None:
    sender = client_config["email_address"]
    password = client_config["email_password"]
    recipient = _extract_address(original_email["sender"])
    subject = f"Re: {original_email['subject']}"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(reply_body, "plain"))

    try:
        with smtplib.SMTP(client_config["smtp_server"], client_config["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
            print(f"  Reply sent to {recipient} via Gmail SMTP")
    except Exception as e:
        print(f"  SMTP error: {e}")


def _extract_address(sender_field: str) -> str:
    if "<" in sender_field and ">" in sender_field:
        return sender_field.split("<")[1].strip(">").strip()
    return sender_field.strip()
