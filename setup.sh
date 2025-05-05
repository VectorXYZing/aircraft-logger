#!/bin/bash

echo "🚀 Setting up Aircraft Logger..."

# Create virtual environment if not exists
if [ ! -d "~/aircraftenv" ]; then
  echo "🔧 Creating Python virtual environment..."
  python3 -m venv ~/aircraftenv
fi

source ~/aircraftenv/bin/activate

# Install required Python packages
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r ~/aircraft-logger/requirements.txt

# Create logs directory
mkdir -p ~/aircraft-logger/logs

# Create .env template if missing
if [ ! -f ~/aircraft-logger/.env ]; then
  echo "⚠️  .env file not found. Creating template..."
  cat <<EOF > ~/aircraft-logger/.env
EMAIL_USER=you@example.com
EMAIL_PASS=yourpassword
EMAIL_TO=recipient@example.com
EMAIL_SUBJECT="Daily Aircraft Log"
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EOF
  echo "⚠️  Please edit ~/aircraft-logger/.env with your actual email settings."
fi

# Set up systemd service for aircraft logger
echo "🔁 Setting up aircraft logger service..."
cat <<EOF | sudo tee /etc/systemd/system/aircraft-logger.service > /dev/null
[Unit]
Description=Aircraft Logger
After=network.target

[Service]
ExecStart=/home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/aircraft_logger.py
WorkingDirectory=/home/pi/aircraft-logger
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable aircraft-logger.service
sudo systemctl restart aircraft-logger.service

# Set up systemd service for dashboard
echo "📊 Setting up aircraft dashboard service..."
cat <<EOF | sudo tee /etc/systemd/system/aircraft-dashboard.service > /dev/null
[Unit]
Description=Aircraft Logger Dashboard
After=network.target

[Service]
ExecStart=/home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/dashboard.py
WorkingDirectory=/home/pi/aircraft-logger
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable aircraft-dashboard.service
sudo systemctl restart aircraft-dashboard.service

# Set up daily cron job for emailing logs
echo "📅 Setting up cron job for daily email report..."
(crontab -l 2>/dev/null | grep -v send_log_email.py ; echo "0 8 * * * /home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/send_log_email.py") | crontab -

echo "✅ Setup complete!"
