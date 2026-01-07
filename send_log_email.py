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
import sys
import shutil
import os

# Load environment variables
load_dotenv()

from airlogger.config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO, SMTP_USE_SSL, SMTP_TIMEOUT

EMAIL_HOST = SMTP_SERVER
EMAIL_PORT = SMTP_PORT
EMAIL_ADDRESS = SMTP_USER
EMAIL_PASSWORD = SMTP_PASSWORD
EMAIL_RECIPIENT = EMAIL_TO
SMTP_USE_SSL = SMTP_USE_SSL
SMTP_TIMEOUT = SMTP_TIMEOUT

LOG_DIR = os.path.expanduser("~/aircraft-logger/logs")
# Allow date override via command line argument
if len(sys.argv) > 1:
    TODAY = sys.argv[1]
else:
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
    # Validate SMTP configuration
    from airlogger.config import validate_smtp_config

    ok, missing = validate_smtp_config()
    if not ok:
        logger.error(f"Missing SMTP/email configuration: {', '.join(missing)}. Aborting email send.")
        return

    if not os.path.exists(LOG_FILE):
        logger.error(f"No log file found for {TODAY}")
        return

    # Calculate summary
    total_records = 0
    unique_aircraft = set()
    operator_counts = {}
    model_counts = {}
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
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
    # Attach a compressed version of the log to reduce size for large logs
    try:
        import gzip
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz") as tmp:
            with open(LOG_FILE, "rb") as src, gzip.GzipFile(fileobj=tmp, mode="wb") as gz:
                shutil.copyfileobj(src, gz)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(tmp_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(tmp_path)}"'
        msg.attach(part)
    except Exception as e:
        logger.error(f"Failed to attach compressed log file for {LOG_FILE}: {e}")
        return

    # Send with retries (handle STARTTLS or SSL)
    import smtplib as _smtplib
    from time import sleep

    attempts = 0
    max_attempts = 3
    tmp_path = locals().get('tmp_path') if 'tmp_path' in locals() else None
    try:
        while attempts < max_attempts:
            try:
                if SMTP_USE_SSL or EMAIL_PORT == 465:
                    server = _smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=SMTP_TIMEOUT)
                else:
                    server = _smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=SMTP_TIMEOUT)
                    server.ehlo()
                    server.starttls()

                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
                server.quit()
                logger.info("✅ Email sent successfully.")
                break
            except _smtplib.SMTPException as e:
                attempts += 1
                logger.warning(f"SMTP send attempt {attempts} failed: {e}")
                if attempts < max_attempts:
                    sleep(2 ** attempts)
                else:
                    logger.error(f"❌ Failed to send email after {attempts} attempts: {e}")
                    break
    finally:
        # cleanup temp compressed file if created
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

if __name__ == "__main__":
    send_email()
