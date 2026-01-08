"""Metadata fetching helper for OpenSky Network.
Provides: fetch_metadata(hex_code) -> (registration, model, operator, callsign)
Includes retries/backoff and an in-memory cache with TTL.
"""
import os
import time
import json
import logging
from typing import Tuple, Dict

import requests

logger = logging.getLogger(__name__)

METADATA_URL = os.environ.get(
    "AIRLOGGER_METADATA_URL", "https://api.adsb.lol/v2/icao/{hex}"
)
CACHE_TTL = int(os.environ.get("AIRLOGGER_CACHE_TTL", 86400))
MAX_RETRIES = int(os.environ.get("AIRLOGGER_MAX_RETRIES", 3))
BACKOFF_BASE = float(os.environ.get("AIRLOGGER_BACKOFF_BASE", 0.5))

# File to store discovered operators
OPERATORS_FILE = os.path.expanduser("~/.opensky_operators.json")

# Simple in-memory cache: hex -> {registration, model, operator, callsign, timestamp}
metadata_cache = {}
_cached_custom_operators = None
_last_operators_load = 0

def load_custom_operators() -> Dict[str, str]:
    """Load additional operators from the JSON file with internal caching."""
    global _cached_custom_operators, _last_operators_load
    now = time.time()
    
    # Only reload file at most once every 5 minutes to save CPU
    if _cached_custom_operators is not None and (now - _last_operators_load) < 300:
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


def get_operator_from_callsign(callsign: str, country: str = "") -> str:
    """Determine operator from callsign prefix."""
    if not callsign or callsign == "N/A":
        return ""

    prefix = (callsign or "")[:3].upper()
    if not prefix:
        return ""
    
    # User-customized operators
    custom = load_custom_operators()
    if prefix in custom:
        return custom[prefix]

    # Predefined common airline prefixes
    airline_prefixes = {
        "BAW": "British Airways",
        "SHT": "British Airways",
        "EZY": "easyJet",
        "BEE": "Flybe",
        "RYR": "Ryanair",
        "STN": "Ryanair",
        "WZZ": "Wizz Air",
        "DLH": "Lufthansa",
        "GWI": "Germanwings",
        "AFR": "Air France",
        "KLM": "KLM",
        "DLX": "Delta",
        "AAL": "American Airlines",
        "UAL": "United",
        "SWA": "Southwest",
        "JBU": "JetBlue",
        "QFA": "Qantas",
        "ANZ": "Air New Zealand",
        "NZ": "Air New Zealand",
        "VA": "Virgin Australia",
        "VOZ": "Virgin Australia",
        "VIR": "Virgin Atlantic",
        "UAE": "Emirates",
        "QTR": "Qatar Airways",
        "ETD": "Etihad",
        "SIA": "Singapore Airlines",
        "HKG": "Hong Kong Airlines",
        "CPA": "Cathay Pacific",
        "JAL": "Japan Airlines",
        "ANA": "All Nippon Airways",
        "KAL": "Korean Air",
        "TAM": "LATAM",
        "LAN": "LATAM",
        "GLO": "Gol",
        "AZA": "ITA Airways",
        "IBE": "Iberia",
        "JST": "Jetstar",
        "TJS": "Jetstar Asia",
        "AVA": "Avianca",
        "TUI": "TUI Airways",
        "SAS": "Scandinavian Airlines",
        "FIN": "Finnair",
        "AAR": "Asiana",
        "CSN": "China Southern",
        "CCA": "Air China",
        "CES": "China Eastern",
        "HYA": "Hainan Airlines",
        "FDX": "FedEx",
        "UPS": "UPS",
        "TNT": "FedEx",
        "CLX": "Cargolux",
        "GTI": "Atlas Air",
        "CAL": "China Airlines",
        "EVA": "EVA Air",
        "RYK": "Ryanair",
        "EXS": "Jet2",
        "VLG": "Vueling",
        "THY": "Turkish Airlines",
        "TSR": "TransState",
        "ASH": "Mesa Airlines",
        "QXE": "Horizon Air",
        "CPZ": "Compass Airlines",
        "SKV": "SkyWest",
        "SKW": "SkyWest",
        "AAY": "Allegiant Air",
        "DAL": "Delta",
        "FDX": "FedEx",
        "MTN": "Mountain Air",
        "NJS": "National Jet Systems",
        "RXA": "Regional Express (Rex)",
        "NWK": "Network Aviation",
        "QLK": "QantasLink",
        "XRO": "JetEx",
        "VBH": "Virgin Australia",
    }
    
    if prefix in airline_prefixes:
        return airline_prefixes[prefix]
        
    return ""


def clear_cache() -> None:
    """Clear the metadata cache (useful for tests)."""
    metadata_cache.clear()


