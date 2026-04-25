from flask import Flask
import logging
from airlogger.config import DASHBOARD_HOST, DASHBOARD_PORT
from airlogger.web import web_bp
from airlogger.api import api_bp

# Flask App Initialization
app = Flask(__name__)
app.register_blueprint(web_bp)
app.register_blueprint(api_bp)

# Simple logging setup for the entry point
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('dashboard')

if __name__ == "__main__":
    logger.info(f"Starting Aircraft Dashboard on {DASHBOARD_HOST}:{DASHBOARD_PORT}...")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT)
