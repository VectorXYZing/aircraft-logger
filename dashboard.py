from flask import Flask, render_template, request
import os
import csv
import gzip
from collections import Counter
from datetime import datetime, date
import pytz
import logging
from logging.handlers import RotatingFileHandler
import time

app = Flask(__name__)
VERSION = "1.2.1"

# Logging setup
LOGGING_DIR = os.path.expanduser('~/aircraft-logger/logs')
os.makedirs(LOGGING_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGGING_DIR, 'dashboard.log')
logger = logging.getLogger('dashboard')
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

from airlogger.config import LOG_DIR as LOG_DIR_CONFIG, TIMEZONE as TIMEZONE_CONFIG

# Use configurable log dir (default: ~/aircraft-logger/logs)
LOG_DIR = os.path.expanduser(LOG_DIR_CONFIG)

# Timezone handling: prefer configured timezone, fall back to system local zone
try:
    from zoneinfo import ZoneInfo
    HAS_ZONEINFO = True
except Exception:
    ZoneInfo = None
    HAS_ZONEINFO = False

if TIMEZONE_CONFIG:
    try:
        if HAS_ZONEINFO:
            LOCAL_TZ = ZoneInfo(TIMEZONE_CONFIG)
        else:
            LOCAL_TZ = pytz.timezone(TIMEZONE_CONFIG)
    except Exception:
        LOCAL_TZ = None
else:
    # No explicit timezone configured; use system local timezone
    try:
        LOCAL_TZ = datetime.now().astimezone().tzinfo
    except Exception:
        LOCAL_TZ = None


def convert_to_local(utc_str):
    """Convert a UTC timestamp string to local timezone-aware datetime.

    Returns None on parse/convert errors.
    """
    try:
        utc_time = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC") if HAS_ZONEINFO else pytz.utc)
        if LOCAL_TZ:
            return utc_time.astimezone(LOCAL_TZ)
        return utc_time
    except ValueError:
        return None
    except Exception:
        return None

def load_and_filter_csv(target_date_str):
    aircraft_data = []
    # Use a dictionary to keep track of the best metadata seen for each hex
    hex_metadata = {}

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except Exception as e:
        logger.error(f"Invalid date format: {target_date_str} - {e}")
        return [], 0, 0, [], []

    # Only load files for the target date (faster than scanning everything)
    candidates = [
        os.path.join(LOG_DIR, f"aircraft_log_{target_date}.csv"),
        os.path.join(LOG_DIR, f"aircraft_log_{target_date}.csv.gz"),
    ]

    try:
        for filepath in candidates:
            if not os.path.exists(filepath):
                continue
            try:
                if filepath.endswith('.gz'):
                    file_handle = gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore')
                else:
                    file_handle = open(filepath, 'r', newline='', encoding='utf-8', errors='ignore')

                with file_handle:
                    reader = csv.DictReader(file_handle)
                    if not reader.fieldnames:
                        continue
                        
                    # Normalize fieldnames (handle extra spaces or case differences)
                    field_map = {f.strip().lower(): f for f in reader.fieldnames}
                    
                    def get_row_val(r, key):
                        actual_key = field_map.get(key.lower())
                        return (r.get(actual_key) or "").strip() if actual_key else ""

                    for row in reader:
                        time_utc = get_row_val(row, "Time UTC")
                        local_time = convert_to_local(time_utc)
                        if not local_time or local_time.date() != target_date:
                            continue
                        
                        row["Time Local"] = local_time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        hex_code = get_row_val(row, "Hex").upper()
                        row["Hex"] = hex_code
                        
                        if hex_code:
                            if hex_code not in hex_metadata:
                                hex_metadata[hex_code] = {"Registration": "", "Model": "", "Operator": ""}
                            
                            for field in ["Registration", "Model", "Operator"]:
                                val = get_row_val(row, field)
                                if val:
                                    # Update if we have better data
                                    if not hex_metadata[hex_code][field] or len(val) > len(hex_metadata[hex_code][field]):
                                        hex_metadata[hex_code][field] = val
                                # Keep the row data consistent with normalized fields
                                row[field] = val
                        
                        aircraft_data.append(row)
            except Exception as e:
                logger.error(f"Failed to read file {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error loading CSV files: {e}")
        return [], 0, 0, [], []

    # Second pass: Apply best-known metadata to every row
    for row in aircraft_data:
        hex_code = row.get("Hex")
        if hex_code and hex_code in hex_metadata:
            meta = hex_metadata[hex_code]
            for field in ["Registration", "Model", "Operator"]:
                if not row.get(field) and meta[field]:
                    row[field] = meta[field]
        
    # Third pass: Collect statistics (one count per unique aircraft)
    unique_hexes_this_day = {row.get("Hex") for row in aircraft_data if row.get("Hex")}
    operator_counts = Counter()
    model_counts = Counter()

    for hex_code in unique_hexes_this_day:
        meta = hex_metadata.get(hex_code, {})
        op = meta.get("Operator", "").strip()
        if op:
            operator_counts[op] += 1
        
        mdl = meta.get("Model", "").strip()
        if mdl:
            model_counts[mdl] += 1

    unique_count = len(unique_hexes_this_day)
    logger.info(f"Summary for {target_date_str}: {len(aircraft_data)} rows, {unique_count} unique aircraft. Metadata found for {len(hex_metadata)} hexes.")

    aircraft_data.sort(key=lambda x: x.get("Time Local", ""), reverse=True)
    return aircraft_data, len(aircraft_data), unique_count, operator_counts.most_common(5), model_counts.most_common(5)

