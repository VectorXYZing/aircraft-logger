"""Metadata fetching helper for OpenSky Network.
Provides: fetch_metadata(hex_code) -> (registration, model, operator, callsign)
Includes retries/backoff and an in-memory cache with TTL.
"""
import os
import time
import logging
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

METADATA_URL = os.environ.get(
    "AIRLOGGER_METADATA_URL", "https://opensky-network.org/api/metadata/aircraft/icao/{hex}"
)
CACHE_TTL = int(os.environ.get("AIRLOGGER_CACHE_TTL", 86400))
MAX_RETRIES = int(os.environ.get("AIRLOGGER_MAX_RETRIES", 3))
BACKOFF_BASE = float(os.environ.get("AIRLOGGER_BACKOFF_BASE", 0.5))

# Simple in-memory cache: hex -> {registration, model, operator, callsign, timestamp}
metadata_cache = {}


def clear_cache() -> None:
    """Clear the metadata cache (useful for tests)."""
    metadata_cache.clear()


def _parse_opensky(data: dict) -> Tuple[str, str, str, str]:
    reg = data.get("registration") or data.get("reg") or ""
    model = data.get("model") or ""
    if not model:
        manufacturer = data.get("manufacturerName") or ""
        if manufacturer:
            model = manufacturer
    operator = data.get("operator") or data.get("owner") or ""
    callsign = data.get("operatorCallsign") or ""
    return reg or "", model or "", operator or "", callsign or ""


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
