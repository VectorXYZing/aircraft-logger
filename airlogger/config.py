"""Centralized configuration for airlogger.

Reads environment variables with sensible defaults and provides helper functions
for validation and parsing.
"""
import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Core paths
LOG_DIR = os.getenv("AIRLOGGER_LOG_DIR", os.path.expanduser("~/aircraft-logger/logs"))
# Timezone: try TZ env, then AIRLOGGER_TZ; if empty, use system local tz
TIMEZONE = os.getenv("AIRLOGGER_TZ", os.getenv("TZ", ""))

# Metadata
METADATA_URL = os.getenv(
    "AIRLOGGER_METADATA_URL", "https://opensky-network.org/api/metadata/aircraft/icao/{hex}"
)
CACHE_TTL = int(os.getenv("AIRLOGGER_CACHE_TTL", "86400"))
MAX_RETRIES = int(os.getenv("AIRLOGGER_MAX_RETRIES", "3"))
BACKOFF_BASE = float(os.getenv("AIRLOGGER_BACKOFF_BASE", "0.5"))

# SMTP / email settings
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("EMAIL_USER")
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "10"))

# Runtime and defaults
SERVICE_USER = os.getenv("AIRLOGGER_SERVICE_USER", os.getenv("USER", ""))
INSTALL_DIR = os.getenv("AIRLOGGER_INSTALL_DIR", os.getcwd())

# Heartbeat / health
HEARTBEAT_FILE = os.path.join(LOG_DIR, "heartbeat.json")
HEALTH_THRESHOLD = int(os.getenv("AIRLOGGER_HEALTH_THRESHOLD", "600"))  # seconds


def validate_smtp_config() -> Tuple[bool, list]:
    """Validate SMTP/email configuration. Returns (is_valid, missing_keys)."""
    missing = []
    if not SMTP_SERVER:
        missing.append("SMTP_SERVER")
    if not SMTP_USER:
        missing.append("EMAIL_USER")
    if not SMTP_PASSWORD:
        missing.append("EMAIL_PASSWORD")
    if not EMAIL_TO:
        missing.append("EMAIL_TO")
    return (len(missing) == 0, missing)
