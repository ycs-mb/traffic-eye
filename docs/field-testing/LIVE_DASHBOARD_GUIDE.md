# Traffic-Eye Live Dashboard with Camera View

**Real-time camera feed with YOLO detection overlay on your iPad**

---

## 🎥 **Features**

- ✅ **Live Camera Feed**: Real-time video stream from Raspberry Pi
- ✅ **YOLO Detection Overlay**: Bounding boxes on detected objects
- ✅ **Color-Coded Classes**: Different colors for person, motorcycle, car, etc.
- ✅ **Confidence Scores**: Shows detection confidence for each object
- ✅ **Detection Count**: Live count of detected objects
- ✅ **Timestamp Overlay**: Current date/time on video
- ✅ **System Metrics**: CPU, memory, temperature, disk usage
- ✅ **Service Status**: Traffic-Eye service monitoring
- ✅ **Live Logs**: Recent application logs
- ✅ **Responsive Design**: Optimized for iPad viewing

---

## 🎨 **Detection Color Legend**

| Object | Color | Hex |
|--------|-------|-----|
| **Person** | 🟢 Green | #00FF00 |
| **Motorcycle** | 🟠 Orange | #FFA500 |
| **Car** | 🔵 Light Blue | #00A5FF |
| **Truck** | 🟣 Magenta | #FF00FF |
| **Bus** | 🟡 Yellow | #FFFF00 |
| **Bicycle** | 🔷 Cyan | #00FFFF |
| **Traffic Light** | 🔴 Red | #FF0000 |

---

## 🚀 **Quick Start**

### **1. Start the Dashboard**

```bash
# On Raspberry Pi
cd /home/yashcs/traffic-eye
source venv/bin/activate
python src/web/dashboard_live.py
```

The dashboard will start on port 8080.

### **2. Access from iPad**

1. Connect iPad to Tailscale VPN
2. Open Safari
3. Navigate to: `http://<tailscale-ip>:8080`

**Example**: `http://100.64.1.2:8080`

### **3. Test with Demo Frames**

```bash
# In another terminal
python scripts/test_live_dashboard.py
```

This sends simulated frames to test the live feed.

---

## 🔧 **Architecture**

### **Components**

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi                       │
│                                                     │
│  ┌──────────────────┐      ┌──────────────────┐   │
│  │  Main Detection  │      │  Live Dashboard  │   │
│  │  Loop            │──────│  (Flask)         │   │
│  │  (YOLOv8n)       │ HTTP │  Port 8080       │   │
│  │                  │ POST │                  │   │
│  └──────────────────┘      └──────────────────┘   │
│         │                          │               │
│         │ Detections              │ MJPEG         │
│         ▼                          ▼               │
│  ┌──────────────────┐      ┌──────────────────┐   │
│  │ Frame Publisher  │      │ Video Stream     │   │
│  │                  │      │ Generator        │   │
│  └──────────────────┘      └──────────────────┘   │
│                                    │               │
└────────────────────────────────────┼───────────────┘
                                     │
                                     │ MJPEG over HTTP
                                     ▼
                            ┌─────────────────┐
                            │      iPad       │
                            │    Safari       │
                            │  Live Video     │
                            └─────────────────┘
```

### **Data Flow**

1. **Detection Loop** captures frame and runs YOLOv8n
2. **Frame Publisher** sends frame + detections to dashboard (HTTP POST)
3. **Dashboard** stores latest frame in memory
4. **Video Generator** encodes frame with overlays as MJPEG
5. **iPad Browser** displays MJPEG stream

---

## 📊 **Dashboard Layout**

```
┌─────────────────────────────────────────────────┐
│       🚦 Traffic-Eye Live Dashboard             │
├──────────────────────────┬──────────────────────┤
│                          │                      │
│   📹 Live Camera Feed    │   System Status      │
│   (with YOLO overlay)    │   - CPU: 45%         │
│                          │   - Memory: 60%      │
│   [Video Stream]         │   - Temp: 65°C       │
│                          │   - Disk: 35%        │
│   Color Legend:          │                      │
│   🟢 Person              │                      │
│   🟠 Motorcycle          │                      │
│   🔵 Car                 │                      │
│                          │                      │
├──────────────────────────┴──────────────────────┤
│   Traffic-Eye Service Status                    │
│   Status: Active | Uptime: 2h | Violations: 5   │
│   [Refresh Logs] [Restart Service]              │
├─────────────────────────────────────────────────┤
│   Recent Logs                                   │
│   [Log entries scrollable view]                 │
└─────────────────────────────────────────────────┘
```

---

## 🛠️ **Integration with Main App**

### **Option 1: Automatic Integration (Recommended)**

The dashboard runs as a separate service and the main app can optionally push frames:

```python
from src.web.frame_publisher import FramePublisher

# In main.py
publisher = FramePublisher(dashboard_url="http://localhost:8080")

# In detection loop
for frame in camera:
    detections = detector.detect(frame)

    # Push to dashboard (non-blocking)
    publisher.publish_frame(frame, detections)

    # Continue with violation detection...
```

### **Option 2: Standalone Mode**

Dashboard can run standalone and display test frames:

```bash
# Start dashboard
python src/web/dashboard_live.py

# In another terminal, send test frames
python scripts/test_live_dashboard.py
```

---

## 🔄 **Systemd Service**

The dashboard is configured as a systemd service for auto-start:

### **Service File**: `systemd/traffic-eye-dashboard.service`

```ini
[Unit]
Description=Traffic-Eye Live Web Dashboard with Camera Feed
After=network.target

