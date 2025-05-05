#!/bin/bash

set -e

echo "🚀 Setting up Aircraft Logger..."

# Create virtual environment if it doesn't exist
if [ ! -d "aircraftenv" ]; then
  python3 -m venv aircraftenv
fi
source aircraftenv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create logs directory if it doesn't exist
mkdir -p logs

# Set up .env file if it doesn't exist
if [ ! -f ".env" ]; then
  echo "EMAIL_USER=your_email@example.com" >> .env
  echo "EMAIL_PASS=your_password_or_app_specific_password" >> .env
  echo "EMAIL_TO=recipient_email@example.com" >> .env
fi

# Create and enable aircraft-logger systemd service
SERVICE_FILE=/etc/systemd/system/aircraft-logger.service
if [ ! -f "$SERVICE_FILE" ]; then
  sudo bash -c 'cat > /etc/systemd/system/aircraft-logger.service' <<EOF
[Unit]
Description=Aircraft Logger
After=network.target

[Service]
ExecStart=/home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/aircraft_logger.py
WorkingDirectory=/home/pi/aircraft-logger
Restart=always
User=pi
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reexec
  sudo systemctl daemon-reload
  sudo systemctl enable aircraft-logger.service
  sudo systemctl start aircraft-logger.service
fi

# Create and enable aircraft-dashboard systemd service
DASHBOARD_SERVICE_FILE=/etc/systemd/system/aircraft-dashboard.service
if [ ! -f "$DASHBOARD_SERVICE_FILE" ]; then
  sudo bash -c 'cat > /etc/systemd/system/aircraft-dashboard.service' <<EOF
[Unit]
Description=Aircraft Logger Dashboard
After=network.target

[Service]
ExecStart=/home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/dashboard.py
WorkingDirectory=/home/pi/aircraft-logger
Restart=always
User=pi
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reexec
  sudo systemctl daemon-reload
  sudo systemctl enable aircraft-dashboard.service
  sudo systemctl start aircraft-dashboard.service
fi

# Set up daily email report cron job (clears other crontab entries first)
crontab -l | grep -v "send_log_email.py" | crontab - || true
CRON_CMD="0 23 * * * /home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/send_log_email.py"
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "📅 Setting up cron job for daily email report..."
echo "✅ Setup complete!"
