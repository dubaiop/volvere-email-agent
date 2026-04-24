"""
Runs the email agent every 10 minutes automatically.
Start with: python scheduler.py
"""

import time
import schedule
from dotenv import load_dotenv
load_dotenv()
from main import run


def job():
    print("\n--- Running email agent ---")
    run()
    print("--- Done. Waiting for next run... ---")


# Schedule to run every 10 minutes
schedule.every(10).minutes.do(job)

print("Email agent scheduler started. Runs every 10 minutes.")
print("Press Ctrl+C to stop.\n")

# Run once immediately on start
job()

# Then keep running on schedule
while True:
    schedule.run_pending()
    time.sleep(30)  # check every 30 seconds
