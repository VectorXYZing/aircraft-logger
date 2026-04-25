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
