#!/usr/bin/env python3
"""Query ADSB.lol v2 `/v2/icao/{hex}` and extract common metadata fields.

Usage:
  python3 scripts/inspect_adsb_lol.py --hex 7C7AB1

Prints a compact summary of registration, model, operator, callsign and last position/time if available.
"""
import argparse
import requests
import json

DEFAULT_URL = 'https://api.adsb.lol/v2/icao/{hex}'


def extract_fields(data):
    # data is the parsed JSON response from ADSB.lol v2
    # try to get an item from 'ac' array
    if isinstance(data, dict) and 'ac' in data and isinstance(data['ac'], list) and data['ac']:
        item = data['ac'][0]
    else:
        item = data if isinstance(data, dict) else {}

    def pick(src, keys):
        if not src or not isinstance(src, dict):
            return None
        for k in keys:
            v = src.get(k)
            if v:
                return v
        return None

    out = {}
    # ADSB.lol v2 specific keys: 'r' = registration, 't' = typecode/model, 'flight' = callsign
    out['registration'] = pick(item, ('r', 'reg', 'registration', 'tail', 'tail_number')) or ''
    out['model'] = pick(item, ('t', 'type', 'typecode', 'model', 'aircraft_type')) or ''
    out['operator'] = pick(item, ('ops', 'operator', 'owner', 'airline')) or ''
    out['callsign'] = (pick(item, ('flight', 'callsign', 'flight_number')) or '').strip()
    # position/time
    lat = pick(item, ('lat', 'latitude'))
    lon = pick(item, ('lon', 'longitude'))
    if lat and lon:
        out['position'] = f"{lat},{lon}"
    else:
        out['position'] = ''
    # prefer item-level timestamps but fall back to top-level 'now' or 'ctime'
    last = pick(item, ('last_seen', 'seen', 'now', 'ctime'))
    if not last and isinstance(data, dict):
        last = data.get('now') or data.get('ctime')
    out['last_seen_ms'] = last
    # render last_seen as ISO if numeric
    try:
        if isinstance(out['last_seen_ms'], (int, float)):
            import datetime
            out['last_seen_iso'] = datetime.datetime.utcfromtimestamp(out['last_seen_ms']/1000.0).isoformat() + 'Z'
        else:
            out['last_seen_iso'] = ''
    except Exception:
        out['last_seen_iso'] = ''
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
    print(f'Querying ADSB.lol v2 for {hex_code}...')
    try:
        data = query(hex_code, url_template=args.url)
    except Exception as e:
        print('ERROR fetching:', e)
        return

    if not data:
        print('No JSON response or empty body')
        return

    print('Raw response summary: total=', data.get('total'), ' msg=', data.get('msg'))
    fields = extract_fields(data)
    print('\nExtracted:')
    for k, v in fields.items():
        print(f'  {k}: {v}')

    print('\nFull JSON (truncated):')
    print(json.dumps(data, indent=2)[:4000])


if __name__ == '__main__':
    main()
