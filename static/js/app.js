/**
 * Aircraft Logger Dashboard - Main Application Logic
 */

class AircraftDashboard {
    constructor(config) {
        this.initialData = config.initialData || [];
        this.summary = config.summary || null;
        this.mapThemeUrl = config.mapThemeUrl;
        this.isLiveModeActive = false;
        this.liveMapInterval = null;
        this.mapLayers = [];
        this.colors = ['#667eea', '#764ba2', '#43e97b', '#4facfe', '#ff0844', '#f6d365', '#fda085', '#00f2fe', '#f093fb', '#f5576c'];
        
        this.initMap();
        if (this.summary) {
            this.initCharts();
            this.initTableFilters();
        }
        this.initEventListeners();
        
        // Initial setup
        this.updateMap(this.initialData, false);
        this.fetchListOnly();
        
        // Background polling for the list (every 60s)
        setInterval(() => this.fetchListOnly(), 60000);
    }

    initMap() {
        this.flightMap = L.map('flightMap').setView([0, 0], 2);
        this.tileLayer = L.tileLayer(this.mapThemeUrl, {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(this.flightMap);
    }

    normalizeData(data) {
        return data.map(ac => ({
            hex: ac.hex || ac.Hex || "UNKNOWN",
            callsign: ac.callsign || ac.Callsign || "",
            reg: ac.reg || ac.Registration || "",
            model: ac.model || ac.Model || "",
            alt: parseFloat(ac.alt || ac.Altitude),
            speed: parseFloat(ac.speed || ac.Speed),
            track: parseFloat(ac.track || ac.Track),
            lat: parseFloat(ac.lat || ac.Latitude),
            lon: parseFloat(ac.lon || ac.Longitude),
            time: ac.time || ac["Time Local"] || ""
        }));
    }

    updateMap(aircraftData, isLive = false) {
        // Clear existing layers
        this.mapLayers.forEach(layer => this.flightMap.removeLayer(layer));
        this.mapLayers = [];
        
        const bounds = [];
        const flightsByHex = {};
        const normalizedData = this.normalizeData(aircraftData);
        
        normalizedData.forEach(ac => {
            if (!isNaN(ac.lat) && !isNaN(ac.lon) && ac.lat !== 0 && ac.lon !== 0) {
                if (!flightsByHex[ac.hex]) flightsByHex[ac.hex] = [];
                flightsByHex[ac.hex].push(ac);
                bounds.push([ac.lat, ac.lon]);
            }
        });

        Object.keys(flightsByHex).forEach((hex, index) => {
            const flightPath = flightsByHex[hex];
            const latlngs = flightPath.map(ac => [ac.lat, ac.lon]);
            const color = this.colors[index % this.colors.length];
            
            // ONLY draw the path line if in Live Mode or if we have very few aircraft
            if (isLive || Object.keys(flightsByHex).length < 5) {
                const polyline = L.polyline(latlngs, {
                    color: color, weight: 2, opacity: 0.6, smoothFactor: 1
                }).addTo(this.flightMap);
                this.mapLayers.push(polyline);
            }

            // Draw markers - in non-live mode, only show the LATEST position to keep it clean
            const pointsToShow = isLive ? flightPath : [flightPath[0]];
            
            pointsToShow.forEach((ac, i) => {
                const isLatest = (i === 0);
                let marker;
                
                if (isLatest) {
                    let heading = ac.track;
                    if (isNaN(heading) || heading === undefined) {
                        heading = (flightPath.length > 1) ? this.calculateHeading(ac, flightPath[1]) : 0;
                    }
                    
                    const iconHtml = `<div style="transform: rotate(${heading}deg); color: ${color}; font-size: 1.5rem; text-shadow: 1px 1px 2px #000;"><i class="bi bi-airplane-fill"></i></div>`;
                    const planeIcon = L.divIcon({
                        html: iconHtml, className: 'custom-plane-icon', iconSize: [24, 24], iconAnchor: [12, 12]
                    });
                    
                    marker = L.marker([ac.lat, ac.lon], { icon: planeIcon }).addTo(this.flightMap);
                    marker.hexCode = ac.hex; // Store hex for lookup
                    if (ac.callsign) {
                        marker.bindTooltip(`<b>${ac.callsign}</b>`, {
                            permanent: true, direction: 'right', className: 'bg-transparent border-0 text-white shadow-none fs-6', offset: [10, 0]
                        });
                    }
                } else {
                    marker = L.circleMarker([ac.lat, ac.lon], {
                        radius: 3, fillColor: color, color: "transparent", weight: 0, opacity: 1, fillOpacity: 0.8
                    }).addTo(this.flightMap);
                    marker.hexCode = ac.hex;
                }
                
                marker.bindPopup(this.createPopup(ac, color));
                this.mapLayers.push(marker);

                // In non-live mode, clicking the marker can trigger the full path
                if (!isLive && isLatest) {
                    marker.on('click', () => {
                        const polyline = L.polyline(latlngs, {
                            color: color, weight: 3, opacity: 0.9, smoothFactor: 1
                        }).addTo(this.flightMap);
                        this.mapLayers.push(polyline);
                    });
                }
            });
        });

        if (bounds.length > 0) {
            this.flightMap.fitBounds(bounds, { padding: [30, 30] });
        }

        if (isLive) {
            this.updateLiveList(flightsByHex);
        }
    }

    calculateHeading(p1, p2) {
        const dy = p1.lon - p2.lon;
        const dx = p1.lat - p2.lat;
        return Math.atan2(dy, dx) * (180 / Math.PI);
    }

    createPopup(ac, color) {
        let timeStr = (ac.time || "").split(' ')[1] || "";
        // Search is much more robust than direct data links
        const fr24Url = `https://www.flightradar24.com/search?q=${ac.reg || ac.callsign || ac.hex}`;
        
        return `<div style="font-family:'Outfit',sans-serif; min-width: 200px;">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <strong style="font-size:1.1em;color:${color}">${ac.hex}</strong>
                        <a href="${fr24Url}" target="_blank" class="btn btn-sm btn-primary py-0 px-2" style="font-size: 0.75rem;">FR24 <i class="bi bi-box-arrow-up-right"></i></a>
                    </div>
                    ${ac.callsign ? `<b>Callsign:</b> <span class="text-primary fw-bold">${ac.callsign}</span><br>` : ''}
                    ${ac.reg ? `<b>Reg:</b> <span class="fw-bold">${ac.reg}</span><br>` : ''}
                    ${ac.model ? `<b>Model:</b> ${ac.model}<br>` : ''}
                    <hr class="my-2 opacity-25">
                    <div class="d-flex justify-content-between">
                        <span><b>Alt:</b> ${ac.alt} ft</span>
                        <span><b>Spd:</b> ${ac.speed} kts</span>
                    </div>
                    <small class="text-muted mt-2 d-block text-center"><i class="bi bi-clock me-1"></i>Last seen at ${timeStr}</small>
                </div>`;
    }

    focusAircraft(hex) {
        // Find the latest marker for this hex
        const markers = this.mapLayers.filter(l => l instanceof L.Marker || l instanceof L.CircleMarker);
        const hexMarkers = markers.filter(m => m.hexCode === hex);
        
        if (hexMarkers.length > 0) {
            // Find the one that is an actual Marker (the airplane icon)
            let target = hexMarkers.find(m => m instanceof L.Marker) || hexMarkers[0];
            this.flightMap.setView(target.getLatLng(), 12);
            target.openPopup();
        }
    }

    updateLiveList(flightsByHex) {
        const container = document.getElementById('liveAircraftList');
        if (!container) return;
        
        const hexes = Object.keys(flightsByHex);
        if (hexes.length === 0) {
            container.innerHTML = `<div class="text-muted text-center mt-5"><i class="bi bi-info-circle d-block fs-3 mb-2"></i>No active flights.</div>`;
            return;
        }

        let html = '<div class="list-group list-group-flush">';
        hexes.forEach((hex, idx) => {
            const ac = flightsByHex[hex][0];
            const color = this.colors[idx % this.colors.length];
            const fr24Url = `https://www.flightradar24.com/search?q=${ac.reg || ac.callsign || ac.hex}`;
            const callsign = ac.callsign 
                ? `<a href="${fr24Url}" target="_blank" class="fw-bold fs-5 text-primary text-decoration-none" onclick="event.stopPropagation();">${ac.callsign}</a>` 
                : `<span class="fw-bold fs-5 text-muted">UNKNOWN</span>`;
            const timeStr = (ac.time || "").split(' ')[1] || "";
            
            html += `
            <div class="list-group-item bg-transparent px-2 py-2 border-bottom border-secondary border-opacity-25" 
                 style="cursor: pointer;" onclick="dashboard.focusAircraft('${hex}')">
                <div class="d-flex w-100 justify-content-between align-items-center mb-1">
                    <div class="d-flex align-items-center">
                        <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:${color}; margin-right:8px;"></span>
                        ${callsign}
                    </div>
                    <div class="text-end">
                        <small class="text-muted d-block" style="font-size: 0.7rem;">Hex: ${ac.hex}</small>
                        <small class="text-muted" style="font-size:0.7rem;">${ac.speed||0}kts | ${ac.alt||0}ft</small>
                    </div>
                </div>
                <div class="d-flex justify-content-between ms-3">
                    <small class="text-muted text-truncate pe-2" style="max-width: 140px; font-size:0.75rem;">${ac.model || ac.reg || 'Unknown'}</small>
                    <small class="text-muted" style="font-size: 0.7rem;"><i class="bi bi-clock me-1"></i>${timeStr}</small>
                </div>
            </div>`;
        });
        container.innerHTML = html + '</div>';
    }

    fetchListOnly() {
        if (this.isLiveModeActive) return;
        fetch('/api/live_flights')
            .then(r => r.json())
            .then(data => {
                if (!data || data.error) return;
                const normalized = this.normalizeData(data);
                const flightsByHex = {};
                normalized.forEach(ac => {
                    if (!isNaN(ac.lat) && !isNaN(ac.lon)) {
                        if (!flightsByHex[ac.hex]) flightsByHex[ac.hex] = [];
                        flightsByHex[ac.hex].push(ac);
                    }
                });
                this.updateLiveList(flightsByHex);
            });
    }

    toggleLiveMode() {
        const btn = document.getElementById('liveViewToggle');
        if (this.liveMapInterval) {
            clearInterval(this.liveMapInterval);
            this.liveMapInterval = null;
            this.isLiveModeActive = false;
            btn.className = 'btn btn-outline-danger rounded-pill px-4 fw-bold';
            btn.innerHTML = '<i class="bi bi-record-circle me-1"></i> Live';
            this.updateMap(this.initialData, false);
            this.fetchListOnly();
        } else {
            this.isLiveModeActive = true;
            btn.className = 'btn btn-danger rounded-pill px-4 fw-bold';
            btn.innerHTML = '<i class="bi bi-broadcast me-1 pulse-icon"></i> Live Active';
            this.fetchLiveFlights();
            this.liveMapInterval = setInterval(() => this.fetchLiveFlights(), 5000);
        }
    }

    fetchLiveFlights() {
        fetch('/api/live_flights')
            .then(r => r.json())
            .then(data => { if (data && !data.error) this.updateMap(data, true); })
            .catch(e => console.error("Live fetch error", e));
    }

    initCharts() {
        // Shared chart settings
        Chart.defaults.font.family = "'Outfit', sans-serif";
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        Chart.defaults.color = isDark ? '#adb5bd' : '#6c757d';

        this.renderOperatorsChart();
        this.renderModelsChart();
        this.renderTimelineChart();
        this.renderScatterChart();
    }

    renderOperatorsChart() {
        const ctx = document.getElementById('operatorsChart').getContext('2d');
        const labels = this.summary.top_operators.map(o => o[0]);
        const data = this.summary.top_operators.map(o => o[1]);
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{ label: 'Aircraft', data: data, backgroundColor: '#667eea', borderRadius: 6 }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    renderModelsChart() {
        const ctx = document.getElementById('modelsChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: this.summary.top_models.map(m => m[0]),
                datasets: [{ data: this.summary.top_models.map(m => m[1]), backgroundColor: this.colors, borderWidth: 0 }]
            },
            options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'right' } } }
        });
    }

    renderTimelineChart() {
        const hourCounts = new Array(24).fill(0);
        this.initialData.forEach(ac => {
            const match = (ac.time || "").match(/ (\d{2}):/);
            if (match) hourCounts[parseInt(match[1], 10)]++;
        });
        
        const ctx = document.getElementById('timelineChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array.from({length: 24}, (_, i) => `${i.toString().padStart(2, '0')}:00`),
                datasets: [{ label: 'Activity', data: hourCounts, borderColor: '#4facfe', backgroundColor: 'rgba(79, 172, 254, 0.2)', fill: true, tension: 0.4 }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    renderScatterChart() {
        const stats = {};
        this.initialData.forEach(ac => {
            if (!stats[ac.hex]) stats[ac.hex] = { x: 0, y: 0, hex: ac.hex, model: ac.model };
            const s = parseFloat(ac.speed), a = parseFloat(ac.alt);
            if (!isNaN(s) && s > stats[ac.hex].x) stats[ac.hex].x = s;
            if (!isNaN(a) && a > stats[ac.hex].y) stats[ac.hex].y = a;
        });

        const ctx = document.getElementById('scatterChart').getContext('2d');
        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{ data: Object.values(stats).filter(s => s.x > 0 && s.y > 0), backgroundColor: 'rgba(255, 8, 68, 0.6)', borderColor: '#ff0844' }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, 
                plugins: { legend: { display: false } },
                scales: { x: { title: { display: true, text: 'Speed (kts)' } }, y: { title: { display: true, text: 'Alt (ft)' } } }
            }
        });
    }

    initTableFilters() {
        const searchInput = document.getElementById('tableSearch');
        if (searchInput) {
            searchInput.addEventListener('keyup', () => {
                const filter = searchInput.value.toUpperCase();
                const rows = document.querySelector("#historyTable tbody").rows;
                for (let i = 0; i < rows.length; i++) {
                    const text = rows[i].textContent.toUpperCase();
                    rows[i].style.display = text.includes(filter) ? "" : "none";
                }
            });
        }
    }

    initEventListeners() {
        const toggle = document.getElementById('liveViewToggle');
        if (toggle) toggle.onclick = () => this.toggleLiveMode();
        
        // Add global sort function
        window.sortTable = (n) => {
            const table = document.getElementById("historyTable");
            let rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
            switching = true;
            dir = "asc";
            while (switching) {
                switching = false;
                rows = table.rows;
                for (i = 1; i < (rows.length - 1); i++) {
                    shouldSwitch = false;
                    x = rows[i].getElementsByTagName("TD")[n];
                    y = rows[i + 1].getElementsByTagName("TD")[n];
                    if (dir == "asc") {
                        if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) {
                            shouldSwitch = true;
                            break;
                        }
                    } else if (dir == "desc") {
                        if (x.innerHTML.toLowerCase() < y.innerHTML.toLowerCase()) {
                            shouldSwitch = true;
                            break;
                        }
                    }
                }
                if (shouldSwitch) {
                    rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                    switching = true;
                    switchcount++;
                } else {
                    if (switchcount == 0 && dir == "asc") {
                        dir = "desc";
                        switching = true;
                    }
                }
            }
        };
    }
}
