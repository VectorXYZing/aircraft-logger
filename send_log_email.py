import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import csv
import logging
from logging.handlers import RotatingFileHandler
import sys
import tempfile
from collections import defaultdict

# Load environment variables
load_dotenv()

from airlogger.config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO, SMTP_USE_SSL, SMTP_TIMEOUT

EMAIL_HOST = SMTP_SERVER
EMAIL_PORT = SMTP_PORT
EMAIL_ADDRESS = SMTP_USER
EMAIL_PASSWORD = SMTP_PASSWORD
EMAIL_RECIPIENT = EMAIL_TO
SMTP_USE_SSL = SMTP_USE_SSL
SMTP_TIMEOUT = SMTP_TIMEOUT

LOG_DIR = os.path.expanduser("~/aircraft-logger/logs")
# Allow date override via command line argument
if len(sys.argv) > 1:
    TODAY = sys.argv[1]
else:
    TODAY = datetime.utcnow().strftime("%Y-%m-%d")
LOG_FILE = os.path.join(LOG_DIR, f"aircraft_log_{TODAY}.csv")

# Logging setup
LOGGING_DIR = os.path.expanduser('~/aircraft-logger/logs')
os.makedirs(LOGGING_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOGGING_DIR, 'send_log_email.log')
logger = logging.getLogger('send_log_email')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# Rotating file handler (5MB per file, keep 3 backups)
file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def consolidate_aircraft_data():
    """Read CSV data and consolidate by aircraft (hex code)"""
    aircraft_data = defaultdict(lambda: {
        'first_seen': None,
        'last_seen': None,
        'max_altitude': 0,
        'max_speed': 0,
        'callsigns': set(),
        'registrations': set(),
        'operators': set(),
        'models': set(),
        'positions': []
    })
    
    try:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from airlogger.db import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flights WHERE date(timestamp_utc) = ?", (TODAY,))
            
            for row in cursor.fetchall():
                hex_code = (row['hex'] or '').upper()
                if not hex_code:
                    continue
                
                # Parse numeric fields
                try:
                    altitude = float(row['altitude'] or 0)
                    speed = float(row['speed'] or 0)
                except (ValueError, TypeError):
                    altitude = 0
                    speed = 0
                
                timestamp = row['timestamp_utc']
                callsign = (row['callsign'] or '').strip()
                registration = (row['registration'] or '').strip()
                operator = (row['operator'] or '').strip()
                model = (row['model'] or '').strip()
                
                # Update consolidated data
                data = aircraft_data[hex_code]
                
                # Track time span
                if timestamp:
                    if not data['first_seen'] or timestamp < data['first_seen']:
                        data['first_seen'] = timestamp
                    if not data['last_seen'] or timestamp > data['last_seen']:
                        data['last_seen'] = timestamp
                
                # Track maximum values
                data['max_altitude'] = max(data['max_altitude'], altitude)
                data['max_speed'] = max(data['max_speed'], speed)
                
                # Track sets of unique values
                if callsign:
                    data['callsigns'].add(callsign)
                if registration:
                    data['registrations'].add(registration)
                if operator:
                    data['operators'].add(operator)
                if model:
                    data['models'].add(model)
                
                # Track positions (lat, lon)
                try:
                    lat = float(row['lat'] or 0)
                    lon = float(row['lon'] or 0)
                    if lat != 0 and lon != 0:
                        data['positions'].append((lat, lon, timestamp))
                except (ValueError, TypeError):
                    pass
    
    except Exception as e:
        logger.error(f"Failed to read from database for {TODAY}: {e}")
        return {}
    
    # Convert sets to lists for easier handling
    for hex_code, data in aircraft_data.items():
        data['callsigns'] = list(data['callsigns'])
        data['registrations'] = list(data['registrations'])
        data['operators'] = list(data['operators'])
        data['models'] = list(data['models'])
    
    return aircraft_data

