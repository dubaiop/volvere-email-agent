"""
Sends reply emails via SendGrid API (avoids SMTP port blocking on Railway).
"""

import os
import urllib.request
import urllib.error
import json


def send_reply(client_config: dict, original_email: dict, reply_body: str) -> None:
    sender = client_config["email_address"]
    recipient = _extract_address(original_email["sender"])
    subject = f"Re: {original_email['subject']}"

    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")

    data = json.dumps({
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/plain", "value": reply_body}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {sendgrid_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  Reply sent to {recipient} (status {resp.status})")
    except urllib.error.HTTPError as e:
        print(f"  SendGrid error {e.code}: {e.read().decode()}")


def _extract_address(sender_field: str) -> str:
    if "<" in sender_field and ">" in sender_field:
        return sender_field.split("<")[1].strip(">").strip()
    return sender_field.strip()
