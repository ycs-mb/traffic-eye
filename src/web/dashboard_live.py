#!/usr/bin/env python3
"""
Enhanced web dashboard with live camera view and YOLO detection overlay.
Access from iPad via http://<tailscale-ip>:8080
"""

from flask import Flask, render_template_string, jsonify, Response
import subprocess
import psutil
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
import threading
import time

app = Flask(__name__)

# Shared state for live video streaming
class VideoStream:
    def __init__(self):
        self.frame = None
        self.detections = []
        self.lock = threading.Lock()
        self.last_update = time.time()

    def update(self, frame, detections=None):
        """Update the current frame and detections."""
        with self.lock:
            self.frame = frame.copy() if frame is not None else None
            self.detections = detections or []
            self.last_update = time.time()

    def get_frame(self):
        """Get the current frame with detections drawn."""
        with self.lock:
            if self.frame is None:
                # Return a placeholder frame
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "No camera feed", (180, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                return placeholder

            frame_copy = self.frame.copy()

            # Draw bounding boxes for detections
            for det in self.detections:
                x1, y1, x2, y2 = int(det['x1']), int(det['y1']), int(det['x2']), int(det['y2'])
                class_name = det.get('class_name', 'unknown')
                confidence = det.get('confidence', 0.0)

                # Color coding by class
                colors = {
                    'person': (0, 255, 0),      # Green
                    'motorcycle': (255, 165, 0), # Orange
                    'car': (0, 165, 255),       # Light blue
                    'truck': (255, 0, 255),     # Magenta
                    'bus': (255, 255, 0),       # Yellow
                    'bicycle': (0, 255, 255),   # Cyan
                    'traffic light': (255, 0, 0) # Red
                }
                color = colors.get(class_name, (255, 255, 255))

                # Draw bounding box
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)

                # Draw label background
                label = f"{class_name} {confidence:.2f}"
                (label_w, label_h), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                cv2.rectangle(frame_copy, (x1, y1 - label_h - 10),
                             (x1 + label_w, y1), color, -1)

                # Draw label text
                cv2.putText(frame_copy, label, (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Add timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame_copy, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Add detection count
            det_count = f"Detections: {len(self.detections)}"
            cv2.putText(frame_copy, det_count, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            return frame_copy

video_stream = VideoStream()

# Load frames from the latest capture directory if available
def load_test_frame():
    """Load a test frame from captures directory."""
    captures_dir = Path('/home/yashcs/traffic-eye/data/captures')
    if captures_dir.exists():
        captures = sorted(captures_dir.glob('*.jpg'))
        if captures:
            return cv2.imread(str(captures[-1]))
    return None

# Initialize with a test frame if available
test_frame = load_test_frame()
if test_frame is not None:
    # Add some mock detections for demo
    h, w = test_frame.shape[:2]
    mock_detections = [
        {'x1': w//4, 'y1': h//4, 'x2': w//2, 'y2': h//2,
         'class_name': 'person', 'confidence': 0.85},
        {'x1': w//2, 'y1': h//3, 'x2': 3*w//4, 'y2': 2*h//3,
         'class_name': 'motorcycle', 'confidence': 0.92}
    ]
    video_stream.update(test_frame, mock_detections)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Traffic-Eye Live Dashboard</title>
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
            max-width: 1400px;
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
        .video-container {
            position: relative;
            width: 100%;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
        }
        .video-feed {
            width: 100%;
            height: auto;
            display: block;
        }
        .video-overlay {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.7);
            padding: 10px;
            border-radius: 4px;
            font-size: 0.9em;
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
        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 10px;
            font-size: 0.85em;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 3px;
        }
        .grid-layout {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 15px;
        }
        @media (max-width: 968px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚦 Traffic-Eye Live Dashboard</h1>

        <div class="grid-layout">
            <!-- Live Video Feed -->
            <div>
                <div class="card">
                    <h2>📹 Live Camera Feed</h2>
                    <div class="video-container">
                        <img class="video-feed" src="/video_feed" alt="Live camera feed">
                        <div class="video-overlay">
                            <div>🟢 LIVE</div>
                        </div>
                    </div>

                    <div class="legend">
                        <div class="legend-item">
                            <div class="legend-color" style="background: #00ff00;"></div>
                            <span>Person</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #ffa500;"></div>
                            <span>Motorcycle</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #00a5ff;"></div>
                            <span>Car</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #ff00ff;"></div>
                            <span>Truck</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #ffff00;"></div>
                            <span>Bus</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #00ffff;"></div>
                            <span>Bicycle</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #ff0000;"></div>
                            <span>Traffic Light</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- System Status -->
            <div>
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

def generate_frames():
    """Generator function for MJPEG streaming."""
    while True:
        frame = video_stream.get_frame()

        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        time.sleep(0.033)  # ~30 FPS

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

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Returns MJPEG stream."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

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

@app.route('/api/update_frame', methods=['POST'])
def api_update_frame():
    """API endpoint for main app to push frames and detections."""
    try:
        from flask import request
        data = request.get_json()

        # Decode base64 frame if provided
        if 'frame_b64' in data:
            import base64
            frame_bytes = base64.b64decode(data['frame_b64'])
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            video_stream.update(frame, data.get('detections', []))
            return jsonify({'status': 'ok'})

        return jsonify({'status': 'no frame'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Traffic-Eye Live Dashboard on http://0.0.0.0:8080")
    print("Access from iPad via: http://<tailscale-ip>:8080")
    print("Video feed with YOLO detection overlay enabled")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
