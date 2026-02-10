#!/usr/bin/env python3
"""
Live dashboard with Pi Camera feed and real-time YOLO detection.
Access from iPad via http://<tailscale-ip>:8080
"""

from flask import Flask, render_template_string, jsonify, Response
import subprocess
import psutil
import cv2
import sys
sys.path.insert(0, '/home/yashcs/traffic-eye')

import time

# Import detection components
from src.platform_factory import create_detector, create_helmet_classifier
from src.config import load_config
from src.web.camera_streamer import CameraStreamer

app = Flask(__name__)

# Initialize components
print("Loading configuration...")
config = load_config("config")

print("Loading YOLO detector...")
detector = create_detector(config)

print("Loading helmet classifier...")
helmet_classifier = create_helmet_classifier(config)

# Initialize camera streamer with camera type from config
camera_streamer = CameraStreamer(
    detector=detector,
    helmet_classifier=helmet_classifier,
    camera_type=config.camera.type
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Traffic-Eye Live Camera</title>
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
        .live-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            background: #4CAF50;
            border-radius: 50%;
            animation: pulse 2s infinite;
            margin-right: 5px;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
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
        <h1>🎥 Traffic-Eye Live Camera Feed</h1>

        <div class="grid-layout">
            <!-- Live Video Feed -->
            <div>
                <div class="card">
                    <h2>📹 Pi Camera with YOLO Detection</h2>
                    <div class="video-container">
                        <img class="video-feed" src="/video_feed" alt="Live camera feed">
                        <div class="video-overlay">
                            <span class="live-indicator"></span>LIVE
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

                    // Color coding
                    if (parseFloat(data.temp) > 80) {
                        document.getElementById('temp').className = 'status-value error';
                    } else if (parseFloat(data.temp) > 70) {
                        document.getElementById('temp').className = 'status-value warning';
                    } else {
                        document.getElementById('temp').className = 'status-value';
                    }
                })
                .catch(err => console.error('Status update error:', err));
        }

        // Auto-refresh every 2 seconds
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
"""

def generate_frames():
    """Generator function for MJPEG streaming from live camera."""
    while True:
        try:
            frame = camera_streamer.get_frame_with_overlay()

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

            # Yield frame in MJPEG format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            time.sleep(0.033)  # ~30 FPS max

        except Exception as e:
            print(f"Frame generation error: {e}")
            time.sleep(0.1)

def get_cpu_temp():
    """Get CPU temperature."""
    try:
        result = subprocess.run(['vcgencmd', 'measure_temp'],
                                capture_output=True, text=True, timeout=2)
        temp = result.stdout.strip().split('=')[1].split("'")[0]
        return temp
    except Exception:
        return "N/A"

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Returns MJPEG stream from live camera."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status')
def api_status():
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    temp = get_cpu_temp()

    # Get current frame resolution
    frame_resolution = "N/A"
    if camera_streamer.current_frame is not None:
        h, w = camera_streamer.current_frame.shape[:2]
        frame_resolution = f"{w}x{h}"

    return jsonify({
        'cpu': round(cpu, 1),
        'memory': round(memory, 1),
        'disk': round(disk, 1),
        'temp': temp,
        'resolution': frame_resolution,
        'fps': camera_streamer.fps,
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Traffic-Eye Live Camera Dashboard")
    print("="*60)
    print("\n✅ Starting camera streamer...")

    # Start camera in background
    camera_streamer.start()
    time.sleep(2)  # Give camera time to initialize

    print("✅ Dashboard starting on http://0.0.0.0:8080")
    print("✅ Access from iPad: http://100.107.114.5:8080")
    print("\nPress Ctrl+C to stop\n")

    try:
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\nStopping camera streamer...")
        camera_streamer.stop()
        print("✅ Stopped")
