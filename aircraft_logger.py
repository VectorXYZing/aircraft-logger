import time
import socket
import logging
import signal
import sys
import json
from datetime import datetime
from airlogger.core import (
    create_socket, parse_message, log_aircraft, 
    cleanup_old_logs, ensure_log_file, current_log_handle
)
from airlogger.db import init_db
from airlogger.config import (
    HEARTBEAT_INTERVAL, HEARTBEAT_FILE, 
    CONNECTION_RETRY_DELAY, MAX_RETRY_DELAY, 
    SOCKET_TIMEOUT
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('aircraft_logger')

running = True
last_heartbeat = 0

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received. Exiting...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def write_heartbeat(line_count):
    try:
        with open(HEARTBEAT_FILE, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'iso': datetime.now().isoformat(),
                'lines_processed': line_count
            }, f)
    except Exception as e:
        logger.debug(f"Heartbeat failed: {e}")

def main():
    global running, last_heartbeat
    logger.info("Starting Aircraft Logger Service...")
    
    try:
        init_db()
    except Exception as e:
        logger.error(f"DB Init failed: {e}")
        return

    retry_delay = CONNECTION_RETRY_DELAY
    
    while running:
        sock = None
        file_handle = None
        try:
            sock = create_socket()
            logger.info(f"Connected to dump1090. Listening...")
            retry_delay = CONNECTION_RETRY_DELAY
            
            file_handle = sock.makefile('r', encoding='utf-8', errors='ignore')
            line_count = 0
            
            for line in file_handle:
                if not running: break
                
                # Maintenance
                now = time.time()
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    logger.info(f"Heartbeat: Processed {line_count} lines. Still healthy.")
                    write_heartbeat(line_count)
                    cleanup_old_logs()
                    last_heartbeat = now
                    line_count = 0
                
                # Process
                parsed = parse_message(line)
                if parsed:
                    log_aircraft(parsed)
                    line_count += 1
                    
        except (socket.timeout, ConnectionRefusedError, socket.error) as e:
            logger.error(f"Connection error: {e}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            time.sleep(retry_delay)
        finally:
            if file_handle: file_handle.close()
            if sock: sock.close()
            time.sleep(1)

    logger.info("Logger service stopped.")

if __name__ == "__main__":
    main()
