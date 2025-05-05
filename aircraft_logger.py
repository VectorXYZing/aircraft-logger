#!/usr/bin/env python3
import socket
import csv
import os
import time
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_BASE_URL = "https://opensky-network.org/api/metadata/"
OUTPUT_DIR = os.path.expanduser("~/aircraft-logger/logs")
CACHE = {}

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get today's log file path
def get_log_file_path():
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, f"aircraft_log_{date_str}.csv")

# Lookup aircraft metadata with basic caching
def lookup_aircraft_metadata(hex_code):
    if hex_code in CACHE:
        return CACHE[hex_code]

    try:
        response = requests.get(f"https://opensky-network.org/api/metadata/aircraft/{hex_code}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            registration = data.get("registration", "")
            model = data.get("model", "")
            operator = data.get("owner", "")  # OpenSky sometimes uses 'owner'
            CACHE[hex_code] = (registration, model, operator)
            return registration, model, operator
    except Exception as e:
        print(f"Metadata lookup failed for {hex_code}: {e}")

    return "", "", ""

# Parse SBS message line into a dictionary
def parse_sbs1_message(line):
    fields = line.strip().split(',')
    if len(fields) < 22:
        return None

    return {
        'hex': fields[4].strip(),
        'callsign': fields[10].strip(),
        'altitude': fields[11].strip(),
        'speed': fields[12].strip(),
        'lat': fields[14].strip(),
        'lon': fields[15].strip(),
        'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }

# Write one row to the log
def log_aircraft(row):
    file_path = get_log_file_path()
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Time UTC", "Hex", "Callsign", "Altitude", "Speed", "Latitude", "Longitude", "Registration", "Model", "Operator"])
        writer.writerow(row)

# Consolidate data per aircraft and flush after timeout
aircraft_data = {}
TIMEOUT_SECONDS = 120

print("Starting aircraft logger...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 30003))
print("Connected. Listening for aircraft data...")

try:
    while True:
        line = sock.recv(4096).decode(errors='ignore')
        if not line:
            continue

        for raw_line in line.strip().split('\n'):
            msg = parse_sbs1_message(raw_line)
            if not msg or not msg['hex']:
                continue

            hex_code = msg['hex']
            now = time.time()

            entry = aircraft_data.get(hex_code, {
                'timestamp': now,
                'callsign': '',
                'altitude': '',
                'speed': '',
                'lat': '',
                'lon': '',
                'registration': '',
                'model': '',
                'operator': ''
            })

            entry['timestamp'] = now
            entry['callsign'] = msg['callsign'] or entry['callsign']
            entry['altitude'] = msg['altitude'] or entry['altitude']
            entry['speed'] = msg['speed'] or entry['speed']
            entry['lat'] = msg['lat'] or entry['lat']
            entry['lon'] = msg['lon'] or entry['lon']

            if not entry['registration']:
                registration, model, operator = lookup_aircraft_metadata(hex_code)
                entry['registration'] = registration
                entry['model'] = model
                entry['operator'] = operator

            aircraft_data[hex_code] = entry

        # Flush stale entries
        expired = [hex_code for hex_code, v in aircraft_data.items() if time.time() - v['timestamp'] > TIMEOUT_SECONDS]
        for hex_code in expired:
            v = aircraft_data.pop(hex_code)
            row = [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), hex_code, v['callsign'], v['altitude'], v['speed'], v['lat'], v['lon'], v['registration'], v['model'], v['operator']]
            log_aircraft(row)
            print(f"Logged aircraft: {row}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping logger. Flushing remaining aircraft...")
    for hex_code, v in aircraft_data.items():
        row = [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), hex_code, v['callsign'], v['altitude'], v['speed'], v['lat'], v['lon'], v['registration'], v['model'], v['operator']]
        log_aircraft(row)
        print(f"Flushed stale aircraft: {row}")
