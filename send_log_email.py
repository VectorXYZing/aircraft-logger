import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import csv
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

EMAIL_HOST = os.getenv("SMTP_SERVER")
EMAIL_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_ADDRESS = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_TO")

LOG_DIR = os.path.expanduser("~/aircraft-logger/logs")
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
LOG_FILE = os.path.join(LOG_DIR, f"aircraft_log_{TODAY}.csv")

# Logging setup
LOGGING_DIR = os.path.expanduser('~/aircraft-logger/logs')
os.makedirs(LOGGING_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOGGING_DIR, 'send_log_email.log')
logger = logging.getLogger('send_log_email')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# Rotating file handler (5MB per file, keep 3 backups)
file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def send_email():
    if not os.path.exists(LOG_FILE):
        logger.error(f"No log file found for {TODAY}")
        return

    # Calculate summary
    total_records = 0
    unique_aircraft = set()
    operator_counts = {}
    model_counts = {}
    try:
        with open(LOG_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_records += 1
                unique_aircraft.add(row.get("Hex", ""))
                operator = row.get("Operator", "")
                if operator:
                    operator_counts[operator] = operator_counts.get(operator, 0) + 1
                model = row.get("Model", "")
                if model:
                    model_counts[model] = model_counts.get(model, 0) + 1
    except Exception as e:
        logger.error(f"Failed to read or parse log file {LOG_FILE}: {e}")
        return
    top_operators = sorted(operator_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    summary_lines = [
        f"Aircraft Log Summary for {TODAY}",
        f"Total records: {total_records}",
        f"Unique aircraft: {len(unique_aircraft)}",
        "Top operators:",
    ]
    for op, count in top_operators:
        summary_lines.append(f"  - {op}: {count}")
    summary_lines.append("Top models:")
    for model, count in top_models:
        summary_lines.append(f"  - {model}: {count}")
    summary_lines.append("\nSee attached aircraft log for today.")
    summary_text = "\n".join(summary_lines)

    subject = f"Aircraft Log Report – {TODAY}"
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject

    msg.attach(MIMEText(summary_text, "plain"))
    try:
        with open(LOG_FILE, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(LOG_FILE))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(LOG_FILE)}"'
        msg.attach(part)
    except Exception as e:
        logger.error(f"Failed to attach log file {LOG_FILE}: {e}")
        return

    try:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info("✅ Email sent successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    send_email()
