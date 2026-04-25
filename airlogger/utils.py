import pytz
from datetime import datetime
from airlogger.config import TIMEZONE as TIMEZONE_CONFIG

try:
    from zoneinfo import ZoneInfo
    HAS_ZONEINFO = True
except Exception:
    ZoneInfo = None
    HAS_ZONEINFO = False

if TIMEZONE_CONFIG:
    try:
        if HAS_ZONEINFO:
            LOCAL_TZ = ZoneInfo(TIMEZONE_CONFIG)
        else:
            LOCAL_TZ = pytz.timezone(TIMEZONE_CONFIG)
    except Exception:
        LOCAL_TZ = None
else:
    try:
        LOCAL_TZ = datetime.now().astimezone().tzinfo
    except Exception:
        LOCAL_TZ = None

def convert_to_local(utc_str):
    """Convert UTC string to local datetime."""
    try:
        utc_time = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("UTC") if HAS_ZONEINFO else pytz.utc
        )
        if LOCAL_TZ:
            return utc_time.astimezone(LOCAL_TZ)
        return utc_time
    except (ValueError, Exception):
        return None

def get_local_time(utc_time_str):
    """Convert UTC time string to local time."""
    try:
        if not utc_time_str: return ""
        utc_dt = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S.%f')
        local_tz = pytz.timezone(TIMEZONE_CONFIG) if TIMEZONE_CONFIG else pytz.utc
        local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
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
