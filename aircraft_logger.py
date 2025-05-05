import csv
import datetime
import smtplib
from email.message import EmailMessage
import socket
import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Settings from environment variables
OUTPUT_DIR = "/home/pi/aircraft_logs"
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

FR24_FEED_HOST = "127.0.0.1"
FR24_FEED_PORT = 30003  # Raw Beast output

os.makedirs(OUTPUT_DIR, exist_ok=True)
today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
filename = os.path.join(OUTPUT_DIR, f"aircraft_log_{today_str}.csv")

# Track seen aircraft with latest metadata
seen_aircraft = {}
last_seen = {}

# Metadata cache to reduce API calls
meta_cache = {}

# Write CSV header
with open(filename, mode="w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Time UTC", "Hex", "Callsign", "Altitude", "Speed", "Latitude", "Longitude",
        "Registration", "Model", "Operator"
    ])

def parse_sbs1_line(line):
    fields = line.split(',')
    if len(fields) < 22 or fields[0] != 'MSG':
        return None
    return {
        "hex": fields[4],
        "callsign": fields[10].strip(),
        "altitude": fields[11],
        "speed": fields[12],
        "lat": fields[14],
        "lon": fields[15]
    }

def enrich_metadata(hexcode):
    if hexcode in meta_cache:
        return meta_cache[hexcode]
    try:
        r = requests.get(f"https://opensky-network.org/api/metadata/aircraft/icao/{hexcode}", timeout=3)
        if r.status_code == 200:
            data = r.json()
            reg = data.get("registration", "")
            model = data.get("model", "")
            operator = data.get("operator", "")
            meta_cache[hexcode] = (reg, model, operator)
            return reg, model, operator
    except Exception as e:
        print(f"Metadata lookup failed for {hexcode}: {e}")
    meta_cache[hexcode] = ("", "", "")
    return "", "", ""

def flush_stale(writer):
    now = time.time()
    stale_keys = [k for k, t in last_seen.items() if now - t > 120]
    for hexcode in stale_keys:
        entry = seen_aircraft.pop(hexcode, None)
        if entry:
            writer.writerow(entry)
            print(f"Flushed stale aircraft: {entry}")
        last_seen.pop(hexcode, None)

def listen_and_log():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((FR24_FEED_HOST, FR24_FEED_PORT))
        print(f"Connected. Listening for aircraft data...")
        with open(filename, mode="a", newline="") as f:
            writer = csv.writer(f)
            while True:
                data = s.recv(4096).decode(errors='ignore')
                for line in data.strip().split('\n'):
                    entry = parse_sbs1_line(line)
                    if entry:
                        hexcode = entry["hex"]
                        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                        last_seen[hexcode] = time.time()

                        current = seen_aircraft.get(hexcode, [now, hexcode, '', '', '', '', '', '', '', ''])

                        # Update fields only if they are non-empty
                        current[2] = entry["callsign"] or current[2]
                        current[3] = entry["altitude"] or current[3]
                        current[4] = entry["speed"] or current[4]
                        current[5] = entry["lat"] or current[5]
                        current[6] = entry["lon"] or current[6]

                        if current[7] == "":
                            reg, model, operator = enrich_metadata(hexcode)
                            current[7] = reg
                            current[8] = model
                            current[9] = operator

                        seen_aircraft[hexcode] = current
                        print(f"Logged aircraft: {current}")

                flush_stale(writer)
                f.flush()

def send_email():
    msg = EmailMessage()
    msg["Subject"] = f"Daily Aircraft Log - {today_str}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg.set_content("Attached is the daily aircraft log from your Raspberry Pi.")

    with open(filename, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=os.path.basename(filename))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

# Main loop
try:
    print("Starting aircraft logger...")
    listen_and_log()
except KeyboardInterrupt:
    print("Stopped by user. Sending email...")
    send_email()
except Exception as e:
    print(f"Error occurred: {e}")
