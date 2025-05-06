from flask import Flask, render_template, request
import os
import csv
from collections import Counter
from datetime import datetime, date
import pytz

app = Flask(__name__)

LOG_DIR = "/home/pi/aircraft-logger/logs"
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

    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    for filename in os.listdir(LOG_DIR):
        if not filename.endswith(".csv"):
            continue
        filepath = os.path.join(LOG_DIR, filename)
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
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

    aircraft_data.sort(key=lambda x: x.get("Time Local", ""), reverse=True)
    return aircraft_data, len(aircraft_data), len(unique_hexes), operator_counts.most_common(5), model_counts.most_common(5)

@app.route("/")
def index():
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
