#!/usr/bin/env python3
"""Query OpenSky `/api/metadata/aircraft/icao/{hex}` and extract common metadata fields.

Usage:
  python3 scripts/inspect_opensky.py --hex AB1234

Prints a compact summary of registration, model, operator, callsign and last seen timestamp if available.
"""
import argparse
import requests
import json

DEFAULT_URL = 'https://opensky-network.org/api/metadata/aircraft/icao/{hex}'


def extract_fields(data):
    # data is the parsed JSON response from OpenSky metadata endpoint
    if not isinstance(data, dict):
        return {
            'registration': '',
            'model': '',
            'operator': '',
            'callsign': '',
            'country': '',
            'last_seen_ms': None,
            'icao24': '',
        }

    out = {}
    out['registration'] = data.get('registration') or ''
    out['model'] = data.get('model') or data.get('manufacturerName') or ''
    out['operator'] = data.get('operator') or data.get('owner') or ''
    out['callsign'] = data.get('operatorCallsign') or ''
    out['country'] = data.get('country') or ''
    out['last_seen_ms'] = data.get('timestamp') or data.get('lastSeen') or None
    out['icao24'] = data.get('icao24') or ''

    return out


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
    p.add_argument('--hex', required=True)
    p.add_argument('--url', default=DEFAULT_URL)
    args = p.parse_args()

    hex_code = args.hex.strip().upper()
    print(f'Querying OpenSky metadata for {hex_code}...')
    try:
        data = query(hex_code, url_template=args.url)
    except Exception as e:
        print('ERROR fetching:', e)
        return

    if not data:
        print('No JSON response or empty body')
        return

    fields = extract_fields(data)
    print('\nExtracted:')
    for k, v in fields.items():
        print(f'  {k}: {v}')

    print('\nFull JSON (truncated):')
    print(json.dumps(data, indent=2)[:4000])


if __name__ == '__main__':
    main()
