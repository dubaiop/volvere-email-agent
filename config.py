"""
Client configuration — one entry per business client.
Add a new dict to CLIENTS to onboard a new client.
"""

CLIENTS = {
    "acme_support": {
        "name": "Acme Corp",
        "system_prompt": (
            "You are a helpful customer support agent for Acme Corp. "
            "Be friendly, concise, and professional. "
            "If you cannot answer something, say you will escalate to a human."
        ),
        "email_address": "support@acmecorp.com",
        "email_password": "YOUR_APP_PASSWORD",  # Gmail App Password
        "imap_server": "imap.gmail.com",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
    },
    # Add more clients here:
    # "client_two": { ... }
}

# Claude model to use
CLAUDE_MODEL = "claude-sonnet-4-6"
