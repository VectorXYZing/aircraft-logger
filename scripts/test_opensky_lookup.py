#!/usr/bin/env python3
"""Test OpenSky aircraft metadata lookups for given ICAO hex codes and print extracted metadata.

Usage:
  python3 scripts/test_opensky_lookup.py --hex AB1234
  python3 scripts/test_opensky_lookup.py --list AB1234,7AB8AE
"""
import argparse
import requests
import json

DEFAULT_URL = 'https://opensky-network.org/api/metadata/aircraft/icao/{hex}'


def extract_fields(data):
    """Extract common metadata fields from OpenSky metadata response."""
    if not isinstance(data, dict):
        return {
            'registration': '',
            'model': '',
            'operator': '',
            'callsign': '',
            'country': '',
            'last_seen_ms': None,
            'icao24': '',
            'raw': data
        }

    reg = data.get('registration') or ''
    model = data.get('model') or ''
    manufacturer = data.get('manufacturerName') or ''
    if not model and manufacturer:
        model = manufacturer
    operator = data.get('operator') or data.get('owner') or ''
    callsign = data.get('operatorCallsign') or ''
    country = data.get('country') or ''
    last_seen_ms = data.get('timestamp') or data.get('lastSeen') or None
    icao24 = data.get('icao24') or ''

    return {
        'registration': reg,
        'model': model,
        'operator': operator,
        'callsign': callsign,
        'country': country,
        'last_seen_ms': last_seen_ms,
        'icao24': icao24,
        'raw': data
    }


def query(hex_code, url_template=DEFAULT_URL, timeout=8):
    url = url_template.format(hex=hex_code, hex_lower=hex_code.lower(), hex_upper=hex_code.upper())
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--hex', help='Single hex to query')
    p.add_argument('--list', help='Comma-separated list of hex codes')
    p.add_argument('--url', default=DEFAULT_URL)
    args = p.parse_args()

    hexes = []
    if args.hex:
        hexes.append(args.hex.strip().upper())
    if args.list:
        hexes.extend([h.strip().upper() for h in args.list.split(',') if h.strip()])

    if not hexes:
        print('No hex codes specified. Use --hex or --list')
        return

    for h in hexes:
        print('='*60)
        print('HEX:', h)
        try:
            data = query(h, args.url)
        except Exception as e:
            print('  ERROR:', e)
            continue
        if not data:
            print('  No JSON response')
            continue
        fields = extract_fields(data)
        print('  registration:', fields['registration'])
        print('  model:', fields['model'])
        print('  operator:', fields['operator'])
        print('  callsign:', fields['callsign'])
        print('  country:', fields['country'])
        print('  last_seen_ms:', fields['last_seen_ms'])
        print('  icao24:', fields['icao24'])
        print('  sample raw snippet:', json.dumps(fields['raw'], indent=2)[:800])


if __name__ == '__main__':
    main()
