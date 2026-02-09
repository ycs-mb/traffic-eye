# Traffic-Eye Deployment Status

**Date**: 2026-02-10 01:28 IST
**Status**: ✅ **OPERATIONAL**

## System Overview

### Hardware
- **Platform**: Raspberry Pi 4 (4GB RAM, ARM64)
- **Camera**: USB Webcam (SNAP U2) on `/dev/video1`
- **Connection**: USB port
- **Network**: Tailscale VPN (100.107.114.5)

### Software Stack
- **OS**: Raspberry Pi OS (Debian-based, Linux 6.12.47)
- **Python**: 3.13.5 (virtual environment)
- **Camera Backend**: OpenCV VideoCapture with V4L2
- **ML Framework**: TensorFlow Lite (XNNPACK delegate)
- **Web Framework**: Flask (development server)

## Current Status

### Service Health
```bash
sudo systemctl status traffic-eye-dashboard
```
✅ **Active**: Running since Feb 10 01:27:55
✅ **PID**: 4276
✅ **Auto-start**: Enabled

### System Metrics
- **CPU Usage**: ~80-85% (normal during detection)
- **Memory Usage**: ~29% (1.2GB / 4GB)
- **CPU Temperature**: 47°C (healthy, no throttling)
- **Disk Usage**: 56.5% (good)

### Camera Status
✅ **Detected**: SNAP U2 USB webcam
✅ **Device**: `/dev/video1` (auto-detected)
✅ **Resolution**: 640x480
✅ **FPS**: 15-30
✅ **Stream**: Active (MJPEG)

### Detection Pipeline
✅ **YOLOv8n**: Loaded and running (INT8 quantized)
✅ **Helmet Classifier**: Loaded and running (Float16 quantized)
✅ **Processing**: Every 3rd frame (~5 FPS effective)
✅ **Inference Time**: ~150-200ms per frame

### Web Dashboard
✅ **URL**: http://100.107.114.5:8080
✅ **Local**: http://localhost:8080
✅ **Network**: http://192.168.68.63:8080
✅ **API**: `/api/status` responding
✅ **Video Feed**: `/video_feed` streaming

## Access Instructions

### From iPad (via Tailscale VPN)
1. Connect to Tailscale network
2. Open browser: http://100.107.114.5:8080
3. Live camera feed with YOLO detection overlays

### From Local Network
1. Open browser: http://192.168.68.63:8080
2. Same live feed accessible

### Detection Legend
- 🟢 **Green**: Person
- 🟠 **Orange**: Motorcycle
- 🔵 **Light Blue**: Car
- 🟣 **Magenta**: Truck
- 🟡 **Yellow**: Bus
- 🔷 **Cyan**: Bicycle
- 🔴 **Red**: Traffic Light

## Configuration

### Camera Settings (`config/settings.yaml`)
```yaml
camera:
  resolution: [640, 480]
  fps: 15
  process_every_nth_frame: 3
  type: "usb"  # Forces USB webcam mode
```

### Detection Settings
```yaml
detection:
  model_path: "models/yolov8n_int8.tflite"
  confidence_threshold: 0.5
  num_threads: 4
  target_classes:
    - person
    - motorcycle
    - car
    - truck
    - bus
    - bicycle
    - traffic light
```

## Maintenance Commands

### Service Management
```bash
# View live logs
sudo journalctl -u traffic-eye-dashboard -f

# Restart service
sudo systemctl restart traffic-eye-dashboard

# Stop service
sudo systemctl stop traffic-eye-dashboard

# Start service
sudo systemctl start traffic-eye-dashboard

# Disable auto-start
sudo systemctl disable traffic-eye-dashboard

# Enable auto-start
sudo systemctl enable traffic-eye-dashboard
```

### Testing
```bash
# Test USB webcam
python scripts/test_webcam.py

# Test live stream
bash scripts/test_live_stream.sh

# Full verification
bash scripts/verify_webcam_deployment.sh

# Check system health
bash scripts/check_power.sh
```

### Monitoring
```bash
# System metrics
htop

# Temperature
vcgencmd measure_temp

# Throttling check
vcgencmd get_throttled

# Network status
tailscale status

# Video devices
v4l2-ctl --list-devices
```

## Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u traffic-eye-dashboard -n 50

# Test manually
source venv/bin/activate
python src/web/dashboard_camera.py
```

### No Video Feed
```bash
# Check camera
python scripts/test_webcam.py

# Check if camera in use
sudo fuser /dev/video*

# Restart service
sudo systemctl restart traffic-eye-dashboard
```

### High CPU/Temperature
```bash
# Check temperature
vcgencmd measure_temp

# Reduce processing load
# Edit config/settings.yaml:
# process_every_nth_frame: 5  # Increase from 3
```

## Known Issues

1. **Detection Logging**: Camera initialization logs not showing device number
   - **Impact**: Low (camera still works correctly)
   - **Workaround**: Use `fuser /dev/video*` to confirm device

2. **Flask Development Server**: Running in development mode
   - **Impact**: Medium (not recommended for production)
   - **Solution**: Consider migrating to gunicorn/uvicorn (future enhancement)

## Recent Changes

### 2026-02-10: USB Webcam Migration
- ✅ Migrated from Pi Camera (OV5647 via CSI) to USB Webcam (SNAP U2)
- ✅ Updated platform factory to support camera type config
- ✅ Added USB camera auto-detection (tries device 1, then 0)
- ✅ Updated camera streamer with camera type parameter
- ✅ Created test scripts for webcam validation
- ✅ Updated all documentation

See `WEBCAM_MIGRATION.md` for full migration details.

## Next Steps

### Immediate (Optional)
- [ ] Add more verbose camera initialization logging
- [ ] Test detection accuracy in field conditions
- [ ] Monitor system stability over 24 hours

### Future Enhancements
- [ ] Migrate to production WSGI server (gunicorn/uvicorn)
- [ ] Add HTTPS support with self-signed cert
- [ ] Implement video recording for violations
- [ ] Add GPS integration for location tagging
- [ ] Set up email alerts for violations

## Support

### Documentation
- `CLAUDE.md` - Project overview and commands
- `CAMERA_DEPLOYMENT.md` - Camera setup details
- `WEBCAM_MIGRATION.md` - Migration from Pi Camera to USB webcam
- `DEPLOYMENT_SUMMARY.md` - Field testing deployment guide
- `POWER_SUPPLY_GUIDE.md` - Power supply recommendations

### Testing Scripts
- `scripts/test_webcam.py` - Test USB camera detection
- `scripts/test_live_stream.sh` - Verify live stream
- `scripts/verify_webcam_deployment.sh` - Full deployment check
- `scripts/check_power.sh` - Power health check

---

**Last Updated**: 2026-02-10 01:28 IST
**System Uptime**: 4 minutes (service restarted)
**Overall Status**: ✅ **FULLY OPERATIONAL**
