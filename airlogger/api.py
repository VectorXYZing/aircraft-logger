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
    """Calculate Haversine distance in nautical miles."""
    if not all([lat1, lon1, lat2, lon2]): return None
    R = 3440.065 # Nautical miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

@api_bp.route('/api/live_flights')
def live_flights():
    """Return filtered live flights from memory."""
    registry = get_live_registry()
    flights_by_hex = {}
    
    for hex_code, flight in registry.items():
        # Include distance if station coordinates are set
        dist = calculate_distance(STATION_LAT, STATION_LON, flight.get('lat'), flight.get('lon'))
        flight['distance'] = round(dist, 1) if dist is not None else None
        flights_by_hex[hex_code] = flight
        
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
            alt_m = (int(r['Altitude']) if r['Altitude'] else 0) * 0.3048 # Convert feet to meters
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
