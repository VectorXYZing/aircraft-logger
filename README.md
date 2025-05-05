# ✈️ Aircraft Logger with Metadata and Dashboard

A Raspberry Pi-based local aircraft tracker using FR24/PiAware feeds with:

- ✅ CSV logging with metadata enrichment (registration, model, operator)
- ✅ Daily log email
- ✅ Web-based live dashboard
- ✅ Easy install with `setup.sh`

---

## 📸 What It Does

This tool listens to `30003` feed data from FR24 or PiAware, logs aircraft with unique ICAO hex codes, and enriches with live metadata from public APIs. It also provides:

- ✉️ Daily email with the full CSV log
- 🌐 Local dashboard for browsing recent flights

---

## 🛠 Requirements

- Raspberry Pi running Debian (Bookworm tested)
- Python 3.11+
- FR24 and/or PiAware installed and running
- Internet access for metadata enrichment (cached)

---

## 🚀 Quick Install

```bash
cd ~
git clone git@github.com:VectorXYZing/aircraft-logger.git
cd aircraft-logger
chmod +x setup.sh
./setup.sh
```

Then visit:

```
http://<your-pi-ip>:5000
```

---

## 📁 Folder Structure

```bash
aircraft-logger/
├── aircraft_logger.py        # Main logging script
├── send_log_email.py        # Daily email script
├── dashboard.py             # Web dashboard (Flask)
├── setup.sh                 # Installer and crontab setup
├── .env                     # Credentials (not committed)
├── logs/                    # CSV logs (daily)
├── static/                  # CSS and favicon
└── templates/               # HTML templates
```

---

## 🔒 Security

- SMTP credentials stored in `.env` and ignored via `.gitignore`
- Uses `requests_cache` to avoid repeated lookups
- No passwords committed to GitHub

---

## ✅ Features Completed

- [x] One record per aircraft (consolidated data)
- [x] Enriched metadata from OpenSky (with fallback)
- [x] CSV log + live web interface
- [x] Email report sent daily via cron
- [x] Setup script installs everything and adds crontab

---

## 🧭 Roadmap

- [ ] Add time range selector to dashboard
- [ ] Export filtered logs
- [ ] Deploy to Docker / other OS support

---

## 📜 License

[Creative Commons Zero v1.0 Universal](LICENSE) — Public Domain.

---

Built with 💡 by [VectorXYZing](https://github.com/VectorXYZing)
