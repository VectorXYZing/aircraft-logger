"""Optimized metadata fetching with aggressive CPU usage reductions."""
import os
import time
import json
import logging
from typing import Tuple, Dict
import requests

logger = logging.getLogger(__name__)

# Configuration
METADATA_URL = os.environ.get("AIRLOGGER_METADATA_URL", "https://api.adsb.lol/v2/icao/{hex}")
CACHE_TTL = int(os.environ.get("AIRLOGGER_CACHE_TTL", 86400))
MAX_RETRIES = int(os.environ.get("AIRLOGGER_MAX_RETRIES", 3))
BACKOFF_BASE = float(os.environ.get("AIRLOGGER_BACKOFF_BASE", 0.5))

# File to store discovered operators
OPERATORS_FILE = os.path.expanduser("~/.opensky_operators.json")

# Optimized caching system
metadata_cache = {}  # hex -> {registration, model, operator, callsign, timestamp}
failed_cache = {}     # hex -> timestamp (to avoid retrying failed lookups immediately)
_cached_custom_operators = None
_last_operators_load = 0

# Shared requests session for connection reuse
_session = requests.Session()

def load_custom_operators() -> Dict[str, str]:
    """Load additional operators from the JSON file with aggressive caching."""
    global _cached_custom_operators, _last_operators_load
    now = time.time()
    
    # Only reload file at most once every 10 minutes to save CPU
    if _cached_custom_operators is not None and (now - _last_operators_load) < 600:
        return _cached_custom_operators

    if os.path.exists(OPERATORS_FILE):
        try:
            with open(OPERATORS_FILE, "r") as f:
                _cached_custom_operators = json.load(f)
                _last_operators_load = now
                return _cached_custom_operators
        except Exception:
            pass
    
    # Negative caching for missing file
    if _cached_custom_operators is None:
        _cached_custom_operators = {}
    _last_operators_load = now
    return _cached_custom_operators

# Optimized airline prefixes - only most common ones to reduce CPU
AIRLINE_PREFIXES = {
    "BAW": "British Airways", "SHT": "British Airways",
    "EZY": "easyJet", "BEE": "Flybe", "RYR": "Ryanair", "STN": "Ryanair",
    "WZZ": "Wizz Air", "DLH": "Lufthansa", "AFR": "Air France", "KLM": "KLM",
    "AAL": "American Airlines", "UAL": "United", "SWA": "Southwest", "JBU": "JetBlue",
    "QFA": "Qantas", "ANZ": "Air New Zealand", "NZ": "Air New Zealand",
    "VA": "Virgin Australia", "VOZ": "Virgin Australia", "VIR": "Virgin Atlantic",
    "UAE": "Emirates", "QTR": "Qatar Airways", "ETD": "Etihad",
    "JAL": "Japan Airlines", "ANA": "All Nippon Airways", "KAL": "Korean Air",
    "TAM": "LATAM", "LAN": "LATAM", "GLO": "Gol", "IBE": "Iberia",
    "JST": "Jetstar", "TUI": "TUI Airways", "SAS": "Scandinavian Airlines",
    "FDX": "FedEx", "UPS": "UPS", "TNT": "FedEx", "CLX": "Cargolux",
}

def get_operator_from_callsign(callsign: str, country: str = "") -> str:
    """Ultra-fast operator lookup with minimal CPU usage."""
    if not callsign or callsign == "N/A":
        return ""

    prefix = callsign[:3].upper() if len(callsign) >= 3 else callsign.upper()
    if not prefix:
        return ""
    
    # Fast lookup in optimized prefix list
    return AIRLINE_PREFIXES.get(prefix, "")

def clear_cache() -> None:
    """Clear all caches."""
    metadata_cache.clear()
    failed_cache.clear()

def _get_cached_result(hex_code: str) -> Tuple[str, str, str, str]:
    """Get result from memory cache with TTL check."""
    cached = metadata_cache.get(hex_code)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL:
        return (
            cached.get("registration", ""),
            cached.get("model", ""),
            cached.get("operator", ""),
            cached.get("callsign", ""),
        )
    return None, None, None, None

def _should_retry_lookup(hex_code: str) -> bool:
    """Determine if we should retry a failed lookup."""
    failed_time = failed_cache.get(hex_code)
    if not failed_time:
        return True
    
    # Exponential backoff: wait longer between failed retries
    retry_interval = min(3600, 60 * (2 ** (len(failed_cache) % 5)))  # Max 1 hour
    return time.time() - failed_time > retry_interval

def _cache_result(hex_code: str, reg: str, model: str, operator: str, callsign: str):
    """Cache successful lookup result."""
    metadata_cache[hex_code] = {
        "registration": reg,
        "model": model,
        "operator": operator,
        "callsign": callsign,
        "timestamp": time.time(),
    }

def _cache_failure(hex_code: str):
    """Cache failed lookup to avoid immediate retries."""
    failed_cache[hex_code] = time.time()
    
    # Keep failed cache size manageable
    if len(failed_cache) > 1000:
        # Remove oldest entries
        oldest_keys = sorted(failed_cache.items(), key=lambda x: x[1])[:500]
        for key, _ in oldest_keys:
            del failed_cache[key]

def fetch_metadata_optimized(hex_code: str) -> Tuple[str, str, str, str]:
    """Ultra-optimized metadata fetching with minimal CPU usage."""
    if not hex_code:
        return "", "", "", ""

    hex_code = hex_code.strip().lower()
    
    # Fast path: check memory cache
    cached_result = _get_cached_result(hex_code)
    if cached_result[0] is not None:
        return cached_result
    
    # Skip if recently failed
    if not _should_retry_lookup(hex_code):
        return "", "", "", ""
    
    # Single API call to adsb.lol (most reliable and fastest)
    try:
        url = METADATA_URL.format(hex=hex_code)
        # Use shared session for connection reuse
        response = _session.get(url, timeout=3)  # Reduced timeout for faster failure
        
        if response.status_code == 200:
            data = response.json()
            if data and "ac" in data and data["ac"] and len(data["ac"]) > 0:
                ac = data["ac"][0]
                
                reg = (ac.get("r") or "").strip()
                model = (ac.get("t") or "").strip()
                callsign = (ac.get("flight") or "").strip()
                
                # Derive operator from callsign (fast local operation)
                operator = get_operator_from_callsign(callsign) if callsign else ""
                
                # Cache the successful result
                _cache_result(hex_code, reg, model, operator, callsign)
                
                return reg, model, operator, callsign
        
        # Cache the failure
        _cache_failure(hex_code)
        
    except Exception as e:
        logger.debug(f"Metadata lookup failed for {hex_code}: {e}")
        _cache_failure(hex_code)
    
    return "", "", "", ""

# Keep legacy function name for compatibility
def fetch_metadata(hex_code: str) -> Tuple[str, str, str, str]:
    """Legacy function that now uses optimized metadata fetching."""
    return fetch_metadata_optimized(hex_code)