#!/usr/bin/env python3
"""Test ADSB.lol metadata lookup for aircraft seen in logs.

Usage:
  python3 scripts/test_adsb_lookup.py [--date YYYY-MM-DD] [--limit N] [--hex HEX]

The script reads log files from AIRLOGGER_LOG_DIR (or ~/aircraft-logger/logs by default),
collects unique Hex codes for the date, and queries ADSB.lol for each hex.
"""
import os
import csv
import gzip
import argparse
import requests
from datetime import datetime


DEFAULT_LOG_DIR = os.environ.get('AIRLOGGER_LOG_DIR', os.path.expanduser('~/aircraft-logger/logs'))
DEFAULT_TEMPLATE = 'https://adsb.lol/aircraft/{hex}.json'
ADSB_TEMPLATE = os.environ.get('AIRLOGGER_METADATA_URLS', DEFAULT_TEMPLATE).split(',')[0]

# Candidate templates to try when the primary returns 404 or is unavailable
CANDIDATE_TEMPLATES = [
    ADSB_TEMPLATE,
    'https://adsb.lol/aircraft/{hex_lower}.json',
    'https://adsb.lol/aircraft/{hex_upper}.json',
    'https://adsb.lol/aircraft/{hex}',
    'https://adsb.lol/api/aircraft/{hex}.json',
    'https://adsb.lol/aircraft/icao/{hex}.json',
    'https://adsb.lol/aircraft/icao/{hex_lower}.json',
    'https://adsb.lol/aircraft/icao/{hex_upper}.json',
    'https://adsb.lol/data/aircraft/{hex}.json',
    'https://www.adsb.lol/aircraft/{hex}.json',
    'https://www.adsb.lol/aircraft/{hex_lower}.json',
    'https://api.adsb.lol/aircraft/{hex}.json',
]


def read_hexes_for_date(log_dir, date_str):
    hexes = []
    seen = set()
    prefix = f"aircraft_log_{date_str}"
    try:
        for fn in os.listdir(log_dir):
            if not fn.startswith(prefix):
                continue
            path = os.path.join(log_dir, fn)
            opener = gzip.open if fn.endswith('.gz') else open
            try:
                with opener(path, 'rt', encoding='utf-8', errors='ignore') as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        h = row.get('Hex') or row.get('hex')
                        if not h:
                            continue
                        h = h.strip().upper()
                        if h and h not in seen:
                            seen.add(h)
                            hexes.append(h)
            except Exception as e:
                print(f"Failed to read {path}: {e}")
    except FileNotFoundError:
        print(f"Log directory not found: {log_dir}")
    return hexes


def query_adsb(hex_code, templates=None, timeout=8):
    templates = templates or CANDIDATE_TEMPLATES
    last_err = 'no attempt'
    for tmpl in templates:
        tmpl = tmpl.strip()
        if not tmpl:
            continue
        url = tmpl.format(hex=hex_code, hex_lower=hex_code.lower(), hex_upper=hex_code.upper())
        print(f' Trying {url} ...')
        try:
            r = requests.get(url, timeout=timeout)
            ctype = r.headers.get('content-type')
            body = r.text
            print(f'  -> HTTP {r.status_code} content-type: {ctype}')
            if r.status_code == 200 and ctype and 'application/json' in ctype:
                try:
                    return r.status_code, True, url, r.json()
                except Exception:
                    return r.status_code, False, url, body[:800]
            if r.status_code == 200:
                return r.status_code, False, url, body[:800]
            # record non-200 and continue
            last_err = f'HTTP {r.status_code} from {url}: ' + (body[:200])
            continue
        except Exception as e:
            print(f'  -> error: {e}')
            last_err = str(e)
            continue
    return None, False, None, last_err


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--date', help='Date YYYY-MM-DD (default today)')
    p.add_argument('--limit', type=int, default=50, help='Max number of hexes to test')
    p.add_argument('--hex', help='Test a single HEX instead of reading logs')
    p.add_argument('--logdir', default=DEFAULT_LOG_DIR, help='Logs directory')
    args = p.parse_args()

    date_str = args.date or datetime.utcnow().date().isoformat()

    if args.hex:
        hexes = [args.hex.strip().upper()]
    else:
        hexes = read_hexes_for_date(args.logdir, date_str)

    if not hexes:
        print('No hexes found for', date_str)
        return

    print(f'Testing {min(len(hexes), args.limit)} hexes from {date_str} using template: {ADSB_TEMPLATE}')
    for i, h in enumerate(hexes[: args.limit], start=1):
        status, is_json, tmpl, payload = query_adsb(h)
        print('-' * 60)
        if status is None:
            print(f'{i}. {h} -> ERROR: {payload}')
            continue
        print(f'{i}. {h} -> HTTP {status} via template: {tmpl}')
        if is_json:
            import json
            print(json.dumps(payload, indent=2)[:2000])
        else:
            print(str(payload)[:2000])


if __name__ == '__main__':
    main()
