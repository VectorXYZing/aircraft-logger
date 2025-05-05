import socket
import csv
import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Constants
HOST = '127.0.0.1'
PORT = 30003
LOG_DIR = os.path.expanduser('~/aircraft-logger/logs')
CACHE_TTL = 86400  # 1 day
LOG_THROTTLE_SECONDS = 60  # Limit to 1 log per aircraft per minute

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Metadata cache and logging throttle
metadata_cache = {}
last_logged_times = defaultdict(lambda: 0)

def get_today_log_path():
    filename = f"aircraft_log_{datetime.utcnow().date()}.csv"
    return os.path.join(LOG_DIR, filename)

def ensure_log_file():
    path = get_today_log_path()
    if not os.path.exists(path):
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time UTC', 'Hex', 'Callsign', 'Altitude', 'Speed', 'Latitude', 'Longitude', 'Registration', 'Model', 'Operator'])
    return path

def fetch_metadata(hex_code):
    cached = metadata_cache.get(hex_code)
    if cached and time.time() - cached['timestamp'] < CACHE_TTL:
        return cached['registration'], cached['model'], cached['operator']

    try:
        url = f"https://opensky-network.org/api/metadata/aircraft/icao/{hex_code}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            reg = data.get('registration', '')
            model = data.get('typecode', '')
            operator = data.get('operator', '')
            metadata_cache[hex_code] = {
                'registration': reg,
                'model': model,
                'operator': operator,
                'timestamp': time.time()
            }
            return reg, model, operator
    except Exception as e:
        print(f"Metadata fetch failed for {hex_code}: {e}")

    return '', '', ''

def parse_message(message):
    parts = message.strip().split(',')
    if len(parts) < 22:
        return None

    hex_code = parts[4].strip()
    callsign = parts[10].strip()
    altitude = parts[11].strip()
    speed = parts[12].strip()
    lat = parts[14].strip()
    lon = parts[15].strip()

    return hex_code, callsign, altitude, speed, lat, lon

def log_aircraft(data):
    hex_code = data[0]
    now = time.time()
    if now - last_logged_times[hex_code] < LOG_THROTTLE_SECONDS:
        return
    last_logged_times[hex_code] = now

    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    reg, model, operator = fetch_metadata(hex_code)
    row = [timestamp, hex_code, *data[1:], reg, model, operator]

    with open(ensure_log_file(), 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row)

    print(f"Logged aircraft: {row}")

# Main loop
print("Starting aircraft logger...")
log_path = ensure_log_file()
print(f"Logging to: {log_path}")
print(f"Connecting to {HOST}:{PORT}...")

while True:
    try:
        with socket.create_connection((HOST, PORT)) as sock:
            print("Connected. Listening for aircraft data...")
            file = sock.makefile()
            for line in file:
                parsed = parse_message(line)
                if parsed:
                    log_aircraft(parsed)
    except (ConnectionRefusedError, socket.error) as e:
        print(f"Connection failed: {e}. Retrying in 10 seconds...")
        time.sleep(10)
    except Exception as e:
        print(f"Unexpected error: {e}")
        time.sleep(5)
