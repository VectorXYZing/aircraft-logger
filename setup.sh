#!/bin/bash

echo "🚀 Setting up Aircraft Logger..."

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y python3-full python3-pip python3-venv git

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
  echo "🔧 Creating Python virtual environment..."
  python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required Python packages
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install specific required packages
echo "📦 Installing specific required packages..."
# pandas is not required for base functionality; only install if requested
pip install flask pytz

# Create logs directory
mkdir -p logs

# Create .env template if missing
if [ ! -f .env ]; then
  echo "⚠️  .env file not found. Creating template..."
  cat <<EOF > .env
EMAIL_FROM=your_email@example.com
EMAIL_TO=recipient_email@example.com
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
EMAIL_USER=your_email_username
EMAIL_PASSWORD=your_email_password
EOF
  echo "⚠️  Please edit .env with your actual email settings."
fi

# Set up systemd service for aircraft logger
echo "🔁 Setting up aircraft logger service..."
SERVICE_USER=${AIRLOGGER_SERVICE_USER:-$USER}
INSTALL_DIR=${AIRLOGGER_INSTALL_DIR:-$PWD}
cat <<EOF | sudo tee /etc/systemd/system/aircraft-logger.service > /dev/null
[Unit]
Description=Aircraft Logger
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/aircraft_logger.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

# Set up systemd service for dashboard
echo "📊 Setting up aircraft dashboard service..."
SERVICE_USER=${AIRLOGGER_SERVICE_USER:-$USER}
INSTALL_DIR=${AIRLOGGER_INSTALL_DIR:-$PWD}
cat <<EOF | sudo tee /etc/systemd/system/aircraft-dashboard.service > /dev/null
[Unit]
Description=Aircraft Logger Dashboard
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/dashboard.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start services
echo "🔄 Reloading systemd and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable aircraft-logger.service
sudo systemctl enable aircraft-dashboard.service
sudo systemctl restart aircraft-logger.service
sudo systemctl restart aircraft-dashboard.service

# Set up daily cron job for emailing logs at 2 AM
echo "📅 Setting up cron job for daily email report at 2 AM..."
(crontab -l 2>/dev/null | grep -v send_log_email.py ; echo "0 2 * * * /home/ps/aircraft-logger/venv/bin/python /home/ps/aircraft-logger/send_log_email.py") | crontab -

# Verify services are running
echo "🔍 Verifying services..."
echo "Checking aircraft-logger service:"
sudo systemctl status aircraft-logger.service --no-pager
echo "Checking aircraft-dashboard service:"
sudo systemctl status aircraft-dashboard.service --no-pager

echo "✅ Setup complete!"
echo "📝 Next steps:"
echo "1. Edit the .env file with your email settings"
echo "2. Access the dashboard at http://<your-raspberry-pi-ip>:5000"
echo "3. Check the logs with: journalctl -u aircraft-logger -f"
echo "4. Email reports will now be sent daily at 2:00 AM UTC with formatted PDF attachments"