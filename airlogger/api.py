import time
import os
import json
import math
import logging
from flask import Blueprint, jsonify, request, Response
from airlogger.db import get_live_registry, get_db_connection
from airlogger.config import HEARTBEAT_FILE, HEALTH_THRESHOLD, STATION_LAT, STATION_LON

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate Haversine distance in nautical miles with type safety."""
    try:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None: return None
        l1, n1, l2, n2 = float(lat1), float(lon1), float(lat2), float(lon2)
        if l2 == 0 or n2 == 0: return None # Filter out bad GPS data
        
        R = 3440.065 # Nautical miles
        phi1, phi2 = math.radians(l1), math.radians(l2)
        dphi = math.radians(l2 - l1)
        dlambda = math.radians(n2 - n1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
    except (ValueError, TypeError):
        return None

@api_bp.route('/api/live_flights')
def live_flights():
    """Return filtered live flights from memory."""
    registry = get_live_registry()
    flights_by_hex = {}
    
    for hex_code, flight in registry.items():
        # Include distance if station coordinates are set
        dist = calculate_distance(STATION_LAT, STATION_LON, flight.get('lat'), flight.get('lon'))
        
        # Format for frontend consistency
        processed_flight = {
            'hex': flight.get('hex'),
            'callsign': flight.get('callsign'),
            'alt': flight.get('alt'),
            'speed': flight.get('speed'),
            'track': flight.get('track'),
            'lat': flight.get('lat'),
            'lon': flight.get('lon'),
            'reg': flight.get('reg'),
            'model': flight.get('model'),
            'operator': flight.get('operator'),
            'time': flight.get('time_utc'),
            'distance': round(dist, 1) if dist is not None else None
        }
        
        flights_by_hex[hex_code] = [processed_flight]
        
    return jsonify(flights_by_hex)

@api_bp.route('/api/export_kml/<hex_code>/<date>')
def export_kml(hex_code, date):
    """Export flight path as KML for Google Earth."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT lat as Latitude, lon as Longitude, altitude as Altitude, callsign as Callsign, timestamp_utc as Time 
        FROM flights 
        WHERE hex = ? AND date(timestamp_utc) = ? 
        ORDER BY timestamp_utc ASC
    ''', (hex_code, date))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No data found", 404

    callsign = rows[0]['Callsign'] or hex_code
    kml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        f'    <name>Flight {callsign} - {date}</name>',
        '    <Style id="yellowLineGreenPoly">',
        '      <LineStyle><color>7f00ffff</color><width>4</width></LineStyle>',
        '      <PolyStyle><color>7f00ff00</color></PolyStyle>',
        '    </Style>',
        '    <Placemark>',
        f'      <name>{callsign} Path</name>',
        '      <styleUrl>#yellowLineGreenPoly</styleUrl>',
        '      <LineString>',
        '        <extrude>1</extrude>',
        '        <tessellate>1</tessellate>',
        '        <altitudeMode>absolute</altitudeMode>',
        '        <coordinates>'
    ]
    
    for r in rows:
        if r['Latitude'] and r['Longitude']:
            try:
                raw_alt = str(r['Altitude']).replace(',', '') if r['Altitude'] else "0"
                alt_m = int(float(raw_alt)) * 0.3048
            except (ValueError, TypeError):
                alt_m = 0
            kml.append(f"          {r['Longitude']},{r['Latitude']},{alt_m}")
            
    kml.extend([
        '        </coordinates>',
        '      </LineString>',
        '    </Placemark>',
        '  </Document>',
        '</kml>'
    ])
    
    return Response(
        "\n".join(kml),
        mimetype="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f"attachment;filename=flight_{hex_code}_{date}.kml"}
    )

@api_bp.route('/health')
def health():
    try:
        hb = None
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, 'r') as f:
                hb = json.load(f)
        
        age = time.time() - hb['timestamp'] if hb else None
        healthy = (age is not None and age <= HEALTH_THRESHOLD)
        return jsonify({'healthy': healthy, 'age_seconds': int(age) if age is not None else None}), 200 if healthy else 503
    except Exception as e:
        return jsonify({'healthy': False, 'error': str(e)}), 500
