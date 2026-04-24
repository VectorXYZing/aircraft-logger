import sqlite3
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = os.path.expanduser('~/aircraft-logger/logs/aircraft.db')

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT,
                hex TEXT,
                callsign TEXT,
                altitude TEXT,
                speed TEXT,
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

def insert_flight(timestamp_utc, hex_code, callsign, altitude, speed, lat, lon, registration, model, operator):
    """Insert a flight record into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO flights (
                timestamp_utc, hex, callsign, altitude, speed, lat, lon, registration, model, operator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp_utc, hex_code, callsign, altitude, speed, lat, lon, registration, model, operator))
        conn.commit()
