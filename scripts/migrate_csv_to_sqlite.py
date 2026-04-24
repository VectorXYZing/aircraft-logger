#!/usr/bin/env python3
import os
import csv
import gzip
import logging
import sys
from datetime import datetime

# Add parent directory to path so we can import airlogger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from airlogger.db import init_db, get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('migrate')

LOG_DIR = os.path.expanduser('~/aircraft-logger/logs')

def migrate_csvs():
    logger.info("Initializing database...")
    init_db()

    # Find all CSV files
    candidates = []
    if os.path.exists(LOG_DIR):
        for f in os.listdir(LOG_DIR):
            if f.startswith('aircraft_log_') and (f.endswith('.csv') or f.endswith('.csv.gz')):
                candidates.append(os.path.join(LOG_DIR, f))
    
    candidates.sort() # sort by date
    
    total_inserted = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        for filepath in candidates:
            logger.info(f"Processing {filepath}...")
            count = 0
            try:
                if filepath.endswith('.gz'):
                    file_handle = gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore')
                else:
                    file_handle = open(filepath, 'r', newline='', encoding='utf-8', errors='ignore')

                with file_handle:
                    reader = csv.DictReader(file_handle)
                    if not reader.fieldnames:
                        continue
                    
                    # Normalize fieldnames
                    field_map = {f.strip().lower(): f for f in reader.fieldnames}
                    
                    def get_row_val(r, key):
                        actual_key = field_map.get(key.lower())
                        return (r.get(actual_key) or "").strip() if actual_key else ""
                    
                    for row in reader:
                        timestamp = get_row_val(row, "Time UTC")
                        if not timestamp:
                            continue
                            
                        hex_code = get_row_val(row, "Hex").upper()
                        callsign = get_row_val(row, "Callsign")
                        altitude = get_row_val(row, "Altitude")
                        speed = get_row_val(row, "Speed")
                        lat = get_row_val(row, "Latitude")
                        lon = get_row_val(row, "Longitude")
                        reg = get_row_val(row, "Registration")
                        model = get_row_val(row, "Model")
                        operator = get_row_val(row, "Operator")
                        
                        cursor.execute('''
                            INSERT INTO flights (
                                timestamp_utc, hex, callsign, altitude, speed, lat, lon, registration, model, operator
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (timestamp, hex_code, callsign, altitude, speed, lat, lon, reg, model, operator))
                        count += 1
                        total_inserted += 1
                        
                conn.commit()
                logger.info(f"  -> Inserted {count} rows from {os.path.basename(filepath)}")
            except Exception as e:
                logger.error(f"Failed to process {filepath}: {e}")
                
    logger.info(f"Migration complete! Total rows inserted: {total_inserted}")

if __name__ == '__main__':
    migrate_csvs()
