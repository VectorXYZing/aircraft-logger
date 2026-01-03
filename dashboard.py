from flask import Flask, render_template, request
import os
import csv
import gzip
from collections import Counter
from datetime import datetime, date
import pytz
import logging
import shutil
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Logging setup
# Allow overriding the logs directory via environment
LOGGING_DIR = os.environ.get('AIRLOGGER_LOG_DIR', os.path.expanduser('~/aircraft-logger/logs'))
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

LOG_DIR = os.environ.get('AIRLOGGER_LOG_DIR', os.path.expanduser('~/aircraft-logger/logs'))
LOCAL_TZ = pytz.timezone("Australia/Melbourne")

def convert_to_local(utc_str):
    try:
        utc_time = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
        return utc_time.astimezone(LOCAL_TZ)
    except:
        return None

def load_and_filter_csv(target_date_str):
    aircraft_data = []
    unique_hexes = set()
    operator_counts = Counter()
    model_counts = Counter()

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except Exception as e:
        logger.error(f"Invalid date format: {target_date_str} - {e}")
        return [], 0, 0, [], []

    try:
        for filename in os.listdir(LOG_DIR):
            # Check for both .csv and .csv.gz files
            if not (filename.endswith(".csv") or filename.endswith(".csv.gz")):
                continue
            
            filepath = os.path.join(LOG_DIR, filename)
            try:
                # Open file (compressed or uncompressed)
                if filename.endswith(".gz"):
                    file_handle = gzip.open(filepath, 'rt', encoding='utf-8')
                else:
                    file_handle = open(filepath, 'r', newline='', encoding='utf-8')
                
                with file_handle:
                    reader = csv.DictReader(file_handle)
                    for row in reader:
                        local_time = convert_to_local(row["Time UTC"])
                        if not local_time:
                            continue
                        if local_time.date() != target_date:
                            continue
                        row["Time Local"] = local_time.strftime("%Y-%m-%d %H:%M:%S")
                        aircraft_data.append(row)
                        unique_hexes.add(row["Hex"])
                        operator = row.get("Operator", "")
                        if operator:
                            operator_counts[operator] += 1
                        model = row.get("Model", "")
                        if model:
                            model_counts[model] += 1
            except Exception as e:
                logger.error(f"Failed to read file {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error loading CSV files: {e}")
        return [], 0, 0, [], []

    aircraft_data.sort(key=lambda x: x.get("Time Local", ""), reverse=True)
    return aircraft_data, len(aircraft_data), len(unique_hexes), operator_counts.most_common(5), model_counts.most_common(5)


def tail_file(path, lines=100):
    """Return the last `lines` lines from a text file (handles missing files)."""
    try:
        if path.endswith('.gz'):
            with gzip.open(path, 'rt', encoding='utf-8', errors='ignore') as f:
                all_lines = f.read().splitlines()
        else:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.read().splitlines()
        return all_lines[-lines:]
    except Exception:
        return []


def get_recent_errors(log_path, lines=200):
    entries = tail_file(log_path, lines)
    errors = [l for l in entries if 'ERROR' in l or 'Traceback' in l or 'Exception' in l]
    return errors[-50:]


@app.route("/status")
def status():
    try:
        today_local = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        data, total, unique, top_operators, top_models = load_and_filter_csv(today_local)

        # Last seen aircraft (most recent)
        last_entry = data[0] if data else None

        # Recent errors from logger files
        aircraft_logger_path = os.path.join(LOGGING_DIR, 'aircraft_logger.log')
        dashboard_log_path = os.path.join(LOGGING_DIR, 'dashboard.log')
        errors_aircraft = get_recent_errors(aircraft_logger_path)
        errors_dashboard = get_recent_errors(dashboard_log_path)

        # Log files stats
        files = []
        try:
            for fname in os.listdir(LOG_DIR):
                if fname.startswith('aircraft_log_') and (fname.endswith('.csv') or fname.endswith('.csv.gz')):
                    path = os.path.join(LOG_DIR, fname)
                    try:
                        size = os.path.getsize(path)
                    except Exception:
                        size = 0
                    files.append({'name': fname, 'size': size})
        except Exception as e:
            logger.error(f"Failed to list log dir {LOG_DIR}: {e}")

        # Disk usage for log directory
        try:
            du = shutil.disk_usage(LOG_DIR)
            disk = {'total': du.total, 'used': du.used, 'free': du.free}
        except Exception:
            disk = None

        status_info = {
            'api': 'ok',
            'total_records_today': total,
            'unique_today': unique,
            'last_entry': last_entry,
            'top_operators': top_operators,
            'top_models': top_models,
            'files': files,
            'disk': disk,
            'errors_aircraft': errors_aircraft,
            'errors_dashboard': errors_dashboard,
        }

        return render_template('status.html', status=status_info)
    except Exception as e:
        logger.error(f"Error building status page: {e}")
        return "An error occurred while building status page.", 500

@app.route("/")
def index():
    try:
        date_str = request.args.get("date")
        today_local = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        selected_date = date_str if date_str else today_local

        data, total, unique, top_operators, top_models = load_and_filter_csv(selected_date)

        summary = {
            "total_aircraft": total,
            "unique_aircraft": unique,
            "top_operators": top_operators,
            "top_models": top_models
        }

        return render_template("index.html", data=data, summary=summary, selected_date=selected_date, max_date=today_local)
    except Exception as e:
        logger.error(f"Error in dashboard route: {e}")
        return "An error occurred while loading the dashboard.", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
