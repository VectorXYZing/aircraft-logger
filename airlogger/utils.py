import pytz
import logging
from datetime import datetime
from airlogger.config import TIMEZONE as TIMEZONE_CONFIG

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    HAS_ZONEINFO = True
except Exception:
    ZoneInfo = None
    HAS_ZONEINFO = False

# Robust timezone initialization
LOCAL_TZ = None
if TIMEZONE_CONFIG and TIMEZONE_CONFIG.strip():
    try:
        if HAS_ZONEINFO:
            LOCAL_TZ = ZoneInfo(TIMEZONE_CONFIG)
        else:
            LOCAL_TZ = pytz.timezone(TIMEZONE_CONFIG)
    except Exception as e:
        logger.warning(f"Could not load timezone {TIMEZONE_CONFIG}: {e}")
        LOCAL_TZ = None

if not LOCAL_TZ:
    try:
        # Fallback to system local time
        LOCAL_TZ = datetime.now().astimezone().tzinfo
    except Exception:
        LOCAL_TZ = pytz.utc

def convert_to_local(utc_str):
    """Convert UTC string (YYYY-MM-DD HH:MM:SS) to local datetime."""
    try:
        if not utc_str: return None
        # Handle formats with or without microseconds
        fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in utc_str else "%Y-%m-%d %H:%M:%S"
        utc_time = datetime.strptime(utc_str, fmt).replace(
            tzinfo=ZoneInfo("UTC") if HAS_ZONEINFO else pytz.utc
        )
        if LOCAL_TZ:
            return utc_time.astimezone(LOCAL_TZ)
        return utc_time
    except Exception as e:
        logger.debug(f"Error converting {utc_str} to local: {e}")
        return None

def get_local_time(utc_time_str):
    """Convert UTC time string to local time formatted string."""
    dt = convert_to_local(utc_time_str)
    if dt:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return utc_time_str

def get_fr24_callsign(callsign):
    """Convert ICAO callsign to IATA-ish flight number for FR24 links."""
    if not callsign: return ""
    c = callsign.upper().strip()
    
    # Mapping for major world airlines
    mapping = {
        "QFA": "QF", "JST": "JQ", "VOZ": "VA", "ANZ": "NZ", "BAW": "BA", "DLH": "LH", "UAE": "EK",
        "AAL": "AA", "DAL": "DL", "UAL": "UA", "SWA": "WN", "AFR": "AF", "KLM": "KL",
        "RYR": "FR", "EZY": "U2", "THY": "TK", "QTR": "QR", "ETD": "EY", "CXA": "MF", "CPA": "CX",
        "ANA": "NH", "JAL": "JL", "KAL": "KE", "SIA": "SQ", "AIC": "AI", "IBE": "IB", "TAP": "TP",
        "FIN": "AY", "SAS": "SK", "SWR": "LX", "AUA": "OS", "BEL": "SN", "LOT": "LO", "CSA": "OK"
    }
    
    prefix = c[:3]
    if prefix in mapping:
        return mapping[prefix] + c[3:]
    return c
