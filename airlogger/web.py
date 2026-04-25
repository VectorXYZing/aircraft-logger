import logging
from collections import Counter
from datetime import datetime, time as dt_time, timedelta
from flask import Blueprint, render_template, request
from airlogger.db import get_db_connection
from airlogger.utils import convert_to_local, LOCAL_TZ
from airlogger.config import VERSION, HEALTH_THRESHOLD, HEARTBEAT_FILE
import os
import json
import time

web_bp = Blueprint('web', __name__)
logger = logging.getLogger(__name__)

def load_historical_data(target_date_str):
    """Load and process historical data for a specific date."""
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except Exception:
        return [], 0, 0, [], []

    # Simple logic for determining UTC overlap
    # In a real app we'd query precisely, but this works for local/UTC edge cases
    utc_dates = [target_date - timedelta(days=1), target_date, target_date + timedelta(days=1)]
    utc_dates_str = [str(d) for d in utc_dates]
    placeholders = ','.join('?' for _ in utc_dates_str)

    aircraft_data = []
    hex_metadata = {}

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM flights WHERE date(timestamp_utc) IN ({placeholders})"
            cursor.execute(query, utc_dates_str)
            
            for row in cursor.fetchall():
                local_time = convert_to_local(row['timestamp_utc'])
                if not local_time or local_time.date() != target_date:
                    continue
                
                # Sanity
                try:
                    alt = int(row['altitude']) if row['altitude'] else 0
                    speed = int(row['speed']) if row['speed'] else 0
                    if alt > 60000 or (speed == 0 and alt == 0): continue
                except: pass

                row_dict = {
                    "Time Local": local_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "Hex": row['hex'].upper(),
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

        # Apply metadata & stats
        operator_counts = Counter()
        model_counts = Counter()
        unique_hexes = set()

        for row in aircraft_data:
            hex_code = row["Hex"]
            unique_hexes.add(hex_code)
            meta = hex_metadata.get(hex_code, {})
            for field in ["Registration", "Model", "Operator", "Callsign"]:
                if not row.get(field) and meta.get(field):
                    row[field] = meta[field]
        
        for hex_code in unique_hexes:
            meta = hex_metadata.get(hex_code, {})
            if meta.get("Operator"): operator_counts[meta["Operator"]] += 1
            if meta.get("Model"): model_counts[meta["Model"]] += 1

        aircraft_data.sort(key=lambda x: x.get("Time Local", ""), reverse=True)
        return aircraft_data, len(aircraft_data), len(unique_hexes), operator_counts.most_common(5), model_counts.most_common(5)
    except Exception as e:
        logger.error(f"Error loading historical data: {e}")
        return [], 0, 0, [], []

@web_bp.route("/")
def index():
    date_str = request.args.get("date")
    now = datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now()
    today_local = now.strftime("%Y-%m-%d")
    selected_date = date_str if date_str else today_local

    data, total, unique, top_operators, top_models = load_historical_data(selected_date)
    
    summary = {
        "total_aircraft": total,
        "unique_aircraft": unique,
        "top_operators": top_operators,
        "top_models": top_models
    }

    # Health Check
    health_status = {"healthy": False, "age_seconds": None}
    if os.path.exists(HEARTBEAT_FILE):
        try:
            with open(HEARTBEAT_FILE, 'r') as f:
                hb = json.load(f)
            age = time.time() - hb['timestamp']
            health_status = {"healthy": age <= HEALTH_THRESHOLD, "age_seconds": int(age)}
        except: pass

    return render_template("index.html", data=data, summary=summary, selected_date=selected_date, max_date=today_local, health_status=health_status, version=VERSION)
