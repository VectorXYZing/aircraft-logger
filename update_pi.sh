#!/bin/bash
# Update script for Raspberry Pi aircraft logger
# Run this script on your Pi after git pull

echo "🚀 Updating Aircraft Logger on Raspberry Pi..."

# Update code repository
echo "📥 Pulling latest changes..."
git pull

# Activate virtual environment and install dependencies
echo "📦 Installing PDF library dependencies..."
source venv/bin/activate
pip install reportlab==4.0.8

# Update cron schedule
echo "⏰ Updating cron schedule to 2 AM..."
(crontab -l 2>/dev/null | grep -v send_log_email.py ; echo "0 2 * * * /home/ps/aircraft-logger/venv/bin/python /home/ps/aircraft-logger/send_log_email.py") | crontab -

# Restart services
echo "🔄 Restarting services..."
sudo systemctl restart aircraft-logger.service
sudo systemctl restart aircraft-dashboard.service

echo "✅ Update complete!"
echo "📧 Email reports will now be sent at 2:00 AM daily with formatted PDF attachments"
echo "🧪 Test the new functionality with: python3 send_log_email.py"