@app.route("/")
def index():
    try:
        date_str = request.args.get("date")
        # Ensure we have a valid base date for today
        try:
            now = datetime.now(LOCAL_TZ)
        except Exception:
            now = datetime.now()
            
        today_local = now.strftime("%Y-%m-%d")
        selected_date = date_str if date_str else today_local

        data, total, unique, top_operators, top_models = load_and_filter_csv(selected_date)

        summary = {
            "total_aircraft": total,
            "unique_aircraft": unique,
            "top_operators": top_operators,
            "top_models": top_models
        }

        # Check health status
        health_status = {"healthy": False, "age_seconds": None}
        try:
            from airlogger.config import HEARTBEAT_FILE, HEALTH_THRESHOLD
            import json
            hb = None
            if os.path.exists(HEARTBEAT_FILE):
                try:
                    with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as hf:
                        hb = json.load(hf)
                except Exception:
                    hb = None

            if hb and isinstance(hb, dict) and 'timestamp' in hb:
                age = time.time() - hb['timestamp']
                healthy = age <= HEALTH_THRESHOLD
                health_status = {
                    "healthy": healthy,
                    "age_seconds": int(age),
                    "last_seen_iso": hb.get('iso')
                }
        except Exception as e:
            logger.error(f"Error checking health status: {e}")

        return render_template("index.html", data=data, summary=summary, selected_date=selected_date, max_date=today_local, health_status=health_status, version=VERSION)
    except Exception as e:
        logger.error(f"CRITICAL Error in dashboard route: {e}", exc_info=True)
        return f"<h1>Dashboard Error</h1><p>{str(e)}</p><p>Check dashboard.log for details.</p>", 500


@app.route('/status')
def status():
    """Return a compact JSON status with totals and the most recent record."""
    try:
        today_local = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        data, total, unique, top_operators, top_models = load_and_filter_csv(today_local)
        last_record = data[0] if data else {}
        resp = {
            'date': today_local,
            'total_records': total,
            'unique_aircraft': unique,
            'last_record': {
                'time_local': last_record.get('Time Local') if last_record else None,
                'hex': last_record.get('Hex') if last_record else None,
                'callsign': last_record.get('Callsign') if last_record else None,
                'registration': last_record.get('Registration') if last_record else None,
                'model': last_record.get('Model') if last_record else None,
                'operator': last_record.get('Operator') if last_record else None,
            }
        }

        # Attach heartbeat / health information
        try:
            import json
            from airlogger.config import HEARTBEAT_FILE, HEALTH_THRESHOLD

            hb = None
            if os.path.exists(HEARTBEAT_FILE):
                try:
                    with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as hf:
                        hb = json.load(hf)
                except Exception:
                    hb = None

            if hb and isinstance(hb, dict) and 'timestamp' in hb:
                age = time.time() - hb['timestamp']
                healthy = age <= HEALTH_THRESHOLD
                resp['heartbeat'] = {
                    'last_seen_iso': hb.get('iso'),
                    'age_seconds': int(age),
                    'healthy': healthy,
                    'pid': hb.get('pid'),
                    'cache_size': hb.get('cache_size')
                }
            else:
                resp['heartbeat'] = {'last_seen_iso': None, 'age_seconds': None, 'healthy': False}
        except Exception:
            resp['heartbeat'] = {'last_seen_iso': None, 'age_seconds': None, 'healthy': False}

        # Use Flask json response helper
        from flask import jsonify
        return jsonify(resp)
    except Exception as e:
        logger.error(f"Error in status route: {e}")
        return {"error": "failed to generate status"}, 500


@app.route('/health')
def health():
    """Simple health endpoint that returns 200 if the logger heartbeat is recent, else 503."""
    try:
        from airlogger.config import HEARTBEAT_FILE, HEALTH_THRESHOLD
        import json
        hb = None
        if os.path.exists(HEARTBEAT_FILE):
            try:
                with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as hf:
                    hb = json.load(hf)
            except Exception:
                hb = None

        healthy = False
        age = None
        if hb and isinstance(hb, dict) and 'timestamp' in hb:
            age = time.time() - hb['timestamp']
            healthy = age <= HEALTH_THRESHOLD

        from flask import jsonify
        if healthy:
            return jsonify({'healthy': True, 'age_seconds': int(age)}), 200
        else:
            return jsonify({'healthy': False, 'age_seconds': int(age) if age is not None else None}), 503
    except Exception as e:
        logger.error(f"Error in health route: {e}")
        return {"healthy": False}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
