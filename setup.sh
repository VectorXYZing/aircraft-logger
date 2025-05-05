#!/bin/bash

set -e

APP_DIR="/home/pi/aircraft-logger"
VENV_DIR="$APP_DIR/aircraftenv"
PYTHON_BIN="$VENV_DIR/bin/python"

# Create virtual environment if not exists
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate virtualenv and install requirements
source "$VENV_DIR/bin/activate"
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.txt"

echo "Creating log directory..."
mkdir -p "$APP_DIR/logs"

# Create systemd service for dashboard
DASHBOARD_SERVICE_FILE="/etc/systemd/system/aircraft-dashboard.service"
if [ ! -f "$DASHBOARD_SERVICE_FILE" ]; then
  echo "Setting up systemd service for dashboard..."
  sudo tee "$DASHBOARD_SERVICE_FILE" > /dev/null <<EOL
[Unit]
Description=Aircraft Logger Dashboard
After=network.target

[Service]
ExecStart=$PYTHON_BIN $APP_DIR/dashboard.py
WorkingDirectory=$APP_DIR
Restart=always
User=pi
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOL
  sudo systemctl daemon-reexec
  sudo systemctl daemon-reload
  sudo systemctl enable aircraft-dashboard.service
  sudo systemctl start aircraft-dashboard.service
fi

# Create systemd service for aircraft logger
LOGGER_SERVICE_FILE="/etc/systemd/system/aircraft-logger.service"
if [ ! -f "$LOGGER_SERVICE_FILE" ]; then
  echo "Setting up systemd service for aircraft logger..."
  sudo tee "$LOGGER_SERVICE_FILE" > /dev/null <<EOL
[Unit]
Description=Aircraft Logger Script
After=network.target

[Service]
ExecStart=$PYTHON_BIN $APP_DIR/aircraft_logger.py
WorkingDirectory=$APP_DIR
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOL
  sudo systemctl daemon-reexec
  sudo systemctl daemon-reload
  sudo systemctl enable aircraft-logger.service
  sudo systemctl start aircraft-logger.service
fi

# Add cron job for sending daily logs
CRON_LINE="0 23 * * * $PYTHON_BIN $APP_DIR/send_log_email.py"
(crontab -l 2>/dev/null | grep -v -F "$CRON_LINE"; echo "$CRON_LINE") | crontab -

echo "Setup complete. Dashboard running on http://<your-pi-ip>:5000"
