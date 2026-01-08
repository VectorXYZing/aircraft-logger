import socket
import csv
import os
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import defaultdict
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys
import gzip
import shutil

# Load environment variables
load_dotenv()

# Constants
HOST = '127.0.0.1'
PORT = 30003
LOG_DIR = os.path.expanduser('~/aircraft-logger/logs')
CACHE_TTL = 86400  # 1 day
LOG_THROTTLE_SECONDS = 60  # Limit to 1 log per aircraft per minute
SOCKET_TIMEOUT = 30  # Socket timeout in seconds
CONNECTION_RETRY_DELAY = 10  # Initial retry delay
MAX_RETRY_DELAY = 300  # Maximum retry delay (5 minutes)
HEARTBEAT_INTERVAL = 300  # Log heartbeat every 5 minutes
CACHE_CLEANUP_INTERVAL = 3600  # Clean cache every hour
MAX_CACHE_SIZE = 10000  # Maximum cache entries
LOG_RETENTION_DAYS = 30  # Keep uncompressed logs for 30 days
THROTTLE_CLEANUP_INTERVAL = 3600  # Clean throttle dicts every hour
MAX_THROTTLE_ENTRIES = 5000  # Maximum throttle entries

# Logging setup
LOGGING_DIR = os.path.expanduser('~/aircraft-logger/logs')
os.makedirs(LOGGING_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGGING_DIR, 'aircraft_logger.log')
logger = logging.getLogger('aircraft_logger')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# Rotating file handler (5MB per file, keep 3 backups)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Global state
import airlogger.metadata as metadata

last_logged_times = defaultdict(lambda: 0)
last_logged_data = {}
running = True
last_heartbeat = time.time()
last_cache_cleanup = time.time()
last_throttle_cleanup = time.time()
last_file_cleanup = time.time()
retry_delay = CONNECTION_RETRY_DELAY
current_log_file = None
current_log_handle = None
current_log_date = None

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global running, current_log_handle
    logger.info("Received shutdown signal, shutting down gracefully...")
    if current_log_handle:
        try:
            current_log_handle.close()
        except:
            pass
    running = False
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_today_log_path():
    filename = f"aircraft_log_{datetime.utcnow().date()}.csv"
    return os.path.join(LOG_DIR, filename)

def ensure_log_file():
    """Ensure log file exists and is open, reopening if date changed"""
    global current_log_file, current_log_handle, current_log_date
    
    today = datetime.utcnow().date()
    path = get_today_log_path()
    
    # If date changed or file not open, close old and open new
    if current_log_date != today or current_log_handle is None:
        if current_log_handle:
            try:
                current_log_handle.close()
            except:
                pass
            current_log_handle = None
        
        if not os.path.exists(path):
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Time UTC', 'Hex', 'Callsign', 'Altitude', 'Speed', 'Latitude', 'Longitude', 'Registration', 'Model', 'Operator'])
                logger.info(f"Created new log file: {path}")
            except Exception as e:
                logger.error(f"Failed to create log file {path}: {e}")
                raise
        
        # Open file in append mode and keep it open
        try:
            current_log_handle = open(path, 'a', newline='', buffering=1)  # Line buffered
            current_log_file = path
            current_log_date = today
            logger.info(f"Opened log file: {path}")
        except Exception as e:
            logger.error(f"Failed to open log file {path}: {e}")
            raise
    
    return current_log_handle