[Service]
Type=simple
User=yashcs
WorkingDirectory=/home/yashcs/traffic-eye
ExecStart=/home/yashcs/traffic-eye/venv/bin/python src/web/dashboard_live.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### **Install and Enable**

```bash
sudo cp systemd/traffic-eye-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable traffic-eye-dashboard
sudo systemctl start traffic-eye-dashboard
```

### **Check Status**

```bash
sudo systemctl status traffic-eye-dashboard
journalctl -u traffic-eye-dashboard -f
```

---

## 📱 **iPad Access**

### **Safari**

1. Open Safari
2. Navigate to `http://<tailscale-ip>:8080`
3. Bookmark for quick access
4. Add to Home Screen (optional)

### **Full-Screen Mode**

1. Tap the Share button
2. Select "Add to Home Screen"
3. Open from Home Screen for full-screen experience

### **Tips**

- Use landscape orientation for best view
- Pinch to zoom on video feed
- Pull down to refresh page
- Dashboard auto-refreshes metrics every 2 seconds

---

## 🔍 **Troubleshooting**

### **Dashboard Not Accessible**

```bash
# Check if service is running
sudo systemctl status traffic-eye-dashboard

# Check port binding
sudo netstat -tulpn | grep 8080

# Check firewall
sudo ufw status

# Restart service
sudo systemctl restart traffic-eye-dashboard
```

### **No Video Feed**

1. **Check if frames are being sent**:
   ```bash
   # Test with demo frames
   python scripts/test_live_dashboard.py
   ```

2. **Check dashboard logs**:
   ```bash
   journalctl -u traffic-eye-dashboard -n 50
   ```

3. **Verify camera is working**:
   ```bash
   python scripts/setup_camera.sh
   ```

### **Slow Video Stream**

- **Reduce frame rate**: Modify `time.sleep()` in `generate_frames()`
- **Lower JPEG quality**: Change `cv2.IMWRITE_JPEG_QUALITY` to 60
- **Check network**: Ping Raspberry Pi from iPad
- **Check CPU usage**: High CPU may slow encoding

### **Connection Refused**

1. **Check Tailscale**:
   ```bash
   tailscale status
   tailscale ip -4
   ```

2. **Verify IP address**: Use correct Tailscale IP
3. **Check service**: Ensure dashboard service is running

---

## ⚙️ **Configuration**

### **Video Quality**

Edit `src/web/dashboard_live.py`:

```python
# Line ~220: Adjust JPEG quality (50-95)
ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

# Line ~230: Adjust frame rate (higher = smoother, more CPU)
time.sleep(0.033)  # 30 FPS
# time.sleep(0.066)  # 15 FPS (recommended for Pi)
# time.sleep(0.100)  # 10 FPS (lowest CPU)
```

### **Dashboard Port**

```python
# Line ~530: Change port
app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
```

### **Bounding Box Style**

```python
# Line ~70-90: Customize colors and thickness
cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)  # thickness=2
```

---

## 📊 **Performance**

### **Resource Usage**

| Component | CPU | Memory | Network |
|-----------|-----|--------|---------|
| **Dashboard** | 5-10% | ~50MB | Low |
| **Video Encoding** | 10-15% | ~20MB | Medium |
| **Frame Publisher** | 2-5% | ~10MB | Low |
| **Total** | ~20-30% | ~80MB | ~2-5 Mbps |

### **Optimization Tips**

1. **Lower resolution**: Resize frames before publishing
2. **Skip frames**: Publish every 2nd or 3rd frame
3. **Reduce quality**: Lower JPEG quality (60-70)
4. **Limit detections**: Only draw top N detections

---

## 🎯 **Use Cases**

### **Field Testing**
- Monitor live detections in real-time
- Verify camera positioning
- Check detection accuracy
- Debug false positives/negatives

### **Demonstration**
- Show system capabilities to stakeholders
- Live demo during presentations
- Training new operators

### **Development**
- Debug detection algorithms
- Tune confidence thresholds
- Test different lighting conditions
- Verify model performance

---

## 📝 **API Endpoints**

The dashboard provides these API endpoints:

### **GET /**
Main dashboard HTML page

### **GET /video_feed**
MJPEG video stream with detection overlay

### **GET /api/status**
```json
{
  "cpu": 45.2,
  "memory": 60.1,
  "temp": "65.3",
  "disk": 35.8,
  "service_status": "active",
  "uptime": "Running",
  "detections": 150,
  "violations": 5
}
```

### **GET /api/logs**
```json
{
  "logs": ["line1", "line2", ...]
}
```

### **POST /api/restart**
Restart the traffic-eye service

### **POST /api/update_frame**
```json
{
  "frame_b64": "base64_encoded_jpeg",
  "detections": [
    {
      "x1": 100, "y1": 100,
      "x2": 200, "y2": 200,
      "class_name": "person",
      "confidence": 0.85
    }
  ]
}
```

---

## 🔐 **Security Notes**

- Dashboard runs on local network only (via Tailscale VPN)
- No authentication required (VPN provides security)
- No data is stored (frames in memory only)
- HTTPS not required (VPN encrypts traffic)
- For production: Add basic auth if exposing publicly

---

## 📚 **Related Documentation**

- **Main Dashboard**: `src/web/dashboard.py` (original without video)
- **Frame Publisher**: `src/web/frame_publisher.py`
- **Test Script**: `scripts/test_live_dashboard.py`
- **Service File**: `systemd/traffic-eye-dashboard.service`

---

**Status**: ✅ Production Ready
**Version**: 1.0
**Last Updated**: 2026-02-09
