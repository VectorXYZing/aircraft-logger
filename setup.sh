#!/bin/bash

echo "=== Aircraft Logger Setup ==="

# Step 1: Create virtual environment
echo "-> Creating virtual environment..."
python3 -m venv ~/aircraftenv
source ~/aircraftenv/bin/activate

# Step 2: Install Python dependencies
echo "-> Installing dependencies..."
pip install flask python-dotenv requests

# Step 3: Ensure log directory exists
echo "-> Creating logs directory..."
mkdir -p ~/aircraft-logger/logs

# Step 4: Create .env file if missing
ENV_FILE=~/aircraft-logger/.env
if [ ! -f "$ENV_FILE" ]; then
  echo "-> Creating .env file..."
  cat <<EOF > $ENV_FILE
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=yourpassword
EMAIL_TO=recipient@email.com
EOF
  echo "!! Remember to edit your .env file with real SMTP credentials !!"
fi

# Step 5: Setup cron jobs
echo "-> Setting up cron jobs..."

# Load existing crontab and add new entries if not already present
(crontab -l 2>/dev/null | grep -v aircraft_logger.py; echo "@reboot /home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/aircraft_logger.py &") | crontab -
(crontab -l 2>/dev/null | grep -v send_log_email.py; echo "0 23 * * * /home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/send_log_email.py") | crontab -
(crontab -l 2>/dev/null | grep -v dashboard.py; echo "@reboot /home/pi/aircraftenv/bin/python /home/pi/aircraft-logger/dashboard.py &") | crontab -

echo "✅ Setup complete. Reboot or run manually to start."
