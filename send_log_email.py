import os
import datetime
import smtplib
from email.message import EmailMessage
import zipfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/pi/aircraft-logger/.env')

# Configuration from environment
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# Paths
log_dir = "/home/pi/aircraft-logger/logs"
today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
csv_filename = os.path.join(log_dir, f"aircraft_log_{today_str}.csv")
zip_filename = os.path.join(log_dir, f"{today_str}.zip")

# Create ZIP if CSV exists
if os.path.isfile(csv_filename):
    try:
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(csv_filename, arcname=os.path.basename(csv_filename))
        print(f"Zipped {csv_filename} to {zip_filename}")
    except Exception as e:
        print(f"Failed to zip log file: {e}")
        zip_filename = None
else:
    print(f"No log file found for today: {csv_filename}")
    zip_filename = None

# Compose and send email
try:
    msg = EmailMessage()
    msg["Subject"] = f"Daily Aircraft Log - {today_str}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg.set_content("Attached is the daily aircraft log from your Raspberry Pi.")

    if zip_filename and os.path.isfile(zip_filename):
        with open(zip_filename, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="zip", filename=os.path.basename(zip_filename))
    else:
        msg.set_content("No log file was available to attach today.")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    print("Email sent.")
except Exception as e:
    print(f"Error sending email: {e}")
