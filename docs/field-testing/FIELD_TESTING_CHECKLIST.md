# Traffic-Eye Field Testing Checklist

## 📋 Pre-Deployment Checklist (At Home)

### Hardware Setup
- [ ] Raspberry Pi 4 in protective case with fan
- [ ] 64GB+ SanDisk Extreme microSD card installed
- [ ] Pi Camera Module v2 connected to CSI port
- [ ] USB GPS module (VK-162 or similar) plugged in
- [ ] Power bank (26800mAh+) or car charger tested
- [ ] All cables secured and labeled

### Software Configuration
- [ ] Run deployment script: `bash scripts/deploy_field_testing.sh`
- [ ] Tailscale VPN installed and authenticated
- [ ] GPS module detected: `gpspipe -w | head -20`
- [ ] Camera working: `libcamera-hello --list-cameras`
- [ ] API key configured in `/etc/traffic-eye.env`
- [ ] Services enabled: `systemctl is-enabled traffic-eye-field`
- [ ] Web dashboard accessible: `curl localhost:8080`

### Testing
- [ ] Reboot test: `sudo reboot` → Services auto-start
- [ ] Power test: Run for 30 minutes on battery
- [ ] GPS fix test: Wait for GPS lock (clear sky view)
- [ ] Camera test: Take test photo with `libcamera-jpeg`
- [ ] Detection test: Run integration tests (passed)
- [ ] Dashboard test: Access from iPad via Tailscale IP

### iPad Setup
- [ ] Tailscale app installed and signed in
- [ ] SSH client installed (Termius or Blink Shell)
- [ ] Bookmark dashboard: `http://<tailscale-ip>:8080`
- [ ] Test SSH connection: `ssh yashcs@<tailscale-ip>`

---

## 🚗 Field Deployment Checklist (In Vehicle)

### Before Starting
- [ ] Mount Raspberry Pi securely (dashboard or windshield)
- [ ] Connect power (power bank or car DC adapter)
- [ ] Position camera for clear road view
- [ ] Place GPS module near window (clear sky view)
- [ ] Verify power LED is solid (not flickering)

### Startup Sequence (Auto)
- [ ] **Power on** → Wait 60 seconds for boot
- [ ] **Services start** automatically (no login needed)
- [ ] **iPad**: Connect to Tailscale VPN
- [ ] **iPad**: Open dashboard at `http://<tailscale-ip>:8080`
- [ ] **Check dashboard**: Service status = "active"

### Verify System Health
- [ ] Dashboard shows: CPU < 80%, Memory < 75%, Temp < 75°C
- [ ] GPS status: Fix acquired (may take 1-5 minutes)
- [ ] Camera: Live detections visible in logs
- [ ] Disk space: > 5GB free

### During Testing
- [ ] Monitor dashboard every 5-10 minutes
- [ ] Check for violations in logs
- [ ] Take notes on detection accuracy
- [ ] Record any false positives/negatives
- [ ] Monitor temperature (should stay < 80°C)

---

## 🛑 Shutdown Procedure

### Graceful Shutdown
```bash
# From iPad SSH
sudo systemctl stop traffic-eye-field
sudo systemctl stop traffic-eye-dashboard
sudo shutdown -h now
```

**Wait 30 seconds**, then disconnect power.

### Emergency Shutdown
If system is unresponsive:
1. Disconnect power
2. Wait 10 seconds
3. Reconnect to recover

⚠️ **WARNING**: Abrupt power loss may corrupt SD card. Always use graceful shutdown when possible.

---

## 🔍 Troubleshooting Guide

### Service Won't Start
```bash
# Check service status
sudo systemctl status traffic-eye-field

# View detailed logs
journalctl -u traffic-eye-field -n 100

# Common fixes
sudo systemctl restart traffic-eye-field
```

### GPS Not Working
```bash
# Check GPS device
ls -l /dev/ttyUSB* /dev/ttyACM*

# Test GPS
gpspipe -w | head -20

# Restart gpsd
sudo systemctl restart gpsd
```

### Camera Not Detected
```bash
# Check camera
vcgencmd get_camera

# Test camera
libcamera-hello --list-cameras

# Reconnect cable and reboot
sudo reboot
```

### Dashboard Not Accessible
```bash
# Check dashboard service
sudo systemctl status traffic-eye-dashboard

# Check Tailscale
tailscale status

# Restart dashboard
sudo systemctl restart traffic-eye-dashboard
```

### High Temperature (> 80°C)
- Add heatsink or fan
- Reduce CPU quota in service file
- Lower detection FPS in config

### Low Disk Space
```bash
# Run cleanup manually
bash scripts/cleanup_old_evidence.sh

# Check disk usage
df -h
du -sh data/evidence/*
```

---

## 📊 Data Collection Log

Use this during field testing:

| Time | Location | Violations Detected | Notes |
|------|----------|---------------------|-------|
| 10:30 AM | MG Road | 2 no-helmet | Good accuracy |
| 11:15 AM | Highway | 1 no-helmet | False positive? |
| ... | ... | ... | ... |

---

## 🎯 Success Criteria

Field testing is successful when:
- [ ] System runs continuously for 2+ hours without crashes
- [ ] GPS maintains stable fix throughout test
- [ ] Camera captures clear frames at 15 FPS
- [ ] Helmet detection accuracy > 80% (manual verification)
- [ ] Dashboard accessible from iPad throughout test
- [ ] No thermal throttling (temp stays < 80°C)
- [ ] No SD card corruption after multiple power cycles

---

## 📝 Post-Testing Review

After field testing, evaluate:

1. **Detection Accuracy**
   - True positives: ____ / ____
   - False positives: ____ / ____
   - False negatives: ____ / ____
   - Overall accuracy: ____%

2. **System Stability**
   - Uptime: ____ hours
   - Crashes: ____
   - Restarts needed: ____

3. **Performance**
   - Average CPU: ____%
   - Average temp: ____°C
   - Average FPS: ____
   - Total detections: ____

4. **Issues Found**
   - [List any problems]

5. **Improvements Needed**
   - [List suggested improvements]

---

## 🔄 Next Steps After Field Testing

Based on results:

1. **If successful**:
   - Move to production deployment
   - Set up continuous operation
   - Configure email alerts

2. **If issues found**:
   - Retrain models with real data
   - Adjust detection thresholds
   - Optimize performance settings

3. **Always**:
   - Review violation logs
   - Backup evidence data
   - Update documentation

---

**Last Updated**: 2026-02-09
**Version**: 1.0 (Initial Field Testing)
