#!/usr/bin/env python3
"""
Advanced Traffic-Eye Mission Control Dashboard
Real-time AI monitoring with comprehensive metrics and debug capabilities
"""

from flask import Flask, render_template_string, jsonify, Response, request
import subprocess
import psutil
import cv2
import sys
sys.path.insert(0, '/home/yashcs/traffic-eye')

from datetime import datetime
from collections import deque
import threading
import time
import json

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

# Global metrics storage
class MetricsTracker:
    def __init__(self, max_history=100):
        self.max_history = max_history
        self.detection_log = deque(maxlen=50)  # Last 50 detections
        self.inference_times = deque(maxlen=max_history)
        self.helmet_times = deque(maxlen=max_history)
        self.total_detections = 0
        self.fps_history = deque(maxlen=max_history)
        self.lock = threading.Lock()

    def add_detection(self, detection_data):
        with self.lock:
            self.detection_log.append(detection_data)
            self.total_detections += 1

    def add_inference_time(self, yolo_time, helmet_time):
        with self.lock:
            if yolo_time:
                self.inference_times.append(yolo_time)
            if helmet_time:
                self.helmet_times.append(helmet_time)

    def add_fps(self, fps):
        with self.lock:
            self.fps_history.append(fps)

    def get_metrics(self):
        with self.lock:
            return {
                'yolo_avg': sum(self.inference_times) / len(self.inference_times) if self.inference_times else 0,
                'yolo_max': max(self.inference_times) if self.inference_times else 0,
                'helmet_avg': sum(self.helmet_times) / len(self.helmet_times) if self.helmet_times else 0,
                'helmet_max': max(self.helmet_times) if self.helmet_times else 0,
                'fps_avg': sum(self.fps_history) / len(self.fps_history) if self.fps_history else 0,
                'total_detections': self.total_detections,
                'recent_detections': list(self.detection_log)[:10]  # Last 10
            }