def generate_pdf_report(aircraft_data, output_path):
    """Generate a formatted PDF report"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        logger.error("reportlab library not installed. Please install with: pip install reportlab")
        return False
    
    try:
        doc = SimpleDocTemplate(output_path, pagesize=A4,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        story = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
        )
        
        normal_style = styles['Normal']
        
        # Title
        title = Paragraph(f"Aircraft Log Report - {TODAY}", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Summary statistics
        total_aircraft = len(aircraft_data)
        total_records = sum(len(data.get('callsigns', [])) for data in aircraft_data.values())
        
        summary_text = f"""
        <b>Summary Statistics:</b><br/>
        Total Aircraft Tracked: {total_aircraft}<br/>
        Total Records: {total_records}<br/>
        Report Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """
        
        summary_para = Paragraph(summary_text, normal_style)
        story.append(summary_para)
        story.append(Spacer(1, 20))
        
        # Table data
        table_data = [['Hex Code', 'Registration', 'Callsign', 'Operator', 'Model', 'Max Alt (ft)', 'Max Speed (kt)', 'Time Logged']]
        
        # Sort aircraft by hex code
        sorted_aircraft = sorted(aircraft_data.items(), key=lambda x: x[0])
        
        for hex_code, data in sorted_aircraft:
            registration = ', '.join(data['registrations']) if data['registrations'] else 'N/A'
            callsign = ', '.join(data['callsigns']) if data['callsigns'] else 'N/A'
            operator = ', '.join(data['operators']) if data['operators'] else 'N/A'
            model = ', '.join(data['models']) if data['models'] else 'N/A'
            
            altitude_str = f"{data['max_altitude']:.0f}" if data['max_altitude'] > 0 else "N/A"
            speed_str = f"{data['max_speed']:.0f}" if data['max_speed'] > 0 else "N/A"
            
            time_logged = data['last_seen'] if data['last_seen'] else 'N/A'
            
            row = [hex_code, registration, callsign, operator, model, altitude_str, speed_str, time_logged]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[1.2*inch, 1*inch, 1*inch, 1.2*inch, 1*inch, 0.8*inch, 0.8*inch, 1.2*inch])
        
        # Style the table
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        table.setStyle(style)
        story.append(table)
        
        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        return False

def send_email():
    # Validate SMTP configuration
    from airlogger.config import validate_smtp_config

    ok, missing = validate_smtp_config()
    if not ok:
        logger.error(f"Missing SMTP/email configuration: {', '.join(missing)}. Aborting email send.")
        return

    if not os.path.exists(LOG_FILE):
        logger.error(f"No log file found for {TODAY}")
        return

    # Consolidate aircraft data
    aircraft_data = consolidate_aircraft_data()
    if not aircraft_data:
        logger.error("No aircraft data found to include in report")
        return

    # Generate summary statistics
    total_records = sum(len(data.get('callsigns', [])) for data in aircraft_data.values())
    total_aircraft = len(aircraft_data)
    
    # Get top operators and models
    operator_counts = defaultdict(int)
    model_counts = defaultdict(int)
    
    for data in aircraft_data.values():
        for operator in data['operators']:
            operator_counts[operator] += 1
        for model in data['models']:
            model_counts[model] += 1
    
    top_operators = sorted(operator_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    summary_lines = [
        f"Aircraft Log Summary for {TODAY}",
        f"Total aircraft tracked: {total_aircraft}",
        f"Total records processed: {total_records}",
        "Top operators:",
    ]
    for op, count in top_operators:
        summary_lines.append(f"  - {op}: {count}")
    summary_lines.append("Top models:")
    for model, count in top_models:
        summary_lines.append(f"  - {model}: {count}")
    summary_lines.append("\nSee attached PDF report for detailed aircraft information.")
    summary_text = "\n".join(summary_lines)

    subject = f"Aircraft Log Report – {TODAY}"
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject

    msg.attach(MIMEText(summary_text, "plain"))
    
    # Generate PDF report
    pdf_filename = f"aircraft_report_{TODAY}.pdf"
    pdf_path = os.path.join(LOG_DIR, pdf_filename)
    pdf_created = False
    
    if generate_pdf_report(aircraft_data, pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=pdf_filename)
            part["Content-Disposition"] = f'attachment; filename="{pdf_filename}"'
            msg.attach(part)
            pdf_created = True
            logger.info(f"PDF report attached to email: {pdf_filename}")
        except Exception as e:
            logger.error(f"Failed to attach PDF report: {e}")
    else:
        logger.error("Failed to generate PDF report")

    # Send with retries (handle STARTTLS or SSL)
    import smtplib as _smtplib
    from time import sleep

    attempts = 0
    max_attempts = 3
    email_sent = False
    try:
        while attempts < max_attempts:
            try:
                if SMTP_USE_SSL or EMAIL_PORT == 465:
                    server = _smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=SMTP_TIMEOUT)
                else:
                    server = _smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=SMTP_TIMEOUT)
                    server.ehlo()
                    server.starttls()

                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
                server.quit()
                logger.info("✅ Email sent successfully.")
                email_sent = True
                break
            except _smtplib.SMTPException as e:
                attempts += 1
                logger.warning(f"SMTP send attempt {attempts} failed: {e}")
                if attempts < max_attempts:
                    sleep(2 ** attempts)
                else:
                    logger.error(f"❌ Failed to send email after {attempts} attempts: {e}")
                    break
    except Exception as e:
        logger.error(f"Unexpected error during email sending: {e}")
    
    # Always clean up PDF file regardless of success/failure
    if pdf_created:
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info("🗑️ PDF file cleaned up successfully")
        except Exception as e:
            logger.warning(f"Failed to clean up PDF file {pdf_path}: {e}")
    
    if not email_sent:
        logger.error("Email sending failed - check logs for details")

if __name__ == "__main__":
    send_email()