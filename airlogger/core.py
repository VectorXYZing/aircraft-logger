import os
import csv
import time
import socket
import logging
import gzip
import shutil
from datetime import datetime, timedelta
from collections import defaultdict
from airlogger.db import init_db, insert_flight
from airlogger.metadata import fetch_metadata
from airlogger.config import (
    LOG_DIR, LOG_THROTTLE_SECONDS, SOCKET_TIMEOUT, 
    CONNECTION_RETRY_DELAY, MAX_RETRY_DELAY, HEARTBEAT_INTERVAL,
    HEARTBEAT_FILE, DUMP1090_HOST, DUMP1090_PORT
)

logger = logging.getLogger(__name__)

# Global state for the logger
last_logged_times = defaultdict(lambda: 0)
last_logged_data = {}
current_log_handle = None
current_log_date = None

def get_today_log_path():
    filename = f"aircraft_log_{datetime.utcnow().date()}.csv"
    return os.path.join(LOG_DIR, filename)

def ensure_log_file():
    """Ensure log file exists and is open, reopening if date changed"""
    global current_log_handle, current_log_date
    
    today = datetime.utcnow().date()
    path = get_today_log_path()
    
    if current_log_date != today or current_log_handle is None:
        if current_log_handle:
            try:
                current_log_handle.close()
            except:
                pass
        
        os.makedirs(LOG_DIR, exist_ok=True)
        if not os.path.exists(path):
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Time UTC', 'Hex', 'Callsign', 'Altitude', 'Speed', 'Latitude', 'Longitude', 'Registration', 'Model', 'Operator'])
        
        current_log_handle = open(path, 'a', newline='', buffering=1)
        current_log_date = today
    
    return current_log_handle

def parse_message(message):
    """Parse BaseStation port 30003 format messages."""
    try:
        parts = message.strip().split(',')
        if len(parts) < 11:
            return None
            
        hex_code = parts[4].strip().upper()
        if not hex_code:
            return None

        callsign = parts[10].strip() if len(parts) > 10 else ""
        altitude = parts[11].strip() if len(parts) > 11 else ""
        speed = parts[12].strip() if len(parts) > 12 else ""
        track = parts[13].strip() if len(parts) > 13 else ""
        lat = parts[14].strip() if len(parts) > 14 else ""
        lon = parts[15].strip() if len(parts) > 15 else ""
        
        return hex_code, callsign, altitude, speed, track, lat, lon
    except Exception as e:
        logger.debug(f"Failed to parse message: {e}")
        return None

def log_aircraft(data):
    """Process and log aircraft data to SQLite and CSV."""
    hex_code = data[0]
    now = time.time()

    if now - last_logged_times[hex_code] < LOG_THROTTLE_SECONDS:
        return

    reg, model, operator, meta_callsign = fetch_metadata(hex_code)
    parsed_callsign = (data[1] or '').strip()
    callsign = parsed_callsign if parsed_callsign else meta_callsign

    altitude, speed, track, lat, lon = data[2], data[3], data[4], data[5], data[6]
    final_data = (callsign, altitude, speed, track, lat, lon, reg, model, operator)

    if last_logged_data.get(hex_code) == final_data:
        return

    last_logged_times[hex_code] = now
    last_logged_data[hex_code] = final_data

    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        insert_flight(timestamp, hex_code, callsign, altitude, speed, track, lat, lon, reg, model, operator)
        
        log_handle = ensure_log_file()
        writer = csv.writer(log_handle)
        writer.writerow([timestamp, hex_code, callsign, altitude, speed, lat, lon, reg, model, operator])
        logger.debug(f"Logged aircraft: {hex_code}")
    except Exception as e:
        logger.error(f"Failed to log aircraft {hex_code}: {e}")

def cleanup_old_logs(retention_days=30):
    """Compress old log files and remove very old ones."""
    logger.info("Starting log file cleanup...")
    cutoff_date = datetime.utcnow().date() - timedelta(days=retention_days)
    
    for filename in os.listdir(LOG_DIR):
        if not filename.startswith('aircraft_log_') or not filename.endswith('.csv'):
            continue
        if filename == f"aircraft_log_{datetime.utcnow().date()}.csv":
            continue
            
        filepath = os.path.join(LOG_DIR, filename)
        if not os.path.exists(filepath):
            continue
            
        try:
            date_str = filename.replace('aircraft_log_', '').replace('.csv', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if file_date < cutoff_date:
                os.remove(filepath)
                logger.info(f"Deleted old log: {filename}")
            else:
                # Compress if not already compressed (it ends in .csv so it's not .gz)
                compressed_path = filepath + '.gz'
                if not os.path.exists(compressed_path):
                    with open(filepath, 'rb') as f_in, gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    os.remove(filepath)
                    logger.info(f"Compressed log: {filename}")
        except Exception as e:
            logger.error(f"Error processing log file {filename}: {e}")

def create_socket():
    """Create a socket connection to dump1090."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(SOCKET_TIMEOUT)
    try:
        sock.connect((DUMP1090_HOST, DUMP1090_PORT))
        sock.settimeout(None)
        return sock
    except Exception as e:
        sock.close()
        raise