def _parse_metadata_response(data: dict) -> Tuple[str, str, str, str]:
    """Parse metadata from adsb.lol or OpenSky."""
    reg = ""
    model = ""
    operator = ""
    callsign = ""
    country = ""

    # Check if this is an adsb.lol response
    if "ac" in data and isinstance(data["ac"], list) and len(data["ac"]) > 0:
        ac = data["ac"][0]
        reg = (ac.get("r") or "").strip()
        model = (ac.get("t") or "").strip()
        callsign = (ac.get("flight") or "").strip()
    else:
        # Fallback to OpenSky format
        reg = (data.get("registration") or data.get("reg") or "").strip()
        model = (data.get("model") or "").strip()
        if not model:
            manufacturer = (data.get("manufacturerName") or "").strip()
            if manufacturer:
                model = manufacturer
        operator = (data.get("operator") or "").strip()
        callsign = (data.get("operatorCallsign") or "").strip()
        country = (data.get("country") or "").strip()
        if not operator:
             operator = (data.get("owner") or "").strip()

    # Derived operator lookup
    final_operator = operator
    if "Various" in final_operator and "operators" in final_operator:
        final_operator = ""
        
    if not final_operator and callsign:
        final_operator = get_operator_from_callsign(callsign, country)
        
    if not final_operator and country:
        if country == "Australia":
            final_operator = "Various Australian operators"
        else:
            final_operator = f"Various {country} operators"

    return reg, model, final_operator or "", callsign


# Multiple metadata sources for comprehensive aircraft lookup
ADSBLOL_URL = "https://api.adsb.lol/v2/icao/{hex}"
OPENSKY_METADATA_URL = "https://opensky-network.org/api/metadata/aircraft/icao/{hex}"
OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"

# File to store aircraft database of known registrations and operators
AIRCRAFT_DB_FILE = os.path.expanduser("~/.aircraft_db.json")

