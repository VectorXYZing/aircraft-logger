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
    "AIRLOGGER_METADATA_URL", "https://opensky-network.org/api/metadata/aircraft/icao/{hex}"
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
    
    # Only reload file at most once every 60 seconds to save CPU
    if _cached_custom_operators is not None and (now - _last_operators_load) < 60:
        return _cached_custom_operators

    if os.path.exists(OPERATORS_FILE):
        try:
            with open(OPERATORS_FILE, "r") as f:
                _cached_custom_operators = json.load(f)
                _last_operators_load = now
                return _cached_custom_operators
        except Exception:
            pass
    
    _cached_custom_operators = {}
    _last_operators_load = now
    return {}


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
    }
    
    if prefix in airline_prefixes:
        return airline_prefixes[prefix]
        
    return ""


def clear_cache() -> None:
    """Clear the metadata cache (useful for tests)."""
    metadata_cache.clear()


def _parse_opensky(data: dict) -> Tuple[str, str, str, str]:
    reg = (data.get("registration") or data.get("reg") or "").strip()
    model = (data.get("model") or "").strip()
    if not model:
        manufacturer = (data.get("manufacturerName") or "").strip()
        if manufacturer:
            model = manufacturer
            
    operator = (data.get("operator") or "").strip()
    owner = (data.get("owner") or "").strip()
    callsign = (data.get("operatorCallsign") or "").strip()
    country = (data.get("country") or "").strip()
    
    # High-quality fallback chain for operator:
    # 1. API 'operator' field
    # 2. Lookup airline from callsign prefix (e.g., JST -> Jetstar)
    # 3. API 'owner' field
    # 4. 'Various [Country] operators' if we have a country
    
    final_operator = operator
    if not final_operator and callsign:
        final_operator = get_operator_from_callsign(callsign, country)
    
    if not final_operator:
        final_operator = owner
        
    if not final_operator and country:
        if country == "Australia":
            final_operator = "Various Australian operators"
        else:
            final_operator = f"Various {country} operators"

    return reg, model, final_operator or "", callsign


def fetch_metadata(hex_code: str) -> Tuple[str, str, str, str]:
    """Fetch metadata for a given ICAO hex using OpenSky with caching and retries.

    Returns a tuple: (registration, model, operator, callsign)
    """
    if not hex_code:
        return "", "", "", ""

    hex_code = hex_code.strip().lower()

    cached = metadata_cache.get(hex_code)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL:
        return (
            cached.get("registration", ""),
            cached.get("model", ""),
            cached.get("operator", ""),
            cached.get("callsign", ""),
        )

    tmpl = os.environ.get("AIRLOGGER_METADATA_URL", METADATA_URL)
    try:
        try:
            url = tmpl.format(hex=hex_code, hex_lower=hex_code.lower(), hex_upper=hex_code.upper())
        except Exception:
            url = tmpl.replace("{hex}", hex_code)

        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    logger.debug("OpenSky returned HTTP %s for %s", resp.status_code, url)
                    data = None
                else:
                    try:
                        data = resp.json()
                    except Exception:
                        data = None

                if data and isinstance(data, dict):
                    reg, model, operator, callsign = _parse_opensky(data)
                    if reg or model or operator or callsign:
                        metadata_cache[hex_code] = {
                            "registration": reg,
                            "model": model,
                            "operator": operator,
                            "callsign": callsign,
                            "timestamp": time.time(),
                        }
                        return reg, model, operator, callsign
                # No useful data yet; treat as a failure to be retried
                last_exc = None
            except requests.exceptions.Timeout as e:
                last_exc = e
                logger.warning("Metadata fetch timeout for %s (attempt %s)", hex_code, attempt)
            except requests.exceptions.RequestException as e:
                last_exc = e
                logger.warning("Metadata fetch failed for %s (attempt %s): %s", hex_code, attempt, e)

            # Backoff before next retry
            if attempt < MAX_RETRIES:
                backoff = BACKOFF_BASE * (2 ** (attempt - 1))
                time.sleep(backoff)

    except Exception as e:
        logger.debug("Unexpected error fetching metadata for %s: %s", hex_code, e)

    return "", "", "", ""
