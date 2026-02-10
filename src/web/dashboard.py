#!/usr/bin/env python3
"""
Simple web dashboard for monitoring Traffic-Eye in real-time.
Access from iPad via http://<tailscale-ip>:8080
"""

from flask import Flask, render_template_string, jsonify
import subprocess
import psutil
from pathlib import Path

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Traffic-Eye Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: #f0f0f0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #4CAF50;
            text-align: center;
        }
        .card {
            background: #2a2a2a;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .status {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
        }
        .status-item {
            flex: 1;
            min-width: 150px;
            margin: 10px;
            padding: 15px;
            background: #333;
            border-radius: 6px;
            text-align: center;
        }
        .status-value {
            font-size: 2em;
            font-weight: bold;
            color: #4CAF50;
        }
        .status-label {
            font-size: 0.9em;
            color: #aaa;
            margin-top: 5px;
        }
        .warning {
            color: #ff9800;
        }
        .error {
            color: #f44336;
        }
        .logs {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.85em;
            overflow-x: auto;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-line {
            margin: 2px 0;
            white-space: pre-wrap;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            margin: 5px;
        }
        button:hover {
            background: #45a049;
        }
        .btn-danger {
            background: #f44336;
        }
        .btn-danger:hover {
            background: #da190b;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚦 Traffic-Eye Field Testing Dashboard</h1>

        <div class="card">
            <h2>System Status</h2>
            <div class="status" id="status">
                <div class="status-item">
                    <div class="status-value" id="cpu">--</div>
                    <div class="status-label">CPU Usage</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="memory">--</div>
                    <div class="status-label">Memory</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="temp">--</div>
                    <div class="status-label">CPU Temp</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="disk">--</div>
                    <div class="status-label">Disk Used</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Traffic-Eye Service</h2>
            <div class="status">
                <div class="status-item">
                    <div class="status-value" id="service-status">--</div>
                    <div class="status-label">Service Status</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="uptime">--</div>
                    <div class="status-label">Uptime</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="detections">--</div>
                    <div class="status-label">Total Detections</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="violations">--</div>
                    <div class="status-label">Violations</div>
                </div>
            </div>
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="refreshLogs()">🔄 Refresh Logs</button>
                <button onclick="restartService()" class="btn-danger">♻️ Restart Service</button>
            </div>
        </div>

        <div class="card">
            <h2>Recent Logs <span style="font-size: 0.7em; color: #aaa;">(Last 50 lines)</span></h2>
            <div class="logs" id="logs">
                Loading logs...
            </div>
        </div>
    </div>

    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('cpu').innerText = data.cpu + '%';
                    document.getElementById('memory').innerText = data.memory + '%';
                    document.getElementById('temp').innerText = data.temp + '°C';
                    document.getElementById('disk').innerText = data.disk + '%';
                    document.getElementById('service-status').innerText = data.service_status;
                    document.getElementById('uptime').innerText = data.uptime;
                    document.getElementById('detections').innerText = data.detections || '--';
                    document.getElementById('violations').innerText = data.violations || '--';

                    // Color coding
                    if (parseFloat(data.temp) > 80) {
                        document.getElementById('temp').className = 'status-value error';
                    } else if (parseFloat(data.temp) > 70) {
                        document.getElementById('temp').className = 'status-value warning';
                    }

                    if (data.service_status !== 'active') {
                        document.getElementById('service-status').className = 'status-value error';
                    } else {
                        document.getElementById('service-status').className = 'status-value';
                    }
                });
        }

        function refreshLogs() {
            fetch('/api/logs')
                .then(r => r.json())
                .then(data => {
                    const logsDiv = document.getElementById('logs');
                    logsDiv.innerHTML = data.logs.map(line =>
                        `<div class="log-line">${line}</div>`
                    ).join('');
                    logsDiv.scrollTop = logsDiv.scrollHeight;
                });
        }

        function restartService() {
            if (confirm('Restart Traffic-Eye service?')) {
                fetch('/api/restart', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => alert(data.message));
            }
        }

        // Auto-refresh every 2 seconds
        setInterval(updateStatus, 2000);
        setInterval(refreshLogs, 5000);

        // Initial load
        updateStatus();
        refreshLogs();
    </script>
</body>
</html>
"""

def get_cpu_temp():
    """Get CPU temperature."""
    try:
        result = subprocess.run(['vcgencmd', 'measure_temp'],
                                capture_output=True, text=True, timeout=2)
        temp = result.stdout.strip().split('=')[1].split("'")[0]
        return temp
    except Exception:
        return "N/A"

def get_service_status():
    """Check systemd service status."""
    try:
        result = subprocess.run(['systemctl', 'is-active', 'traffic-eye-field'],
                                capture_output=True, text=True, timeout=2)
        return result.stdout.strip()
    except Exception:
        return "unknown"

def get_service_uptime():
    """Get service uptime."""
    try:
        result = subprocess.run(['systemctl', 'show', 'traffic-eye-field',
                                 '--property=ActiveEnterTimestamp'],
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            timestamp_line = result.stdout.strip()
            # Parse format like: ActiveEnterTimestamp=Sun 2026-02-09 12:34:56 IST
            if '=' in timestamp_line:
                return "Running"
        return "N/A"
    except Exception:
        return "N/A"

def get_logs():
    """Get recent service logs."""
    try:
        result = subprocess.run(['journalctl', '-u', 'traffic-eye-field',
                                 '-n', '50', '--no-pager'],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip().split('\n')
    except Exception:
        return ["Error fetching logs"]

def get_db_stats():
    """Get detection counts from database."""
    try:
        db_path = Path('/home/yashcs/traffic-eye/data/traffic_eye.db')
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Count detections
            cursor.execute("SELECT COUNT(*) FROM violations")
            violations = cursor.fetchone()[0]

            conn.close()
            return {'violations': violations, 'detections': violations}
        return {'violations': 0, 'detections': 0}
    except Exception:
        return {'violations': 0, 'detections': 0}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def api_status():
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    temp = get_cpu_temp()
    service_status = get_service_status()
    uptime = get_service_uptime()
    db_stats = get_db_stats()

    return jsonify({
        'cpu': round(cpu, 1),
        'memory': round(memory, 1),
        'disk': round(disk, 1),
        'temp': temp,
        'service_status': service_status,
        'uptime': uptime,
        'detections': db_stats['detections'],
        'violations': db_stats['violations'],
    })

@app.route('/api/logs')
def api_logs():
    logs = get_logs()
    return jsonify({'logs': logs})

@app.route('/api/restart', methods=['POST'])
def api_restart():
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'traffic-eye-field'],
                       timeout=5)
        return jsonify({'message': 'Service restart initiated'})
    except Exception as e:
        return jsonify({'message': f'Error: {str(e)}'}), 500

if __name__ == '__main__':
    print("Starting Traffic-Eye Dashboard on http://0.0.0.0:8080")
    print("Access from iPad via: http://<tailscale-ip>:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
