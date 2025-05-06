# ✈️ Aircraft Logger

A lightweight aircraft logger and dashboard for Raspberry Pi that:

- Captures ADS-B data from FR24/PiAware feeds  
- Enriches it with aircraft metadata using OpenSky (no API key needed)  
- Logs to daily CSV files  
- Emails daily logs automatically  
- Hosts a stylish web dashboard to explore sightings  

## 🔧 Features

- ADS-B message capture from `30003` port  
- Metadata enrichment from OpenSky (no API key required)  
- Caching to reduce lookups  
- Logs to `~/aircraft-logger/logs/aircraft_log_YYYY-MM-DD.csv`  
- Prevents duplicate log entries unless aircraft state has changed  
- Sends daily log email at 7pm (customisable via cron)  
- Web dashboard with:  
  - Column sorting  
  - Date picker (based on local time)  
  - Summary metrics (unique aircraft, top operators, total messages)  
  - Styled UI with pastel theme and icons  
- Setup via single script (`setup.sh`)  

## 🖥️ Ideal for:

- Hobbyists running aircraft feeders (PiAware/FR24)  
- People curious about what's flying overhead  
- Teaching basic data logging, APIs, dashboards  

## 📁 Project Structure

```
~/aircraft-logger/
├── aircraft_logger.py       # Main logger script
├── send_log_email.py        # Sends daily email summary
├── dashboard.py             # Flask dashboard web app
├── templates/
│   └── index.html           # HTML template for dashboard
├── static/
│   ├── style.css            # Dashboard CSS styling
│   └── script.js            # Dashboard interactivity (optional)
├── logs/                    # Daily aircraft logs stored here
├── .env                     # Local config (ignored by git)
├── .gitignore
├── requirements.txt
└── setup.sh                 # One-step setup script
```

## 🧪 Prerequisites

- Raspberry Pi or Linux system  
- ADS-B data stream (via FR24, PiAware, or similar)  
- Python 3.9+ (venv supported)  

## 📦 Installation (Novice-Friendly)

1. **Clone the repo** (on your Pi or system with FR24/PiAware):

```bash
git clone https://github.com/VectorXYZing/aircraft-logger.git
cd aircraft-logger
```

2. **Run setup script**

```bash
chmod +x setup.sh
./setup.sh
```

This installs dependencies, sets up cron and systemd services, and prepares the environment.

3. **Create `.env` file manually**

This file holds your private email config for daily log emails. Create `.env` in the root folder (`~/aircraft-logger/.env`) with the following contents:

```
EMAIL_FROM=your_email@example.com
EMAIL_TO=recipient_email@example.com
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
EMAIL_USER=your_email_username
EMAIL_PASSWORD=your_email_password
```

📌 _This file is private and should **never** be uploaded to GitHub. It's excluded via `.gitignore`._

4. **View the dashboard**

Once setup is complete, visit:

```
http://<your-raspberry-pi-ip>:5000
```

You’ll see a live dashboard of aircraft data.

## 🧠 Common Questions (Novice Help)

### Q: I don’t see metadata like aircraft model/operator?
A: This feature uses the OpenSky API. Sometimes OpenSky may not have info for every hex code, especially for military/private planes.

### Q: The time seems off — what’s going on?
A: The dashboard uses your **local timezone** (e.g., AEST), but logs are saved in UTC. The dashboard correctly merges and presents logs by local date.

### Q: How do I stop the logger or dashboard?

```bash
sudo systemctl stop aircraft-logger
sudo systemctl stop aircraft-dashboard
```

### Q: How do I check if it’s working?

```bash
systemctl status aircraft-logger
journalctl -u aircraft-logger -n 50
```

### Q: How do I check the dashboard?

```bash
systemctl status aircraft-dashboard
```

## 🚀 Roadmap Ideas

- CSV viewer in dashboard  
- Heatmap / timeline of flights  
- Metadata history lookup cache  
- Export to Google Sheets or SQLite  
- Flight paths / map view  
- Alerts or filters by aircraft type or altitude  

## ✅ Status

- Fully working, v1.0 stable.  
- Verified with FR24 + PiAware on Raspberry Pi 4.  
- Logs, dashboard, email all tested and functioning.  
- UI updated with pastel theme, iconography, and interactivity.  

---

Built by [VectorXYZing](https://github.com/VectorXYZing). Contributions and feedback welcome!

🛫 Happy spotting!
