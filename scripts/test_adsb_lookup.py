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
ADSB_TEMPLATE = os.environ.get('AIRLOGGER_METADATA_URLS', 'https://adsb.lol/aircraft/{hex}.json').split(',')[0]


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


def query_adsb(hex_code, template=ADSB_TEMPLATE, timeout=8):
    url = template.format(hex=hex_code, hex_lower=hex_code.lower(), hex_upper=hex_code.upper())
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, r.text[:400], r.headers.get('content-type')
    except Exception as e:
        return None, str(e), None


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
        status, body_snip, ctype = query_adsb(h)
        print('-' * 60)
        print(f'{i}. {h} -> HTTP {status} content-type: {ctype}')
        print(body_snip)


if __name__ == '__main__':
    main()
