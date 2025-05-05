import csv
import datetime
import socket
import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/home/pi/aircraft-logger/.env")

# Settings
OUTPUT_DIR = "/home/pi/aircraft-logger/logs"
FR24_FEED_HOST = "127.0.0.1"
FR24_FEED_PORT = 30003  # Raw Beast output

os.makedirs(OUTPUT_DIR, exist_ok=True)
today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
filename = os.path.join(OUTPUT_DIR, f"aircraft_log_{today_str}.csv")

# SMTP from environment
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# Basic cache for metadata
aircraft_cache = {}

# Write CSV header if not already exists
if not os.path.exists(filename):
    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Time UTC", "Hex", "Callsign", "Altitude", "Speed", "Latitude", "Longitude", "Registration", "Type", "Operator"])

# Parse SBS-1 line format
def parse_sbs1_line(line):
    fields = line.split(',')
    if len(fields) < 22 or fields[0] != 'MSG':
        return None
    return {
        "hex": fields[4].strip(),
        "callsign": fields[10].strip(),
        "altitude": fields[11].strip(),
        "speed": fields[12].strip(),
        "lat": fields[14].strip(),
        "lon": fields[15].strip()
    }

# Lookup metadata (registration, type, operator)
def get_aircraft_metadata(hex_code):
    if hex_code in aircraft_cache:
        return aircraft_cache[hex_code]
    try:
        url = f"https://opensky-network.org/api/metadata/aircraft/icao/{hex_code}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            reg = data.get("registration", "")
            ac_type = data.get("typecode", "")
            operator = data.get("operator", "")
            aircraft_cache[hex_code] = (reg, ac_type, operator)
            return reg, ac_type, operator
    except Exception as e:
        print(f"Metadata lookup error for {hex_code}: {e}")
    return ("", "", "")

# Main listener loop
def listen_and_log():
    print("Starting aircraft logger...")
    print(f"Connecting to {FR24_FEED_HOST}:{FR24_FEED_PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((FR24_FEED_HOST, FR24_FEED_PORT))
        print("Connected. Listening for aircraft data...")
        with open(filename, mode="a", newline="") as f:
            writer = csv.writer(f)
            seen = set()
            while True:
                data = s.recv(4096).decode(errors='ignore')
                for line in data.strip().split('\n'):
                    entry = parse_sbs1_line(line)
                    if entry and entry["hex"]:
                        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                        reg, ac_type, operator = get_aircraft_metadata(entry["hex"])
                        row = [
                            now,
                            entry["hex"],
                            entry["callsign"],
                            entry["altitude"],
                            entry["speed"],
                            entry["lat"],
                            entry["lon"],
                            reg,
                            ac_type,
                            operator
                        ]
                        writer.writerow(row)
                        f.flush()
                        print("Logged aircraft:", row)
                time.sleep(30)

if __name__ == "__main__":
    try:
        listen_and_log()
    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