def cleanup_old_logs():
    """Compress old log files and remove very old ones"""
    global last_file_cleanup
    current_time = time.time()
    
    # Run cleanup once per day
    if current_time - last_file_cleanup < 86400:
        return
    
    logger.info("Starting log file cleanup...")
    cutoff_date = datetime.utcnow().date() - timedelta(days=LOG_RETENTION_DAYS)
    files_compressed = 0
    files_deleted = 0
    
    try:
        for filename in os.listdir(LOG_DIR):
            if not filename.startswith('aircraft_log_') or not filename.endswith('.csv'):
                continue
            
            # Skip today's file
            if filename == f"aircraft_log_{datetime.utcnow().date()}.csv":
                continue
            
            filepath = os.path.join(LOG_DIR, filename)
            try:
                # Extract date from filename
                date_str = filename.replace('aircraft_log_', '').replace('.csv', '')
                file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # If older than retention period, delete
                if file_date < cutoff_date:
                    os.remove(filepath)
                    files_deleted += 1
                    logger.info(f"Deleted old log file: {filename}")
                # If not compressed yet, compress it
                elif not filename.endswith('.gz'):
                    compressed_path = filepath + '.gz'
                    if not os.path.exists(compressed_path):
                        with open(filepath, 'rb') as f_in:
                            with gzip.open(compressed_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(filepath)
                        files_compressed += 1
                        logger.info(f"Compressed log file: {filename}")
            except Exception as e:
                logger.error(f"Error processing log file {filename}: {e}")
    
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")
    
    last_file_cleanup = current_time
    logger.info(f"Log cleanup complete: {files_compressed} compressed, {files_deleted} deleted")

def cleanup_throttle_dicts():
    """Clean up throttle dictionaries to prevent memory growth"""
    global last_logged_times, last_logged_data, last_throttle_cleanup
    current_time = time.time()
    
    if current_time - last_throttle_cleanup < THROTTLE_CLEANUP_INTERVAL:
        return
    
    logger.info(f"Cleaning throttle dictionaries (times: {len(last_logged_times)}, data: {len(last_logged_data)})")
    
    # Remove entries older than 24 hours from throttle dicts
    cutoff_time = current_time - 86400
    expired_times = [key for key, value in last_logged_times.items() if value < cutoff_time]
    for key in expired_times:
        del last_logged_times[key]
        if key in last_logged_data:
            del last_logged_data[key]
    
    # If still too large, remove oldest entries
    if len(last_logged_times) > MAX_THROTTLE_ENTRIES:
        sorted_times = sorted(last_logged_times.items(), key=lambda x: x[1])
        entries_to_remove = len(last_logged_times) - MAX_THROTTLE_ENTRIES
        for key, _ in sorted_times[:entries_to_remove]:
            del last_logged_times[key]
            if key in last_logged_data:
                del last_logged_data[key]
        logger.warning(f"Throttle dicts exceeded max size, removed {entries_to_remove} oldest entries")
    
    last_throttle_cleanup = current_time
    logger.info(f"Throttle cleanup complete (times: {len(last_logged_times)}, data: {len(last_logged_data)})")

def cleanup_cache():
    """Remove old cache entries to prevent memory growth"""
    global metadata_cache, last_cache_cleanup
    current_time = time.time()
    
    if current_time - last_cache_cleanup < CACHE_CLEANUP_INTERVAL:
        return
    
    logger.info(f"Cleaning cache (current size: {len(metadata.metadata_cache)})")
    expired_keys = []
    for key, value in list(metadata.metadata_cache.items()):
        if current_time - value['timestamp'] > CACHE_TTL:
            expired_keys.append(key)

    for key in expired_keys:
        del metadata.metadata_cache[key]

    # If cache is still too large, remove oldest entries
    if len(metadata.metadata_cache) > MAX_CACHE_SIZE:
        sorted_cache = sorted(metadata.metadata_cache.items(), key=lambda x: x[1]['timestamp'])
        entries_to_remove = len(metadata.metadata_cache) - MAX_CACHE_SIZE
        for key, _ in sorted_cache[:entries_to_remove]:
            del metadata.metadata_cache[key]
        logger.warning(f"Cache exceeded max size, removed {entries_to_remove} oldest entries")

    last_cache_cleanup = current_time
    logger.info(f"Cache cleanup complete (new size: {len(metadata.metadata_cache)})")

# Metadata fetching now lives in `airlogger.metadata`
from airlogger.metadata import fetch_metadata

# NOTE: metadata_cache and metadata_failures were moved into the metadata module.

def parse_message(message):
    """
    Parse BaseStation port 30003 format messages.
    Format: MSG,type,id,session,hex,session_id,date,time,date,time,callsign,altitude,speed,track,lat,lon,rate,squawk,alert,emergency,spi,ground
    """
    try:
        parts = message.strip().split(',')
        if len(parts) < 11:
            return None
            
        # Message type is parts[1]
        # Callsign is parts[10]
        # Hex code is parts[4]
        
        msg_type = parts[1].strip()
        hex_code = parts[4].strip().upper()
        
        # BaseStation format has up to 22 fields, but we only need up to longevity
        callsign = parts[10].strip() if len(parts) > 10 else ""
        altitude = parts[11].strip() if len(parts) > 11 else ""
        speed = parts[12].strip() if len(parts) > 12 else ""
        lat = parts[14].strip() if len(parts) > 14 else ""
        lon = parts[15].strip() if len(parts) > 15 else ""
        
        # We need at least a hex code
        if not hex_code:
            return None
            
        return hex_code, callsign, altitude, speed, lat, lon
    except Exception as e:
        logger.debug(f"Failed to parse message: {e}")
        return None

def log_aircraft(data):
    hex_code = data[0]
    now = time.time()

    # Only log if enough time has passed
    if now - last_logged_times[hex_code] < LOG_THROTTLE_SECONDS:
        return

    # Fetch metadata first so changes in metadata trigger new log rows
    reg, model, operator, meta_callsign = fetch_metadata(hex_code)

    # Determine callsign: prefer parsed message, fallback to metadata if empty
    parsed_callsign = (data[1] or '').strip()
    
    # We never want commercial names (like JETSTAR) in the callsign column.
    # So we prefer the real flight code from the airwaves, but fallback to metadata
    # if the receiver didn't transmit it in this specific message.
    callsign = parsed_callsign if parsed_callsign else meta_callsign

    altitude = data[2]
    speed = data[3]
    lat = data[4]
    lon = data[5]

    final_data = (callsign, altitude, speed, lat, lon, reg, model, operator)

    # Check if data has changed since last log
    if last_logged_data.get(hex_code) == final_data:
        return

    last_logged_times[hex_code] = now
    last_logged_data[hex_code] = final_data

    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    row = [timestamp, hex_code, callsign, altitude, speed, lat, lon, reg, model, operator]

    try:
        log_handle = ensure_log_file()
        writer = csv.writer(log_handle)
        writer.writerow(row)
        log_handle.flush()  # Ensure data is written
        logger.debug(f"Logged aircraft: {hex_code}")
    except Exception as e:
        logger.error(f"Failed to log aircraft {hex_code}: {e}")

def create_socket():
    """Create a socket connection with proper timeouts"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(SOCKET_TIMEOUT)
    try:
        sock.connect((HOST, PORT))
        sock.settimeout(None)  # Remove timeout after connection
        return sock
    except Exception as e:
        sock.close()
        raise

# Main loop
logger.info("Starting aircraft logger...")
logger.info(f"Socket timeout: {SOCKET_TIMEOUT}s, Heartbeat interval: {HEARTBEAT_INTERVAL}s")
logger.info(f"Log retention: {LOG_RETENTION_DAYS} days, cleanup interval: {CACHE_CLEANUP_INTERVAL}s")
log_path = ensure_log_file()
logger.info(f"Logging to: {log_path}")
logger.info(f"Connecting to {HOST}:{PORT}...")

def write_heartbeat(line_count):
    """Write heartbeat file for dashboard health checks"""
    global last_heartbeat
    current_time = time.time()
    try:
        import json
        import tempfile
        from airlogger.config import HEARTBEAT_FILE

        hb = {
            "timestamp": current_time,
            "iso": datetime.utcfromtimestamp(current_time).isoformat() + "Z",
            "pid": os.getpid(),
            "processed_since_last": line_count,
            "cache_size": len(metadata.metadata_cache),
        }
        dirpath = os.path.dirname(HEARTBEAT_FILE)
        os.makedirs(dirpath, exist_ok=True)
        # atomic write
        with tempfile.NamedTemporaryFile('w', delete=False, dir=dirpath, encoding='utf-8') as tmp:
            json.dump(hb, tmp)
            tmp.flush()
            tmp_name = tmp.name
        os.replace(tmp_name, HEARTBEAT_FILE)
        last_heartbeat = current_time
        return True
    except Exception as e:
        logger.debug(f"Failed to write heartbeat file: {e}")
        return False

while running:
    sock = None
    file_handle = None
    try:
        sock = create_socket()
        logger.info("Connected. Listening for aircraft data...")
        retry_delay = CONNECTION_RETRY_DELAY  # Reset retry delay on successful connection
        
        file_handle = sock.makefile('r', encoding='utf-8', errors='ignore')
        line_count = 0
        
        # Initial heartbeat on connection
        write_heartbeat(0)
        
        for line in file_handle:
            if not running:
                break
                
            # Periodic maintenance
            current_time = time.time()
            
            # Heartbeat logging
            if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
                logger.info(f"Heartbeat: Still running. Processed {line_count} lines since last heartbeat")
                logger.info(f"Memory stats - Cache: {len(metadata.metadata_cache)}, Throttle: {len(last_logged_times)}")
                write_heartbeat(line_count)
                line_count = 0
            
            # Periodic cleanup tasks
            cleanup_cache()
            cleanup_throttle_dicts()
            cleanup_old_logs()
            
            # Process message
            try:
                parsed = parse_message(line)
                if parsed:
                    log_aircraft(parsed)
                    line_count += 1
            except Exception as e:
                logger.error(f"Error processing line: {e}")
                    
    except socket.timeout:
        logger.error(f"Socket timeout after {SOCKET_TIMEOUT}s. Reconnecting...")
    except (ConnectionRefusedError, socket.error, OSError) as e:
        logger.error(f"Connection failed: {e}. Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)  # Exponential backoff
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
    finally:
        # Clean up resources
        if file_handle:
            try:
                file_handle.close()
            except:
                pass
        if sock:
            try:
                sock.close()
            except:
                pass
        if not running:
            break
        time.sleep(5)  # Brief pause before reconnecting

# Cleanup on exit
if current_log_handle:
    try:
        current_log_handle.close()
    except:
        pass

logger.info("Aircraft logger stopped.")