def _load_aircraft_db() -> Dict[str, dict]:
    """Load persistent aircraft database."""
    if os.path.exists(AIRCRAFT_DB_FILE):
        try:
            with open(AIRCRAFT_DB_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_aircraft_db(db: Dict[str, dict]):
    """Save aircraft database persistently."""
    try:
        with open(AIRCRAFT_DB_FILE, 'w') as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save aircraft database: {e}")

def _update_aircraft_db(hex_code: str, reg: str, model: str, operator: str, callsign: str):
    """Update persistent aircraft database with new information."""
    db = _load_aircraft_db()
    
    # Update only if we have new information
    if hex_code not in db:
        db[hex_code] = {}
    
    if reg and not db[hex_code].get("registration"):
        db[hex_code]["registration"] = reg
    if model and not db[hex_code].get("model"):
        db[hex_code]["model"] = model
    if operator and not db[hex_code].get("operator"):
        db[hex_code]["operator"] = operator
    if callsign and not db[hex_code].get("callsign"):
        db[hex_code]["callsign"] = callsign
    
    # Always update last_seen
    db[hex_code]["last_seen"] = time.time()
    
    _save_aircraft_db(db)

def _get_from_aircraft_db(hex_code: str) -> Tuple[str, str, str, str]:
    """Get aircraft information from local database."""
    db = _load_aircraft_db()
    aircraft = db.get(hex_code.lower())
    
    if aircraft:
        return (
            aircraft.get("registration", ""),
            aircraft.get("model", ""),
            aircraft.get("operator", ""),
            aircraft.get("callsign", "")
        )
    
    return "", "", "", ""

def _parse_opensky_metadata(data: dict) -> Tuple[str, str, str, str]:
    """Parse OpenSky metadata API response."""
    reg = (data.get("registration") or data.get("reg") or "").strip()
    model = (data.get("model") or "").strip()
    if not model:
        manufacturer = (data.get("manufacturerName") or "").strip()
        if manufacturer:
            model = manufacturer
    operator = (data.get("operator") or "").strip()
    callsign = (data.get("operatorCallsign") or "").strip()
    country = (data.get("country") or "").strip()
    
    if not operator:
        operator = (data.get("owner") or "").strip()
    
    return reg, model, operator, callsign, country

def _parse_opensky_states(data: dict, hex_code: str) -> Tuple[str, str, str, str]:
    """Parse OpenSky states API response for live flight data."""
    if "states" not in data or not data["states"]:
        return "", "", "", ""
    
    # Find matching aircraft by hex code
    for state in data["states"]:
        if len(state) >= 17 and state[0].upper() == hex_code.upper():
            reg = (state[1] or "").strip()  # registration
            callsign = (state[10] or "").strip()  # callsign
            operator = ""  # Derive from callsign
            model = ""  # States API doesn't provide model
            
            return reg, model, operator, callsign
    
    return "", "", "", ""

def fetch_metadata_comprehensive(hex_code: str) -> Tuple[str, str, str, str]:
    """Comprehensive metadata fetching with multiple sources and fallbacks."""
    if not hex_code:
        return "", "", "", ""

    hex_code = hex_code.strip().lower()

    # Check cache first
    cached = metadata_cache.get(hex_code)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL:
        return (
            cached.get("registration", ""),
            cached.get("model", ""),
            cached.get("operator", ""),
            cached.get("callsign", ""),
        )

    # Check local aircraft database
    db_reg, db_model, db_operator, db_callsign = _get_from_aircraft_db(hex_code)
    
    final_reg = db_reg
    final_model = db_model
    final_operator = db_operator
    final_callsign = db_callsign
    
    # Try adsb.lol (live flight data)
    try:
        url = ADSBLOL_URL.format(hex=hex_code)
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and "ac" in data and data["ac"]:
                # Parse adsb.lol response
                ac = data["ac"][0]
                reg = (ac.get("r") or "").strip()
                model = (ac.get("t") or "").strip()
                callsign = (ac.get("flight") or "").strip()
                
                # Update with any new information
                if reg:
                    final_reg = reg
                if model:
                    final_model = model
                if callsign:
                    final_callsign = callsign
                
                # Derive operator from callsign if we have one
                if final_callsign and not final_operator:
                    final_operator = get_operator_from_callsign(final_callsign)
                
                # Update database and cache
                _update_aircraft_db(hex_code, final_reg, final_model, final_operator, final_callsign)
                
                # Cache the result
                metadata_cache[hex_code] = {
                    "registration": final_reg,
                    "model": final_model,
                    "operator": final_operator,
                    "callsign": final_callsign,
                    "timestamp": time.time(),
                }
                
                return final_reg, final_model, final_operator, final_callsign
    except Exception as e:
        logger.debug(f"adsb.lol lookup failed for {hex_code}: {e}")

    # Try OpenSky metadata API
    try:
        url = OPENSKY_METADATA_URL.format(hex=hex_code)
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                reg, model, operator, callsign, country = _parse_opensky_metadata(data)
                
                # Update with any new information
                if reg:
                    final_reg = reg
                if model:
                    final_model = model
                if operator:
                    final_operator = operator
                if callsign:
                    final_callsign = callsign
                
                # Derive operator from callsign if missing
                if not final_operator and final_callsign:
                    final_operator = get_operator_from_callsign(final_callsign, country)
                
                # Update database and cache
                _update_aircraft_db(hex_code, final_reg, final_model, final_operator, final_callsign)
                
                # Cache the result
                metadata_cache[hex_code] = {
                    "registration": final_reg,
                    "model": final_model,
                    "operator": final_operator,
                    "callsign": final_callsign,
                    "timestamp": time.time(),
                }
                
                return final_reg, final_model, final_operator, final_callsign
    except Exception as e:
        logger.debug(f"OpenSky metadata lookup failed for {hex_code}: {e}")

    # Try OpenSky states API (live data)
    try:
        resp = requests.get(OPENSKY_STATES_URL, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                reg, model, operator, callsign = _parse_opensky_states(data, hex_code)
                
                # Update with any new information
                if reg:
                    final_reg = reg
                if callsign:
                    final_callsign = callsign
                
                # Derive operator from callsign if we have one
                if final_callsign and not final_operator:
                    final_operator = get_operator_from_callsign(final_callsign)
                
                # Update database and cache
                _update_aircraft_db(hex_code, final_reg, final_model, final_operator, final_callsign)
                
                # Cache the result
                metadata_cache[hex_code] = {
                    "registration": final_reg,
                    "model": final_model,
                    "operator": final_operator,
                    "callsign": final_callsign,
                    "timestamp": time.time(),
                }
                
                return final_reg, final_model, final_operator, final_callsign
    except Exception as e:
        logger.debug(f"OpenSky states lookup failed for {hex_code}: {e}")

    # Return whatever we have from database, cache it if we found something
    if final_reg or final_model or final_operator or final_callsign:
        metadata_cache[hex_code] = {
            "registration": final_reg,
            "model": final_model,
            "operator": final_operator,
            "callsign": final_callsign,
            "timestamp": time.time(),
        }
        return final_reg, final_model, final_operator, final_callsign

    return "", "", "", ""

# Keep legacy function name for backward compatibility
def fetch_metadata(hex_code: str) -> Tuple[str, str, str, str]:
    """Legacy function that now uses comprehensive metadata fetching."""
    return fetch_metadata_comprehensive(hex_code)
