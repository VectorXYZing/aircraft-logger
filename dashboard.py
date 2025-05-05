from flask import Flask, render_template
import os
import csv
from collections import defaultdict, Counter
from datetime import datetime

app = Flask(__name__)

LOG_DIR = "/home/pi/aircraft-logger/logs"

def parse_csv(file_path):
    aircraft_data = []
    unique_hexes = set()
    operator_counts = Counter()

    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            hex_code = row["Hex"]
            aircraft_data.append(row)
            unique_hexes.add(hex_code)
            operator = row.get("Operator", "")
            if operator:
                operator_counts[operator] += 1

    return aircraft_data, len(aircraft_data), len(unique_hexes), operator_counts.most_common(5)

@app.route("/")
def index():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"aircraft_log_{today}.csv")
    
    if not os.path.exists(log_file):
        return render_template("index.html", data=[], summary={})

    data, total, unique, top_operators = parse_csv(log_file)

    summary = {
        "total_aircraft": total,
        "unique_aircraft": unique,
        "top_operators": top_operators
    }

    return render_template("index.html", data=data, summary=summary)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