metrics = MetricsTracker()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Traffic-Eye Mission Control</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Orbitron:wght@500;700;900&display=swap" rel="stylesheet">

    <style>
        :root {
            --bg-primary: #0a0e27;
            --bg-secondary: #12172e;
            --bg-tertiary: #1a1f3a;
            --accent-cyan: #00d9ff;
            --accent-yellow: #ffea00;
            --accent-red: #ff003c;
            --accent-green: #00ff88;
            --text-primary: #e4e9f7;
            --text-secondary: #8892b0;
            --text-dim: #495670;
            --border-glow: rgba(0, 217, 255, 0.3);
            --grid-size: 2px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }

        /* Animated grid background */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image:
                linear-gradient(var(--text-dim) var(--grid-size), transparent var(--grid-size)),
                linear-gradient(90deg, var(--text-dim) var(--grid-size), transparent var(--grid-size));
            background-size: 40px 40px;
            opacity: 0.03;
            z-index: 0;
            pointer-events: none;
        }

        .container {
            position: relative;
            z-index: 1;
            max-width: 1920px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            box-shadow: 0 0 30px rgba(0, 217, 255, 0.1);
            animation: slideDown 0.6s ease-out;
        }

        @keyframes slideDown {
            from { transform: translateY(-30px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .header h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 2rem;
            font-weight: 900;
            letter-spacing: 2px;
            text-transform: uppercase;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 20px rgba(0, 217, 255, 0.5));
        }

        .live-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 20px;
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid var(--accent-green);
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 1px;
            animation: pulse 2s infinite;
        }

        .live-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(0.95); }
        }

        /* Main Grid Layout */
        .dashboard-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }

        @media (max-width: 1400px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Card Component */
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--text-dim);
            border-radius: 4px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
            opacity: 0;
            transition: opacity 0.3s;
        }

        .card:hover::before {
            opacity: 1;
        }

        .card-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--accent-cyan);
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-title::before {
            content: '▶';
            color: var(--accent-yellow);
            font-size: 0.7rem;
        }

        /* Video Feed */
        .video-container {
            position: relative;
            width: 100%;
            background: #000;
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid var(--accent-cyan);
            box-shadow: 0 0 30px rgba(0, 217, 255, 0.2);
        }

        .video-feed {
            width: 100%;
            height: auto;
            display: block;
        }

        .video-overlay {
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(10, 14, 39, 0.9);
            padding: 10px 15px;
            border: 1px solid var(--accent-green);
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--accent-green);
            letter-spacing: 1px;
            backdrop-filter: blur(10px);
        }

        /* AI Pipeline Visualization */
        .pipeline {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            margin: 20px 0;
            padding: 20px;
            background: rgba(26, 31, 58, 0.5);
            border-radius: 4px;
            border: 1px dashed var(--text-dim);
        }

        .pipeline-stage {
            flex: 1;
            text-align: center;
            position: relative;
            padding: 15px 10px;
            background: var(--bg-tertiary);
            border: 1px solid var(--text-dim);
            border-radius: 4px;
            transition: all 0.3s;
        }

        .pipeline-stage.active {
            border-color: var(--accent-cyan);
            box-shadow: 0 0 15px rgba(0, 217, 255, 0.3);
            transform: scale(1.05);
        }

        .pipeline-stage::after {
            content: '→';
            position: absolute;
            right: -20px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-dim);
            font-size: 1.5rem;
        }

        .pipeline-stage:last-child::after {
            display: none;
        }

        .stage-name {
            font-size: 0.65rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }

        .stage-status {
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--accent-green);
        }

        .stage-time {
            font-size: 0.7rem;
            color: var(--text-dim);
            margin-top: 3px;
        }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .metric {
            background: var(--bg-tertiary);
            padding: 15px;
            border-radius: 4px;
            border-left: 3px solid var(--accent-cyan);
            transition: all 0.3s;
        }

        .metric:hover {
            transform: translateX(5px);
            border-left-color: var(--accent-yellow);
        }

        .metric-label {
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent-cyan);
            font-family: 'Orbitron', sans-serif;
        }

        .metric-unit {
            font-size: 0.8rem;
            color: var(--text-dim);
            margin-left: 4px;
        }

        .metric.warning .metric-value {
            color: var(--accent-yellow);
        }

        .metric.critical .metric-value {
            color: var(--accent-red);
            animation: flash 1s infinite;
        }

        @keyframes flash {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Detection Log */
        .detection-log {
            max-height: 400px;
            overflow-y: auto;
            background: var(--bg-tertiary);
            border-radius: 4px;
            padding: 10px;
        }

        .detection-log::-webkit-scrollbar {
            width: 8px;
        }

        .detection-log::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }

        .detection-log::-webkit-scrollbar-thumb {
            background: var(--accent-cyan);
            border-radius: 4px;
        }

        .log-entry {
            padding: 10px;
            margin-bottom: 8px;
            background: var(--bg-secondary);
            border-left: 3px solid var(--accent-green);
            border-radius: 2px;
            font-size: 0.75rem;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { transform: translateX(-20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .log-time {
            color: var(--text-dim);
            margin-right: 10px;
        }

        .log-class {
            color: var(--accent-yellow);
            font-weight: 700;
            margin-right: 10px;
        }

        .log-confidence {
            color: var(--accent-cyan);
        }

        .log-helmet {
            color: var(--accent-green);
            margin-left: 10px;
            font-weight: 700;
        }

        .log-no-helmet {
            color: var(--accent-red);
            margin-left: 10px;
            font-weight: 700;
        }

        /* Debug Toggle */
        .debug-toggle {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 1000;
        }

        .debug-btn {
            padding: 12px 24px;
            background: var(--accent-cyan);
            color: var(--bg-primary);
            border: none;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 0.8rem;
            letter-spacing: 1px;
            text-transform: uppercase;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0, 217, 255, 0.5);
            transition: all 0.3s;
        }

        .debug-btn:hover {
            background: var(--accent-yellow);
            box-shadow: 0 0 30px rgba(255, 234, 0, 0.6);
            transform: translateY(-2px);
        }

        .debug-btn.active {
            background: var(--accent-red);
        }

        /* Bottom Grid */
        .bottom-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        @media (max-width: 768px) {
            .bottom-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Legend */
        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 15px;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            font-size: 0.7rem;
            transition: all 0.3s;
        }

        .legend-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 2px;
            box-shadow: 0 0 8px currentColor;
        }

        /* Loading Animation */
        .loading {
            color: var(--text-dim);
            font-size: 0.9rem;
        }

        .loading::after {
            content: '...';
            animation: dots 1.5s infinite;
        }

        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60%, 100% { content: '...'; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>⬡ TRAFFIC-EYE Mission Control</h1>
            <div class="live-badge">
                <div class="live-dot"></div>
                <span>LIVE MONITORING</span>
            </div>
        </div>

        <!-- Main Dashboard Grid -->
        <div class="dashboard-grid">
            <!-- Left Column: Video + Pipeline -->
            <div>
                <!-- Video Feed -->
                <div class="card">
                    <div class="card-title">Live Camera Feed • 720p</div>
                    <div class="video-container">
                        <img class="video-feed" src="/video_feed" alt="Live camera feed">
                        <div class="video-overlay">
                            <span id="video-res">1280x720</span> • <span id="video-fps">--</span> FPS
                        </div>
                    </div>

                    <!-- Detection Legend -->
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

                <!-- AI Pipeline Visualization -->
                <div class="card" style="margin-top: 20px;">
                    <div class="card-title">AI Detection Pipeline</div>
                    <div class="pipeline">
                        <div class="pipeline-stage active" id="stage-capture">
                            <div class="stage-name">Frame Capture</div>
                            <div class="stage-status">ACTIVE</div>
                            <div class="stage-time" id="capture-time">--</div>
                        </div>
                        <div class="pipeline-stage active" id="stage-yolo">
                            <div class="stage-name">YOLO Detection</div>
                            <div class="stage-status" id="yolo-status">RUNNING</div>
                            <div class="stage-time" id="yolo-time">-- ms</div>
                        </div>
                        <div class="pipeline-stage active" id="stage-helmet">
                            <div class="stage-name">Helmet Classifier</div>
                            <div class="stage-status" id="helmet-status">RUNNING</div>
                            <div class="stage-time" id="helmet-time">-- ms</div>
                        </div>
                        <div class="pipeline-stage" id="stage-violation">
                            <div class="stage-name">Violation Check</div>
                            <div class="stage-status" id="violation-status">STANDBY</div>
                            <div class="stage-time" id="violation-time">--</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Column: Metrics + System -->
            <div>
                <!-- Performance Metrics -->
                <div class="card">
                    <div class="card-title">Performance Metrics</div>
                    <div class="metrics-grid">
                        <div class="metric">
                            <div class="metric-label">Camera FPS</div>
                            <div class="metric-value"><span id="camera-fps">--</span><span class="metric-unit">fps</span></div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Process FPS</div>
                            <div class="metric-value"><span id="process-fps">--</span><span class="metric-unit">fps</span></div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">YOLO Avg</div>
                            <div class="metric-value"><span id="yolo-avg">--</span><span class="metric-unit">ms</span></div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Helmet Avg</div>
                            <div class="metric-value"><span id="helmet-avg">--</span><span class="metric-unit">ms</span></div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Total Detections</div>
                            <div class="metric-value"><span id="total-detections">0</span><span class="metric-unit">objs</span></div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Frame Skip</div>
                            <div class="metric-value"><span id="frame-skip">--</span><span class="metric-unit">%</span></div>
                        </div>
                    </div>
                </div>

                <!-- System Health -->
                <div class="card" style="margin-top: 20px;">
                    <div class="card-title">System Health</div>
                    <div class="metrics-grid">
                        <div class="metric" id="cpu-metric">
                            <div class="metric-label">CPU Usage</div>
                            <div class="metric-value" id="cpu">--<span class="metric-unit">%</span></div>
                        </div>
                        <div class="metric" id="memory-metric">
                            <div class="metric-label">Memory</div>
                            <div class="metric-value" id="memory">--<span class="metric-unit">%</span></div>
                        </div>
                        <div class="metric" id="temp-metric">
                            <div class="metric-label">CPU Temp</div>
                            <div class="metric-value" id="temp">--<span class="metric-unit">°C</span></div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Disk Used</div>
                            <div class="metric-value" id="disk">--<span class="metric-unit">%</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Bottom Grid: Detection Log + Debug -->
        <div class="bottom-grid">
            <!-- Detection Log -->
            <div class="card">
                <div class="card-title">Recent Detections</div>
                <div class="detection-log" id="detection-log">
                    <div class="loading">Waiting for detections</div>
                </div>
            </div>

            <!-- AI Inference Details / Debug Panel -->
            <div class="card" id="inference-card">
                <div class="card-title">AI Inference Stats</div>
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-label">YOLO Peak</div>
                        <div class="metric-value"><span id="yolo-max">--</span><span class="metric-unit">ms</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Helmet Peak</div>
                        <div class="metric-value"><span id="helmet-max">--</span><span class="metric-unit">ms</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Total Latency</div>
                        <div class="metric-value"><span id="total-latency">--</span><span class="metric-unit">ms</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Det/Frame</div>
                        <div class="metric-value"><span id="det-per-frame">--</span><span class="metric-unit">avg</span></div>
                    </div>
                </div>
            </div>

            <!-- Gemini API Stats (Debug Mode) -->
            <div class="card" id="gemini-card" style="display: none;">
                <div class="card-title">🔮 Gemini API Usage</div>
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-label">Total Calls</div>
                        <div class="metric-value"><span id="gemini-calls">0</span><span class="metric-unit">req</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Success Rate</div>
                        <div class="metric-value"><span id="gemini-success">--</span><span class="metric-unit">%</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Total Tokens</div>
                        <div class="metric-value"><span id="gemini-tokens">0</span><span class="metric-unit">tok</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Avg Latency</div>
                        <div class="metric-value"><span id="gemini-latency">--</span><span class="metric-unit">ms</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Cache Hits</div>
                        <div class="metric-value"><span id="gemini-cache">0</span><span class="metric-unit">hits</span></div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Last Call</div>
                        <div class="metric-value"><span id="gemini-last" style="font-size: 0.7rem;">--</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Debug Mode Toggle -->
    <div class="debug-toggle">
        <button class="debug-btn" id="debug-btn" onclick="toggleDebug()">
            Debug Mode: OFF
        </button>
    </div>

    <script>
        let debugMode = false;

        function toggleDebug() {
            debugMode = !debugMode;
            const btn = document.getElementById('debug-btn');
            btn.textContent = `Debug Mode: ${debugMode ? 'ON' : 'OFF'}`;
            btn.classList.toggle('active', debugMode);

            // Send debug state to backend
            fetch('/api/debug/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: debugMode})
            });

            // Toggle Gemini panel visibility
            const geminiCard = document.getElementById('gemini-card');
            const inferenceCard = document.getElementById('inference-card');

            if (debugMode) {
                geminiCard.style.display = 'block';
                inferenceCard.style.display = 'none';
                updateGeminiStats();
            } else {
                geminiCard.style.display = 'none';
                inferenceCard.style.display = 'block';
            }
        }

        function updateGeminiStats() {
            if (!debugMode) return;

            fetch('/api/gemini/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('gemini-calls').textContent = data.total_calls;
                    document.getElementById('gemini-tokens').textContent = data.total_tokens;
                    document.getElementById('gemini-cache').textContent = data.cache_hits;
                    document.getElementById('gemini-latency').textContent = data.avg_latency_ms || '--';

                    // Calculate success rate
                    const successRate = data.total_calls > 0 ?
                        ((data.successful_calls / data.total_calls) * 100).toFixed(1) : '--';
                    document.getElementById('gemini-success').textContent = successRate;

                    // Format last call time
                    if (data.last_call) {
                        const lastCall = new Date(data.last_call).toLocaleTimeString();
                        document.getElementById('gemini-last').textContent = lastCall;
                    } else {
                        document.getElementById('gemini-last').textContent = 'Never';
                    }
                })
                .catch(err => console.error('Gemini stats error:', err));
        }

        // Update all metrics
        function updateDashboard() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    // Video metrics
                    document.getElementById('video-res').textContent = data.resolution || '1280x720';
                    document.getElementById('video-fps').textContent = data.fps || '--';

                    // System health
                    document.getElementById('cpu').textContent = data.cpu || '--';
                    document.getElementById('memory').textContent = data.memory || '--';
                    document.getElementById('temp').textContent = data.temp || '--';
                    document.getElementById('disk').textContent = data.disk || '--';

                    // Color coding for system health
                    updateMetricStatus('cpu-metric', data.cpu, 85, 95);
                    updateMetricStatus('memory-metric', data.memory, 80, 90);
                    updateMetricStatus('temp-metric', parseFloat(data.temp), 70, 80);
                })
                .catch(err => console.error('Status update error:', err));

            // Update AI metrics
            fetch('/api/metrics')
                .then(r => r.json())
                .then(data => {
                    // Performance - FPS
                    const cameraFps = data.fps_avg || 0;
                    const processFps = cameraFps > 0 ? Math.round(cameraFps / 5) : 0; // Every 5th frame
                    document.getElementById('camera-fps').textContent = Math.round(cameraFps);
                    document.getElementById('process-fps').textContent = processFps;

                    // Inference times
                    const yoloAvg = Math.round(data.yolo_avg) || 0;
                    const helmetAvg = Math.round(data.helmet_avg) || 0;
                    document.getElementById('yolo-avg').textContent = yoloAvg;
                    document.getElementById('helmet-avg').textContent = helmetAvg;

                    // Detections
                    document.getElementById('total-detections').textContent = data.total_detections || 0;

                    // Frame skip (calculated from process every 5th frame)
                    const frameSkip = cameraFps > 0 ? (((cameraFps - processFps) / cameraFps) * 100).toFixed(1) : 0;
                    document.getElementById('frame-skip').textContent = frameSkip;

                    // Pipeline times
                    document.getElementById('yolo-time').textContent = yoloAvg + ' ms';
                    document.getElementById('helmet-time').textContent = helmetAvg + ' ms';

                    // Inference stats
                    document.getElementById('yolo-max').textContent = Math.round(data.yolo_max) || '--';
                    document.getElementById('helmet-max').textContent = Math.round(data.helmet_max) || '--';
                    document.getElementById('total-latency').textContent = (yoloAvg + helmetAvg) || '--';

                    // Detections per frame
                    const detPerFrame = data.total_detections > 0 && processFps > 0 ?
                        (data.total_detections / (processFps * 60)).toFixed(1) : 0; // Assuming 60s window
                    document.getElementById('det-per-frame').textContent = detPerFrame;

                    // Update detection log
                    updateDetectionLog(data.recent_detections);
                })
                .catch(err => console.error('Metrics update error:', err));

            // Update Gemini stats if in debug mode
            if (debugMode) {
                updateGeminiStats();
            }
        }

        function updateMetricStatus(elementId, value, warningThreshold, criticalThreshold) {
            const elem = document.getElementById(elementId);
            elem.classList.remove('warning', 'critical');

            if (value > criticalThreshold) {
                elem.classList.add('critical');
            } else if (value > warningThreshold) {
                elem.classList.add('warning');
            }
        }

        function updateDetectionLog(detections) {
            const logContainer = document.getElementById('detection-log');
            if (!detections || detections.length === 0) return;

            logContainer.innerHTML = '';
            detections.forEach(det => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';

                const time = new Date(det.timestamp).toLocaleTimeString();
                const helmetStatus = det.helmet !== undefined ?
                    (det.helmet ? '<span class="log-helmet">✓ HELMET</span>' : '<span class="log-no-helmet">✗ NO HELMET</span>') : '';

                entry.innerHTML = `
                    <span class="log-time">${time}</span>
                    <span class="log-class">${det.class}</span>
                    <span class="log-confidence">${(det.confidence * 100).toFixed(1)}%</span>
                    ${helmetStatus}
                `;
                logContainer.appendChild(entry);
            });
        }

        // Auto-refresh every 2 seconds
        setInterval(updateDashboard, 2000);
        updateDashboard();

        // Initial load animation
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('.card').forEach((card, index) => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    card.style.transition = 'all 0.6s ease-out';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, index * 100);
            });
        });
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

