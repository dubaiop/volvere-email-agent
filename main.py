"""
Main runner — processes unread emails for all configured clients.
"""

from config import CLIENTS
from email_reader import fetch_unread_emails
from agent import generate_reply
from email_sender import send_reply
from database import init_db, log_email, already_processed


def run():
    init_db()

    for client_id, client_config in CLIENTS.items():
        print(f"\n[{client_id}] Checking inbox for {client_config['name']}...")

        try:
            emails = fetch_unread_emails(client_config)

            if not emails:
                print("  No new emails.")
                continue

            for email_data in emails:
                # Skip automated/no-reply emails
                sender = email_data["sender"].lower()
                if any(x in sender for x in ["no-reply", "noreply", "sendgrid", "mailer-daemon"]):
                    print(f"  Skipping automated email from: {email_data['sender']}")
                    continue

                if already_processed(client_id, email_data["sender"], email_data["body"]):
                    print(f"  Skipping duplicate: {email_data['subject']}")
                    continue

                print(f"  Processing: {email_data['subject']}")
                reply = generate_reply(client_id, client_config, email_data)
                send_reply(client_config, email_data, reply)
                log_email(client_id, client_config["name"], email_data, reply)

        except Exception as e:
            print(f"  ERROR for {client_id}: {e}")


if __name__ == "__main__":
    run()
