#!/usr/bin/env python3
"""Test ADSB.lol v2 lookups for given HEX codes and print extracted metadata.

Usage:
  python3 scripts/test_adsb_lookup.py --hex 7C7AB1
  python3 scripts/test_adsb_lookup.py --list 7C7AB1,7AB8AE
"""
import argparse
import requests
import json

DEFAULT_URL = 'https://api.adsb.lol/v2/icao/{hex}'


def extract_fields(data):
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

    reg = pick(item, ('r', 'reg', 'registration', 'tail')) or ''
    model = pick(item, ('t', 'type', 'typecode', 'model')) or ''
    operator = pick(item, ('ops', 'operator', 'owner', 'airline')) or ''
    callsign = (pick(item, ('flight', 'callsign', 'flight_number')) or '').strip()
    lat = pick(item, ('lat', 'latitude'))
    lon = pick(item, ('lon', 'longitude'))

    return {
        'registration': reg,
        'model': model,
        'operator': operator,
        'callsign': callsign,
        'lat': lat,
        'lon': lon,
        'raw': item
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
        print('  total:', data.get('total'), ' msg:', data.get('msg'))
        fields = extract_fields(data)
        print('  registration:', fields['registration'])
        print('  model:', fields['model'])
        print('  operator:', fields['operator'])
        print('  callsign:', fields['callsign'])
        print('  lat/lon:', fields['lat'], fields['lon'])
        print('  sample raw snippet:', json.dumps(fields['raw'], indent=2)[:800])


if __name__ == '__main__':
    main()