@app.route('/api/metrics')
def api_metrics():
    """Return AI inference metrics and detection log."""
    # Track actual FPS
    metrics.add_fps(camera_streamer.fps)

    # Track actual detections
    if camera_streamer.current_detections:
        for det in camera_streamer.current_detections[-5:]:
            metrics.add_detection({
                'timestamp': datetime.now().isoformat(),
                'class': det.get('class_name', 'unknown'),
                'confidence': det.get('confidence', 0.0),
                'helmet': det.get('has_helmet', None)
            })

    # Track actual inference times
    if camera_streamer.yolo_inference_time > 0:
        metrics.add_inference_time(camera_streamer.yolo_inference_time, camera_streamer.helmet_inference_time)

    return jsonify(metrics.get_metrics())

@app.route('/api/debug/toggle', methods=['POST'])
def toggle_debug():
    """Toggle debug mode on/off."""
    data = json.loads(request.data) if request.data else {}
    camera_streamer.debug_mode = data.get('enabled', False)
    return jsonify({'debug_mode': camera_streamer.debug_mode})

@app.route('/api/gemini/stats')
def gemini_stats():
    """Return Gemini API usage statistics."""
    # TODO: Track actual Gemini API calls in cloud module
    # For now, return placeholder data
    return jsonify({
        'total_calls': 0,
        'successful_calls': 0,
        'failed_calls': 0,
        'total_tokens': 0,
        'cache_hits': 0,
        'avg_latency_ms': 0,
        'last_call': None,
        'quota_remaining': 'N/A'
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Traffic-Eye Mission Control Dashboard")
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
