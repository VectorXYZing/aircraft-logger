#!/usr/bin/env python3
"""
Script to fetch aircraft metadata from OpenSky Network using an ICAO 24-bit hex code.
Usage: python opensky_flight_info.py <hex_code>
Example: python opensky_flight_info.py abc123
"""

import requests
import sys
import json
import os
from datetime import datetime

# File to store discovered operators
OPERATORS_FILE = os.path.expanduser("~/.opensky_operators.json")

# Load custom operators from file
def load_custom_operators():
    """Load additional operators from the JSON file."""
    if os.path.exists(OPERATORS_FILE):
        try:
            with open(OPERATORS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_custom_operator(prefix, operator_name):
    """Save a newly discovered operator to the JSON file."""
    operators = load_custom_operators()
    if prefix not in operators:
        operators[prefix] = operator_name
        try:
            with open(OPERATORS_FILE, 'w') as f:
                json.dump(operators, f, indent=2)
            print(f"  [Saved new operator: {prefix} -> {operator_name}]")
        except Exception as e:
            print(f"  [Warning: Could not save operator: {e}]")


def get_flight_metadata(icao24):
    """
    Fetch aircraft metadata from OpenSky Network API.
    
    Args:
        icao24: 6-character hex code (ICAO 24-bit address)
    
    Returns:
        dict: Aircraft metadata or None if not found
    """
    icao24 = icao24.lower().strip()
    
    if len(icao24) != 6:
        print(f"Error: ICAO24 hex code must be 6 characters, got '{icao24}'")
        return None
    
    # Check if hex is valid
    try:
        int(icao24, 16)
    except ValueError:
        print(f"Error: '{icao24}' is not a valid hex code")
        return None
    
    # OpenSky States API
    url = f"https://opensky-network.org/api/states/all"
    params = {"icao24": icao24}
    
    try:
        print(f"Querying OpenSky Network for aircraft {icao24.upper()}...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        states = data.get("states", [])
        if not states:
            print(f"No aircraft found with ICAO24 code {icao24.upper()}")
            return None
        
        # OpenSky returns a list of states, each state is a list of attributes
        # Header: icao24, callsign, origin_country, time_position, last_contact, 
        #         longitude, latitude, baro_altitude, on_ground, velocity, heading, 
        #         vertical_rate, sensors, geo_altitude, squawk, spi, position_source
        state = states[0]
        
        metadata = {
            "icao24": state[0],
            "callsign": state[1].strip() if state[1] else "N/A",
            "origin_country": state[2],
            "time_position": datetime.fromtimestamp(state[3]).strftime('%Y-%m-%d %H:%M:%S') if state[3] else "N/A",
            "last_contact": datetime.fromtimestamp(state[4]).strftime('%Y-%m-%d %H:%M:%S') if state[4] else "N/A",
            "longitude": state[5],
            "latitude": state[6],
            "baro_altitude_ft": round(state[7] * 3.28084, 2) if state[7] else "N/A",
            "on_ground": state[8],
            "velocity_kts": round(state[9] * 1.94384, 2) if state[9] else "N/A",
            "heading": state[10],
            "vertical_rate_fpm": round(state[11] * 196.85, 2) if state[11] else "N/A",
            "geo_altitude_ft": round(state[12] * 3.28084, 2) if state[12] else "N/A",
            "squawk": state[13],
            "spi": state[14],
            "position_source": state[15]
        }
        
        return metadata
        
    except requests.exceptions.RequestException as e:
        print(f"Error querying OpenSky API: {e}")
        return None


def get_operator_info(callsign, origin_country, prompt_new=True):
    """
    Attempt to determine operator information from callsign and country.
    Automatically saves newly discovered operators to ~/.opensky_operators.json
    
    Args:
        callsign: The aircraft callsign
        origin_country: The country of registration
        prompt_new: Whether to prompt user for unknown operators
    
    Returns:
        str: Operator information
    """
    if not callsign or callsign == "N/A":
        return "Unknown"
    
    prefix = callsign[:3] if len(callsign) >= 3 else callsign
    
    # Check custom operators file first (user-discovered operators)
    custom_operators = load_custom_operators()
    if prefix in custom_operators:
        return f"{custom_operators[prefix]} ({prefix})"
    
    # Common airline prefixes (first 3 characters of callsign)
    airline_prefixes = {
        "BAW": "British Airways",
        "SHT": "British Airways (Shuttle)",
        "EZY": "easyJet",
        "BEE": "Flybe",
        "RYR": "Ryanair",
        "STN": "Ryanair",
        "WZZ": "Wizz Air",
        "DLH": "Lufthansa",
        "GWI": "Germanwings",
        "AFR": "Air France",
        "KLM": "KLM Royal Dutch Airlines",
        "DLX": "Delta Air Lines",
        "AAL": "American Airlines",
        "UAL": "United Airlines",
        "SWA": "Southwest Airlines",
        "JBU": "JetBlue Airways",
        "QFA": "Qantas",
        "Qantas": "Qantas",
        "ANZ": "Air New Zealand",
        "VA": "Virgin Australia",
        "vir": "Virgin Atlantic",
        "VIR": "Virgin Atlantic",
        "UAE": "Emirates",
        "QTR": "Qatar Airways",
        "ETD": "Etihad Airways",
        "SIA": "Singapore Airlines",
        "HKG": "Hong Kong Airlines",
        "CPA": "Cathay Pacific",
        "JAL": "Japan Airlines",
        "ANA": "All Nippon Airways",
        "KAL": "Korean Air",
        "ASN": "Korean Air",
        "TAM": "LATAM Airlines",
        "LAN": "LATAM Airlines",
        "GLO": "Gol Linhas Aéreas",
        "AZA": "ITA Airways",
        "IBE": "Iberia",
    "JST": "Jetstar",
        "AVA": "Avianca",
        "LAN": "LATAM Chile",
        "LPE": "LATAM Express",
        "LPC": "LATAM Paraguay",
        "LPL": "LATAM Perú",
        "TUI": "TUI Airways",
        "CFG": "Condor",
        "SAS": "SAS Scandinavian Airlines",
        "FIN": "Finnair",
        "AAR": "Asiana Airlines",
        "CSN": "China Southern Airlines",
        "CCA": "Air China",
        "CES": "China Eastern Airlines",
        "CKK": "China Cargo Airline",
        "HYA": "Hainan Airlines",
        "SQA": "SF Airlines",
        "XJC": "Hong Kong Express",
        "CPE": "Cope",
        "CFE": "BA CityFlyer",
        "EXS": "Jet2.com",
        "GAW": "Gandalf Airways",
        "GLG": "AeroLease",
        "HSR": "Air Saint Pierre",
        "HZT": "Air Horizont",
        "JEA": "Northeaster",
        "JKK": "Binter Canarias",
        "JSY": "Jalways",
        "LGL": "Luxair",
        "LRC": "Lufthansa CityLine",
        "LXB": "Luxair",
        "OCN": "Air Charter Services",
        "OHY": "Onur Air",
        "SXS": "SunExpress",
        "TNT": "FedEx",
        "UPS": "UPS Airlines",
        "FDX": "FedEx",
        "CLX": "Cargolux",
        "GTI": "Atlas Air",
        "ABX": "ABX Air",
        "CAL": "China Airlines",
        "EVA": "EVA Air",
        "BOX": "Polar Air Cargo",
        "PAC": "Polar Air Cargo",
        "NCA": "Nippon Cargo Airlines",
    }
    
    prefix = callsign[:3] if len(callsign) >= 3 else callsign
    
    if prefix in airline_prefixes:
        return f"{airline_prefixes[prefix]} ({prefix})"
    
    # Try to guess from country
    country_airlines = {
        "United States": "Various US operators",
        "United Kingdom": "Various UK operators",
        "Germany": "Various German operators",
        "France": "Various French operators",
        "Spain": "Various Spanish operators",
        "Italy": "Various Italian operators",
        "Netherlands": "Various Dutch operators",
        "Australia": "Various Australian operators",
        "Canada": "Various Canadian operators",
        "Brazil": "Various Brazilian operators",
        "Japan": "Various Japanese operators",
        "China": "Various Chinese operators",
        "India": "Various Indian operators",
        "Russia": "Various Russian operators",
        "UAE": "Various Middle Eastern operators",
    }
    
    if origin_country in country_airlines:
        return f"{country_airlines[origin_country]} - {prefix}"
    
    # Prompt user to identify this operator
    if prompt_new:
        print(f"\n  [New operator discovered: {prefix}]")
        print(f"  Country: {origin_country}")
        try:
            operator_name = input("  Enter operator name (or press Enter to skip): ").strip()
            if operator_name:
                save_custom_operator(prefix, operator_name)
                return f"{operator_name} ({prefix})"
        except (EOFError, KeyboardInterrupt):
            pass
    
    return f"Unknown operator (prefix: {prefix}, country: {origin_country})"


def print_metadata(metadata):
    """Pretty print the aircraft metadata."""
    if not metadata:
        return
    
    print("\n" + "=" * 60)
    print(f"  FLIGHT METADATA FOR ICAO24: {metadata['icao24'].upper()}")
    print("=" * 60)
    
    print(f"\n  Callsign:          {metadata['callsign']}")
    print(f"  Operator:          {get_operator_info(metadata['callsign'], metadata['origin_country'])}")
    print(f"  Origin Country:    {metadata['origin_country']}")
    
    print(f"\n  Last Contact:      {metadata['last_contact']}")
    print(f"  Time Position:     {metadata['time_position']}")
    
    print(f"\n  Position:")
    print(f"    Latitude:        {metadata['latitude']}")
    print(f"    Longitude:       {metadata['longitude']}")
    print(f"    Baro Altitude:   {metadata['baro_altitude_ft']} ft")
    print(f"    Geo Altitude:    {metadata['geo_altitude_ft']} ft")
    
    print(f"\n  Movement:")
    print(f"    Velocity:        {metadata['velocity_kts']} kts")
    print(f"    Heading:         {metadata['heading']}°")
    print(f"    Vertical Rate:   {metadata['vertical_rate_fpm']} fpm")
    
    print(f"\n  Additional Info:")
    print(f"    On Ground:       {'Yes' if metadata['on_ground'] else 'No'}")
    print(f"    Squawk:          {metadata['squawk']}")
    print(f"    SPI:             {'Yes' if metadata['spi'] else 'No'}")
    print(f"    Position Source: {metadata['position_source']}")
    
    print("=" * 60 + "\n")


def main():
    if len(sys.argv) != 2:
        print("Usage: python opensky_flight_info.py <hex_code>")
        print("Example: python opensky_flight_info.py abc123")
        print("\nNote: hex_code is the 6-character ICAO 24-bit address (e.g., 4CA303)")
        sys.exit(1)
    
    icao24 = sys.argv[1]
    metadata = get_flight_metadata(icao24)
    
    if metadata:
        print_metadata(metadata)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
