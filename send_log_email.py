import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import csv

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

    # Calculate summary
    total_records = 0
    unique_aircraft = set()
    operator_counts = {}
    model_counts = {}
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
    with open(LOG_FILE, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(LOG_FILE))
    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(LOG_FILE)}"'
    msg.attach(part)

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
