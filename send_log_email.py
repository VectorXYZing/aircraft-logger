import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Load environment variables
load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

LOG_DIR = os.path.expanduser("~/aircraft-logger/logs")
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
LOG_FILE = os.path.join(LOG_DIR, f"aircraft_log_{TODAY}.csv")

def send_email():
    if not os.path.exists(LOG_FILE):
        print(f"No log file found for {TODAY}")
        return

    with open(LOG_FILE, "r") as f:
        log_content = f.read()

    subject = f"Aircraft Log Report – {TODAY}"
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject

    msg.attach(MIMEText("See attached aircraft log for today.\n\n", "plain"))
    msg.attach(MIMEText(log_content, "plain"))

    try:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    send_email()
