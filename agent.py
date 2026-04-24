"""
Processes an email using Claude API and returns a reply.
"""

import anthropic
from config import CLAUDE_MODEL


def generate_reply(client_config: dict, email_data: dict) -> str:
    """
    Sends the email content to Claude and returns the generated reply.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    user_message = (
        f"You received an email.\n\n"
        f"From: {email_data['sender']}\n"
        f"Subject: {email_data['subject']}\n\n"
        f"Message:\n{email_data['body']}\n\n"
        f"Write a professional reply."
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=client_config["system_prompt"],
        messages=[
            {"role": "user", "content": user_message}
        ],
    )

    return response.content[0].text
