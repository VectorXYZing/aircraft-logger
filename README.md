# Aircraft Logger

A Raspberry Pi-based aircraft data logger for FR24 and PiAware. Captures, enriches, and emails daily aircraft logs, and serves a local dashboard for live viewing.

## Features
- Connects to local dump1090 or FR24 stream
- Logs all aircraft seen each day
- Enriches data with registration and operator info
- Emails zipped CSV daily
- Web-based dashboard (Flask)

## Requirements
- Raspberry Pi (tested on Pi 4)
- Python 3
- dump1090-fa or fr24feed installed

## Setup
1. Clone repo
2. Create `.env` with email config
3. Install Python packages: `pip install -r requirements.txt`
4. Set up cron jobs (see `crontab -e` section)

## Author
[VectorXYZing](https://github.com/VectorXYZing)
