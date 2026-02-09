# USB Webcam Deployment Summary

## Camera Hardware

**Camera Model**: SNAP U2 USB Webcam
**Connection**: USB (connected to USB port)
**Driver**: Video4Linux2 (V4L2)
**Device Path**: `/dev/video1` (main device), `/dev/video2` (metadata device)

## Configuration

The system has been updated to work with the USB webcam:

```yaml
camera:
  resolution: [640, 480]  # Standard resolution for USB webcam
  fps: 15                  # Stable FPS for USB webcam
  process_every_nth_frame: 3  # Process every 3rd frame
  type: "usb"             # Force USB camera (skip Pi Camera detection)
```

### Why These Settings?

- **640x480 resolution**: Standard resolution supported by most USB webcams
- **15 FPS**: Reduces CPU load while maintaining smooth detection
- **Process every 3rd frame**: Effective detection rate of ~5 FPS, balancing accuracy and performance
- **type: "usb"**: Forces OpenCV VideoCapture and skips Picamera2 initialization

## Current Status

✅ **Camera**: USB Webcam (SNAP U2) detected on /dev/video1 and streaming at 640x480
✅ **Dashboard**: Running on http://100.107.114.5:8080
✅ **YOLO Detection**: Active with INT8 quantized YOLOv8n model
✅ **Helmet Classifier**: Active with Float16 MobileNetV3 model
✅ **Auto-start**: Enabled via systemd service
✅ **System Health**: CPU ~58°C, no current throttling

## Access Points

- **Local**: http://localhost:8080
- **Network**: http://192.168.68.63:8080
- **Tailscale VPN**: http://100.107.114.5:8080

## System Architecture

```
USB Webcam (SNAP U2)
    ↓
OpenCV VideoCapture (/dev/video1 via V4L2)
    ↓
CameraStreamer (background thread)
    ↓
YOLOv8n TFLite Detector (640x480 input)
    ↓
Helmet Classifier (96x96 head crops)
    ↓
Flask Dashboard (MJPEG stream on port 8080)
```

## Service Management

```bash
# View live logs
sudo journalctl -u traffic-eye-dashboard -f

# Restart service
sudo systemctl restart traffic-eye-dashboard

# Stop service
sudo systemctl stop traffic-eye-dashboard

# Check status
sudo systemctl status traffic-eye-dashboard

# Disable auto-start
sudo systemctl disable traffic-eye-dashboard

# Re-enable auto-start
sudo systemctl enable traffic-eye-dashboard
```

## Verification

Run the verification script to check all components:

```bash
# Comprehensive USB webcam verification
bash scripts/verify_webcam_deployment.sh

# Quick camera test
python scripts/test_webcam.py

# Original verification script (legacy)
bash scripts/verify_camera_deployment.sh
```

## Performance Metrics

- **Camera FPS**: 15 (native capture)
- **Detection FPS**: ~5 (every 3rd frame processed)
- **YOLO Inference Time**: ~150-200ms per frame
- **Helmet Classification**: ~71ms per detection
- **CPU Usage**: ~70-80% (normal during active detection)
- **Memory Usage**: ~27% (1GB out of 4GB)

## Detection Classes

The system detects and tracks:

- 🟢 **Person** (Green)
- 🟠 **Motorcycle** (Orange)
- 🔵 **Car** (Light Blue)
- 🟣 **Truck** (Magenta)
- 🟡 **Bus** (Yellow)
- 🔵 **Bicycle** (Cyan)
- 🔴 **Traffic Light** (Red)

## Code Changes Made

### 1. Updated Configuration (`config/settings.yaml`)
- Changed resolution from 1280x720 to 640x480
- Reduced FPS from 30 to 15
- Adjusted frame processing interval

### 2. No Code Changes Required
The existing code automatically detects and uses the OV5647 camera via:
- `src/web/camera_streamer.py`: Auto-detects Picamera2
- `src/capture/camera.py`: PiCamera class with libcamera backend
- `src/platform_factory.py`: Platform detection factory pattern

## Power Supply Warning

The system showed past undervoltage events (throttling code 0x50005):
- Bit 0x1: Under-voltage detected (past)
- Bit 0x4: ARM frequency capped (past)
- Bit 0x10000: Under-voltage since boot
- Bit 0x40000: Frequency capping since boot

**Recommendation**: Use a quality 5V/3A power supply to prevent:
- SD card corruption
- System instability
- Performance throttling
- Camera initialization failures

## Troubleshooting

### Camera Not Detected

```bash
# Check camera cable connection
libcamera-hello --list-cameras

# Check video devices
ls -l /dev/video*

# Check kernel logs
dmesg | grep -i ov5647
```

### Dashboard Not Streaming

```bash
# Check if camera is in use
ps aux | grep picamera

# Test camera manually
python3 -c "from picamera2 import Picamera2; cam = Picamera2(); print('OK')"

# Check service logs
sudo journalctl -u traffic-eye-dashboard -n 100
```

### High CPU Usage

If CPU usage exceeds 90%:
1. Increase `process_every_nth_frame` (e.g., 5 or 7)
2. Lower FPS (e.g., 10)
3. Reduce resolution (already optimized at 640x480)

### Memory Issues

If memory exceeds 80%:
1. Restart the service
2. Check for memory leaks in logs
3. Reduce buffer sizes

## Field Testing

The system is ready for field testing:

1. ✅ Camera configured for optimal performance
2. ✅ Dashboard auto-starts on boot
3. ✅ Real-time YOLO detection with overlay
4. ✅ Helmet classification for persons on motorcycles
5. ✅ Remote access via Tailscale
6. ✅ System health monitoring

## Next Steps

For production deployment:

1. **Test Detection Accuracy**: Place camera at traffic location and verify detection quality
2. **Monitor Temperature**: Check thermal performance over 1-2 hours
3. **Verify Power Supply**: Ensure stable power with `vcgencmd get_throttled` (should be 0x0)
4. **Adjust Frame Processing**: If CPU too high, increase `process_every_nth_frame`
5. **Test Different Times**: Day/night, different lighting conditions

## Camera Specifications (OV5647)

- **Sensor**: OmniVision OV5647
- **Resolution**: 5MP (2592×1944)
- **Video**: 1080p30, 720p60, VGA90
- **Interface**: CSI (Camera Serial Interface)
- **Field of View**: 54° x 41° (diagonal 65°)
- **Focus**: Fixed focus (1m to infinity)
- **Compatible**: All Raspberry Pi models with CSI port

## Deployment Date

**Deployed**: February 10, 2026, 01:10 IST
**System**: Raspberry Pi 4 (4GB RAM)
**OS**: Raspberry Pi OS (64-bit)
**Python**: 3.13
**Dashboard URL**: http://100.107.114.5:8080
