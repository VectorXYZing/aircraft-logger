import time
import os
import json
import math
import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, Response
from airlogger.db import get_db_connection
from airlogger.config import STATION_LAT, STATION_LON, HEARTBEAT_FILE, HEALTH_THRESHOLD, LIVE_DATA_MINUTES
from airlogger.utils import convert_to_local

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate Haversine distance in nautical miles with type safety."""
    try:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None: return None
        l1, n1, l2, n2 = float(lat1), float(lon1), float(lat2), float(lon2)
        if l2 == 0 or n2 == 0: return None
        R = 3440.065
        phi1, phi2 = math.radians(l1), math.radians(l2)
        dphi = math.radians(l2 - l1)
        dlambda = math.radians(n2 - n1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
    except (ValueError, TypeError):
        return None

@api_bp.route('/api/live_flights')
def live_flights():
    """Fetch live flights directly from the database (cross-process safe)."""
    minutes = request.args.get('minutes', default=LIVE_DATA_MINUTES, type=int)
    threshold = (datetime.utcnow() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    
    flights_by_hex = {}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Get latest position for each aircraft seen in the last X minutes
            cursor.execute('''
                SELECT * FROM flights 
                WHERE timestamp_utc > ? 
                ORDER BY timestamp_utc DESC
            ''', (threshold,))
            
            for row in cursor.fetchall():
                hex_code = row['hex'].upper()
                if hex_code not in flights_by_hex:
                    dist = calculate_distance(STATION_LAT, STATION_LON, row['lat'], row['lon'])
                    local_time = convert_to_local(row['timestamp_utc'])
                    
                    flights_by_hex[hex_code] = [{
                        'hex': hex_code,
                        'callsign': row['callsign'] or "",
                        'alt': row['altitude'] or 0,
                        'speed': row['speed'] or 0,
                        'track': row['track'] or 0,
                        'lat': row['lat'],
                        'lon': row['lon'],
                        'reg': row['registration'] or "",
                        'model': row['model'] or "",
                        'operator': row['operator'] or "",
                        'time': local_time.strftime('%Y-%m-%d %H:%M:%S') if local_time else row['timestamp_utc'],
                        'distance': round(dist, 1) if dist is not None else None
                    }]
    except Exception as e:
        logger.error(f"Error fetching live flights: {e}")
        return jsonify({"error": str(e)}), 500
        
    return jsonify(flights_by_hex)

@api_bp.route('/api/export_kml/<hex_code>/<date>')
def export_kml(hex_code, date):
    """Export flight path as KML for Google Earth."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT lat, lon, altitude, callsign, timestamp_utc 
            FROM flights 
            WHERE hex = ? AND date(timestamp_utc) = ? 
            ORDER BY timestamp_utc ASC
        ''', (hex_code, date))
        rows = cursor.fetchall()
        conn.close()

        if not rows: return "No data found", 404

        callsign = rows[0]['callsign'] or hex_code
        kml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '  <Document>',
            f'    <name>Flight {callsign} - {date}</name>',
            '    <Placemark>',
            '      <name>Path</name>',
            '      <LineString><altitudeMode>absolute</altitudeMode><coordinates>'
        ]
        for r in rows:
            if r['lat'] and r['lon']:
                alt_m = (int(float(str(r['altitude']).replace(',',''))) if r['altitude'] else 0) * 0.3048
                kml.append(f"{r['lon']},{r['lat']},{alt_m}")
        kml.append('</coordinates></LineString></Placemark></Document></kml>')
        
        return Response("\n".join(kml), mimetype="application/vnd.google-earth.kml+xml",
                        headers={"Content-Disposition": f"attachment;filename=flight_{hex_code}.kml"})
    except Exception as e:
        return str(e), 500

@api_bp.route('/health')
def health():
    try:
        hb = None
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, 'r') as f:
                hb = json.load(f)
        age = time.time() - hb['timestamp'] if hb else 9999
        healthy = age <= HEALTH_THRESHOLD
        return jsonify({'healthy': healthy, 'age_seconds': int(age)}), 200 if healthy else 503
    except:
        return jsonify({'healthy': False}), 500
