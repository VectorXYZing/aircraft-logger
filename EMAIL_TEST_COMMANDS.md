# 📧 Test Email Commands for Raspberry Pi

## Send Test Email with Today's Log

```bash
# Navigate to your aircraft-logger directory
cd /home/ps/aircraft-logger  # or your actual path

# Activate virtual environment
source venv/bin/activate

# Send test email with today's log
python3 send_log_email.py
```

## Send Test Email with Specific Date

```bash
# Navigate to your aircraft-logger directory
cd /home/ps/aircraft-logger  # or your actual path

# Activate virtual environment
source venv/bin/activate

# Send test email with specific date (YYYY-MM-DD format)
python3 send_log_email.py 2025-01-11
```

## What the Script Does:

1. ✅ **Reads** the aircraft log CSV file for the specified date
2. ✅ **Consolidates** aircraft data (one line per aircraft)
3. ✅ **Generates** formatted PDF report with:
   - Summary statistics
   - Aircraft table with max altitude, speed, etc.
   - Professional formatting
4. ✅ **Sends** email with PDF attachment

## Log File Location:
- Default: `~/aircraft-logger/logs/aircraft_log_YYYY-MM-DD.csv`
- The script automatically finds the log file for the specified date

## Email Configuration Requirements:
Make sure your `.env` file has these SMTP settings configured:

```env
# Email Settings (required for sending)
SMTP_SERVER=your.smtp.server.com
SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=destination-email@gmail.com
SMTP_USE_SSL=false
```

## Troubleshooting:

### If you get SMTP errors:
1. Check your `.env` file has the correct settings
2. Make sure you have an app password (not your regular password)
3. Verify the SMTP server and port are correct

### If no log file is found:
1. Check that the date format is correct: YYYY-MM-DD
2. Verify the log file exists: `ls ~/aircraft-logger/logs/`

### If you get PDF generation errors:
1. Make sure reportlab is installed: `pip install reportlab`
2. Check that the log file has data in it

## Quick Test Commands:

```bash
# Test email with today's date
python3 send_log_email.py

# Test email with yesterday's date
python3 send_log_email.py $(date -d "yesterday" +%Y-%m-%d)

# Check what log files are available
ls ~/aircraft-logger/logs/aircraft_log_*.csv