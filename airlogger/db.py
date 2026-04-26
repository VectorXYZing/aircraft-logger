import sqlite3
import os
import logging
import time
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = os.path.expanduser('~/aircraft-logger/logs/aircraft.db')

# In-memory shared registry for live dashboard performance
_live_registry = {}
_last_registry_cleanup = 0

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Auto-migrate: add 'track' column if it's missing from an older database
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='flights'")
        if cursor.fetchone()[0] == 1:
            cursor.execute("PRAGMA table_info(flights)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'track' not in columns:
                logger.info("Auto-migrating database: adding 'track' column...")
                cursor.execute("ALTER TABLE flights ADD COLUMN track TEXT")
                conn.commit()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT,
                hex TEXT,
                callsign TEXT,
                altitude TEXT,
                speed TEXT,
                track TEXT,
                lat TEXT,
                lon TEXT,
                registration TEXT,
                model TEXT,
                operator TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp_utc ON flights(timestamp_utc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hex ON flights(hex)')
        conn.commit()

@contextmanager
def get_db_connection():
    """Provide a transactional scope around a series of operations."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_live_registry(minutes=15):
    """Return the current live aircraft registry, cleaned of old entries."""
    global _live_registry, _last_registry_cleanup
    
    now = time.time()
    # Periodic cleanup every minute
    if now - _last_registry_cleanup > 60:
        threshold = datetime.utcnow() - timedelta(minutes=minutes)
        new_registry = {}
        for h, f in _live_registry.items():
            try:
                # Handle both formats (with/without microseconds)
                fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in f['time_utc'] else '%Y-%m-%d %H:%M:%S'
                if datetime.strptime(f['time_utc'], fmt) > threshold:
                    new_registry[h] = f
            except:
                continue
        _live_registry = new_registry
        _last_registry_cleanup = now
        
    return _live_registry

def insert_flight(timestamp_utc, hex_code, callsign, altitude, speed, track, lat, lon, registration, model, operator):
    """Insert a flight record into the database and update live registry."""
    global _live_registry
    
    # Update in-memory registry for the live dashboard
    _live_registry[hex_code] = {
        'hex': hex_code,
        'callsign': callsign,
        'alt': altitude,
        'speed': speed,
        'track': track,
        'lat': lat,
        'lon': lon,
        'reg': registration,
        'model': model,
        'operator': operator,
        'time_utc': timestamp_utc
    }
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO flights (
                timestamp_utc, hex, callsign, altitude, speed, track, lat, lon, registration, model, operator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp_utc, hex_code, callsign, altitude, speed, track, lat, lon, registration, model, operator))
        conn.commit()
