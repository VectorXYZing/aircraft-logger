#!/usr/bin/env python3
"""Probe common readsb/dump1090 Net API endpoints for a given HEX.

Tries a set of candidate URL patterns against a host:port (default localhost:30053)
and prints any JSON responses or HTTP status for inspection.
"""
import argparse
import requests
import json


DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 30053

CANDIDATE_PATHS = [
    '/json/aircraft/{hex}',
    '/aircraft/{hex}',
    '/ac/{hex}',
    '/data/aircraft.json?icao={hex}',
    '/data/aircraft.json?icao={hex_lower}',
    '/data/aircraft.json?icao={hex_upper}',
    '/dump1090/data/aircraft.json?icao={hex}',
    '/dump1090/data/aircraft.json?icao={hex_lower}',
    '/dump1090/data/aircraft.json?icao={hex_upper}',
    '/stations/{hex}',
]


def probe_one(host, port, hex_code, timeout=5):
    results = []
    for path in CANDIDATE_PATHS:
        url = f'http://{host}:{port}' + path.format(hex=hex_code, hex_lower=hex_code.lower(), hex_upper=hex_code.upper())
        try:
            r = requests.get(url, timeout=timeout)
            ctype = r.headers.get('content-type', '')
            entry = {'url': url, 'status': r.status_code, 'content-type': ctype}
            if r.status_code == 200 and 'application/json' in ctype:
                try:
                    entry['json'] = r.json()
                except Exception:
                    entry['text'] = r.text[:2000]
            else:
                entry['text'] = r.text[:400]
        except Exception as e:
            entry = {'url': url, 'error': str(e)}
        results.append(entry)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host', default=DEFAULT_HOST)
    p.add_argument('--port', type=int, default=DEFAULT_PORT)
    p.add_argument('--hex', required=True)
    p.add_argument('--timeout', type=int, default=5)
    args = p.parse_args()

    hex_code = args.hex.strip().upper()
    print(f'Probing readsb/dump1090-style Net API on {args.host}:{args.port} for HEX {hex_code}')
    results = probe_one(args.host, args.port, hex_code, timeout=args.timeout)
    for r in results:
        print('-' * 80)
        print(r.get('url'))
        if 'error' in r:
            print(' ERROR:', r['error'])
            continue
        print(' Status:', r.get('status'), ' Content-Type:', r.get('content-type'))
        if 'json' in r:
            print(json.dumps(r['json'], indent=2)[:4000])
        elif 'text' in r:
            print(r['text'][:2000])


if __name__ == '__main__':
    main()
