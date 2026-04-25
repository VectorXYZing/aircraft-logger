import time
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from airlogger.db import get_db_connection
from airlogger.utils import convert_to_local, LOCAL_TZ
from airlogger.config import HEARTBEAT_FILE, HEALTH_THRESHOLD, VERSION

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# In-memory cache for live flights to reduce DB load
_live_flights_cache = {
    'data': [],
    'last_updated': 0
}
CACHE_TIMEOUT = 10  # seconds

def get_live_flights_data(minutes=15):
    """Fetch and process live flight data with caching."""
    global _live_flights_cache
    now = time.time()
    
    if now - _live_flights_cache['last_updated'] < CACHE_TIMEOUT:
        return _live_flights_cache['data']

    aircraft_data = []
    hex_metadata = {}
    utc_now = datetime.utcnow()
    time_threshold = (utc_now - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM flights WHERE timestamp_utc >= ?"
            cursor.execute(query, (time_threshold,))
            
            for row in cursor.fetchall():
                time_utc = row['timestamp_utc']
                local_time = convert_to_local(time_utc)
                if not local_time: continue
                
                # Sanity check
                try:
                    alt_val = int(row['altitude']) if row['altitude'] else 0
                    speed_val = int(row['speed']) if row['speed'] else 0
                    if alt_val > 60000 or (speed_val == 0 and alt_val == 0):
                        continue
                except (ValueError, TypeError):
                    pass

                row_dict = {
                    "Time Local": local_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "Hex": row['hex'].upper() if row['hex'] else "",
                    "Callsign": row['callsign'] or "",
                    "Altitude": row['altitude'] or "",
                    "Speed": row['speed'] or "",
                    "Track": row['track'] if 'track' in row.keys() and row['track'] else "",
                    "Latitude": row['lat'] or "",
                    "Longitude": row['lon'] or "",
                    "Registration": row['registration'] or "",
                    "Model": row['model'] or "",
                    "Operator": row['operator'] or ""
                }
                
                hex_code = row_dict["Hex"]
                if hex_code:
                    if hex_code not in hex_metadata:
                        hex_metadata[hex_code] = {"Registration": "", "Model": "", "Operator": "", "Callsign": ""}
                    for field in ["Registration", "Model", "Operator", "Callsign"]:
                        val = row_dict[field]
                        if val and len(val) > len(hex_metadata[hex_code][field]):
                            hex_metadata[hex_code][field] = val
                
                aircraft_data.append(row_dict)

        # Apply best metadata
        for row in aircraft_data:
            hex_code = row.get("Hex")
            if hex_code in hex_metadata:
                meta = hex_metadata[hex_code]
                for field in ["Registration", "Model", "Operator", "Callsign"]:
                    if not row.get(field) and meta[field]:
                        row[field] = meta[field]
                        
        aircraft_data.sort(key=lambda x: x.get("Time Local", ""), reverse=True)
        _live_flights_cache = {'data': aircraft_data, 'last_updated': now}
        return aircraft_data
    except Exception as e:
        logger.error(f"Error fetching live flights: {e}")
        return []

@api_bp.route('/api/live_flights')
def api_live_flights():
    minutes = request.args.get('minutes', default=15, type=int)
    return jsonify(get_live_flights_data(minutes))

@api_bp.route('/health')
def health():
    try:
        hb = None
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, 'r') as f:
                hb = json.load(f)
        
        age = time.time() - hb['timestamp'] if hb else None
        healthy = (age is not None and age <= HEALTH_THRESHOLD)
        return jsonify({'healthy': healthy, 'age_seconds': int(age) if age is not None else None}), 200 if healthy else 503
    except Exception as e:
        return jsonify({'healthy': False, 'error': str(e)}), 500
