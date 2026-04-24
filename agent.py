"""
Processes an email using Claude API and returns a reply.
Includes conversation memory so the agent remembers past exchanges.
"""

import anthropic
from config import CLAUDE_MODEL
from database import get_conversation_history


def generate_reply(client_id: str, client_config: dict, email_data: dict) -> str:
    """
    Sends the email to Claude with past conversation history and returns a reply.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    # Load past conversation with this sender
    history = get_conversation_history(client_id, email_data["sender"], limit=10)

    # Build the new user message
    new_message = (
        f"From: {email_data['sender']}\n"
        f"Subject: {email_data['subject']}\n\n"
        f"{email_data['body']}"
    )

    # Append the new email to the history
    messages = history + [{"role": "user", "content": new_message}]

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=client_config["system_prompt"],
        messages=messages,
    )

    return response.content[0].text
