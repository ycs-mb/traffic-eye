# ✅ Traffic-Eye Field Testing Deployment - READY

**Status**: **DEPLOYMENT SCRIPTS READY**
**Date**: 2026-02-09
**Platform**: Raspberry Pi 4 (4GB RAM, ARM64)
**Deployment Type**: Plug-and-Play Field Testing

---

## 🎯 Mission Accomplished

Your Traffic-Eye system is now ready for **plug-and-play field testing**:

✅ **Connect power** → System boots → Auto-runs detection → Monitor from iPad

---

## 📦 What Was Created

### **1. Hardware Shopping List**
- ✅ Power options (power bank + car DC adapter)
- ✅ Camera recommendations (Pi Camera v2)
- ✅ GPS module (VK-162 USB GPS)
- ✅ Storage and mounting hardware
- ✅ Complete budget estimates (₹6,500-12,000)

**File**: See section "Hardware Shopping List" above

### **2. Deployment Scripts**

| Script | Purpose |
|--------|---------|
| `scripts/deploy_field_testing.sh` | **Master deployment script** (run once) |
| `scripts/check_power.sh` | Power health monitoring |
| `scripts/setup_camera.sh` | Camera detection and testing |
| `scripts/setup_gps.sh` | GPS module setup and testing |
| `scripts/setup_tailscale.sh` | VPN setup for iPad access |
| `scripts/cleanup_old_evidence.sh` | Auto-cleanup old evidence (cron) |

### **3. Systemd Services (Auto-Start)**

| Service | Description |
|---------|-------------|
| `traffic-eye-field.service` | Main detection service (auto-start on boot) |
| `traffic-eye-dashboard.service` | Web dashboard (port 8080) |

### **4. Web Dashboard**
- ✅ Real-time monitoring from iPad
- ✅ System metrics (CPU, memory, temp, disk)
- ✅ Service status and uptime
- ✅ Live logs (last 50 lines)
- ✅ Restart service button
- ✅ Auto-refresh every 2 seconds

**Access**: `http://<tailscale-ip>:8080`

### **5. Tailscale VPN**
- ✅ Secure Pi ↔ iPad connection
- ✅ No port forwarding needed
- ✅ Works over 4G/WiFi
- ✅ Simple setup (one command)

### **6. Documentation**

| Document | Purpose |
|----------|---------|
| `FIELD_TESTING_CHECKLIST.md` | **Complete pre-flight and testing checklist** |
| `FIELD_QUICK_REFERENCE.md` | **Printable quick reference card** |
| `FIELD_DEPLOYMENT_COMPLETE.md` | **This summary document** |

---

## 🚀 Deployment Steps (Run Once on Pi)

### **Step 1: Run Master Deployment Script**

```bash
cd /home/yashcs/traffic-eye
bash scripts/deploy_field_testing.sh
```

This script will:
1. Install system dependencies (gpsd, camera tools, etc.)
2. Setup Python venv and install packages
3. Configure GPS module
4. Test camera
5. Install Tailscale VPN
6. Setup systemd services (auto-start)
7. Create data directories
8. Setup cron jobs for cleanup
9. Run health checks

**Time**: 10-15 minutes

### **Step 2: Setup Tailscale VPN**

```bash
sudo tailscale up
```

Follow the authentication URL, then:

```bash
tailscale ip -4
# Save this IP for iPad access
```

### **Step 3: Install Tailscale on iPad**

1. Install **Tailscale** from App Store
2. Sign in with same account
3. Enable VPN

### **Step 4: Start Services**

```bash
# Start main detection service
sudo systemctl start traffic-eye-field

# Start web dashboard
sudo systemctl start traffic-eye-dashboard

# Check status
sudo systemctl status traffic-eye-field
```

### **Step 5: Access Dashboard from iPad**

Open Safari on iPad:
```
http://<tailscale-ip>:8080
```

You should see the Traffic-Eye dashboard with live system stats.

### **Step 6: Test Auto-Start**

```bash
sudo reboot
```

Wait 60 seconds, then check if services started automatically:

```bash
sudo systemctl status traffic-eye-field
sudo systemctl status traffic-eye-dashboard
```

Both should show **"active (running)"**.

---

## 🔧 Hardware Setup (Before Field Testing)

### **Required Hardware**

#### **Option A: Portable Testing (Recommended for first test)**
- [ ] Raspberry Pi 4 (4GB)
- [ ] Power bank (26800mAh, 5V/3A USB-C output) - ₹2,500
- [ ] Pi Camera Module v2 - ₹2,000
- [ ] VK-162 USB GPS module - ₹1,000
- [ ] SanDisk Extreme 64GB microSD - ₹1,000
- [ ] Pi case with fan - ₹1,000
- **Total**: ~₹7,500

#### **Option B: Car Installation**
- Same as above, but replace power bank with:
- [ ] 12V car charger (USB-C, 5V/3A) - ₹1,500

### **Physical Installation**

1. **Mount Raspberry Pi**:
   - Dashboard mount or windshield suction cup
   - Secure with velcro or mount bracket
   - Ensure good airflow around case

2. **Position Camera**:
   - Mount at windshield level
   - Clear view of road ahead
   - Secure CSI cable to prevent disconnection

3. **Place GPS Module**:
   - Near window (clear sky view)
   - Plug into USB port
   - Secure with velcro

4. **Connect Power**:
   - Power bank: Charge fully before test
   - Car: Use cigarette lighter adapter (engine running)

---

## 📱 iPad Monitoring Setup

### **Apps to Install**

1. **Tailscale** (VPN) - Required
   - Free from App Store
   - Sign in with same account as Pi

2. **Termius** or **Blink Shell** (SSH) - Recommended
   - For terminal access to Pi
   - Configure with Tailscale IP

3. **Safari** (Built-in)
   - For web dashboard access

### **Bookmark Dashboard**

Safari → Bookmark: `http://<TAILSCALE_IP>:8080`

Add to Home Screen for quick access.

---

## ✅ Pre-Flight Checklist (Print This)

See `FIELD_TESTING_CHECKLIST.md` for complete checklist.

**Quick Pre-Flight (5 minutes)**:
- [ ] Power LED solid (not flickering)
- [ ] Tailscale connected on iPad
- [ ] Dashboard accessible: `http://<tailscale-ip>:8080`
- [ ] Service status: "active"
- [ ] GPS fix: Wait 1-5 minutes for "3D FIX"
- [ ] Temperature < 70°C
- [ ] Disk space > 5GB free

---

## 🔍 Monitoring During Field Testing

### **Dashboard Metrics (Check Every 10 Min)**

| Metric | Normal | Warning | Action |
|--------|--------|---------|--------|
| CPU | 40-70% | > 80% | Reduce FPS in config |
| Memory | 50-70% | > 80% | Restart service |
| Temperature | 50-70°C | > 75°C | Add cooling, reduce load |
| Disk Space | > 10GB | < 5GB | Run cleanup script |

### **Live Logs (via Dashboard)**

- Watch for violation detections
- Note any errors or warnings
- Record timestamps of interesting events

### **SSH Commands (via iPad)**

```bash
# View live logs
journalctl -u traffic-eye-field -f

# Check GPS status
cgps

# Check power health
vcgencmd measure_temp
vcgencmd get_throttled  # Should be 0x0

# Restart service
sudo systemctl restart traffic-eye-field
```

---

## 🛑 Safe Shutdown Procedure

### **Graceful Shutdown (Recommended)**

From iPad SSH:
```bash
sudo systemctl stop traffic-eye-field
sudo systemctl stop traffic-eye-dashboard
sudo shutdown -h now
```

Wait 30 seconds until green LED stops blinking, then unplug power.

### **Emergency Shutdown**

If system is frozen:
1. Unplug power
2. Wait 10 seconds
3. Reconnect when ready

⚠️ **Note**: Emergency shutdown may corrupt SD card. Always try graceful shutdown first.

---

## 🐛 Troubleshooting

### **Service Won't Start**

```bash
# Check what went wrong
sudo systemctl status traffic-eye-field
journalctl -u traffic-eye-field -n 50

# Common fixes
sudo systemctl restart traffic-eye-field
```

### **Dashboard Not Accessible**

```bash
# Check if dashboard service is running
sudo systemctl status traffic-eye-dashboard

# Restart dashboard
sudo systemctl restart traffic-eye-dashboard

# Check Tailscale connection
tailscale status
```

### **GPS Not Getting Fix**

- Move to window (clear sky view)
- Wait 1-5 minutes (cold start takes longer)
- Check device: `ls -l /dev/ttyUSB* /dev/ttyACM*`
- Test manually: `cgps` or `gpsmon`

### **Camera Not Working**

```bash
# Check camera detection
vcgencmd get_camera

# Test camera
libcamera-hello --list-cameras

# If not detected, reconnect CSI cable and reboot
```

### **High Temperature (> 80°C)**

- Add heatsink or fan to case
- Reduce FPS in `config/settings.yaml`
- Lower `CPUQuota` in service file

### **Low Disk Space**

```bash
# Run cleanup manually
bash scripts/cleanup_old_evidence.sh

# Check what's using space
du -sh data/evidence/*
```

---

## 📊 Post-Testing Analysis

After field testing session:

1. **Stop services**:
   ```bash
   sudo systemctl stop traffic-eye-field
   ```

2. **Review logs**:
   ```bash
   journalctl -u traffic-eye-field > ~/field-test-logs.txt
   ```

3. **Check database**:
   ```bash
   sqlite3 data/traffic_eye.db "SELECT COUNT(*) FROM violations;"
   ```

4. **Review evidence**:
   ```bash
   ls -lh data/evidence/
   ```

5. **Backup data** (optional):
   ```bash
   rsync -av data/ ~/field-test-backup/
   ```

---

## 🎯 Success Criteria

Field testing is **successful** when:
- ✅ System runs continuously for 2+ hours without crashes
- ✅ GPS maintains stable fix throughout test
- ✅ Camera captures frames at target FPS (15 FPS)
- ✅ Helmet detections are reasonably accurate (>70%)
- ✅ Dashboard accessible from iPad throughout
- ✅ No thermal throttling (temp < 80°C)
- ✅ No power issues (no undervoltage warnings)
- ✅ No SD card corruption after multiple reboots

---

## 🔄 Next Steps After Successful Testing

### **If Testing Goes Well**:
1. ✅ Move to production deployment
2. ✅ Configure email/SMS alerts
3. ✅ Set up cloud backup (optional)
4. ✅ Retrain models with collected real data
5. ✅ Add remaining features (red-light, wrong-side)

### **If Issues Found**:
1. 🔧 Adjust detection thresholds
2. 🔧 Optimize performance (reduce FPS, lower resolution)
3. 🔧 Improve helmet model accuracy
4. 🔧 Fix hardware issues (power, cooling)

---

## 📝 Field Testing Log Template

Use this during testing:

```
Date: ___________
Location: ___________
Duration: ___________
Weather: ___________

Hardware:
- Power Source: [ ] Power Bank  [ ] Car DC
- Camera: [ ] Pi Camera v2  [ ] USB Webcam
- GPS: [ ] VK-162 USB

Results:
- Total Runtime: _____ hours
- System Crashes: _____
- Detections: _____
- Violations (No Helmet): _____
- False Positives: _____
- False Negatives: _____

System Performance:
- Average CPU: _____%
- Average Temp: _____°C
- Max Temp: _____°C
- Disk Space Used: _____GB

Issues Encountered:
- _____________________
- _____________________

Observations:
- _____________________
- _____________________

Overall Rating: [ ] Pass  [ ] Needs Improvement  [ ] Fail
```

---

## 📚 Reference Documents

| Document | Purpose |
|----------|---------|
| `FIELD_TESTING_CHECKLIST.md` | Complete checklist with troubleshooting |
| `FIELD_QUICK_REFERENCE.md` | Printable quick reference (keep in car) |
| `README.md` | Project overview and architecture |
| `INTEGRATION_TEST_RESULTS.md` | Integration test results |
| `GEMINI_OCR_COMPLETE.md` | Cloud OCR setup and testing |

---

## 💡 Pro Tips

### **Battery Life**
- Use 26800mAh power bank for ~8-10 hours runtime
- Monitor battery level on power bank
- Bring spare power bank for longer sessions

### **GPS Performance**
- First fix takes 1-5 minutes (cold start)
- Subsequent fixes are faster (hot start)
- Park with clear sky view for best results
- GPS accuracy improves over time

### **Camera Quality**
- Clean lens before testing
- Avoid direct sunlight in frame
- Test during different lighting conditions
- Mount securely to prevent vibration blur

### **Network**
- Tailscale works over 4G/WiFi
- iPad can use cellular hotspot if needed
- Dashboard uses minimal bandwidth
- SSH is very lightweight

### **Data Management**
- Evidence auto-cleaned after 7 days
- Manual cleanup: `bash scripts/cleanup_old_evidence.sh`
- Check disk space regularly
- Backup important evidence before cleanup

---

## 🆘 Emergency Contacts

**Project**: Traffic-Eye Field Testing
**Platform**: Raspberry Pi 4 (4GB RAM, ARM64)
**OS**: Raspberry Pi OS 64-bit

**Documentation**:
- Project folder: `/home/yashcs/traffic-eye`
- Logs: `journalctl -u traffic-eye-field -f`
- Config: `config/settings.yaml`

**Support Resources**:
- Integration tests: `python scripts/test_integration.py`
- Power check: `bash scripts/check_power.sh`
- GPS test: `cgps` or `gpsmon`
- Camera test: `libcamera-hello --list-cameras`

---

## ✅ Final Checklist Before Field Deployment

### **Hardware**
- [ ] Raspberry Pi 4 in case with fan
- [ ] Camera connected and tested
- [ ] GPS module connected and tested
- [ ] Power source ready (charged/connected)
- [ ] All cables secured
- [ ] Mounting hardware installed

### **Software**
- [ ] Deployment script completed successfully
- [ ] Services auto-start on boot (tested with reboot)
- [ ] Tailscale VPN configured on Pi and iPad
- [ ] Dashboard accessible from iPad
- [ ] GPS getting fix (3D FIX)
- [ ] Camera capturing frames
- [ ] Disk space > 10GB free
- [ ] API key configured

### **Documentation**
- [ ] `FIELD_QUICK_REFERENCE.md` printed
- [ ] `FIELD_TESTING_CHECKLIST.md` reviewed
- [ ] Tailscale IP written down
- [ ] iPad apps installed and tested
- [ ] Field testing log template ready

### **Testing**
- [ ] Integration tests passed (4/4)
- [ ] Helmet detection tested on video (6 violations found)
- [ ] System ran for 30+ minutes without issues
- [ ] Reboot test passed (auto-start works)
- [ ] Dashboard shows all green metrics

---

## 🎉 You Are Ready!

**Your Traffic-Eye system is fully prepared for field testing.**

### **Quick Start (Day of Testing)**:

1. **Connect power** → Wait 60 seconds for boot
2. **iPad**: Connect to Tailscale VPN
3. **Open dashboard**: `http://<tailscale-ip>:8080`
4. **Verify**: Service active, GPS fix, camera running
5. **Start driving** and monitor dashboard

**That's it! The system runs automatically.**

---

**Deployment Completed**: 2026-02-09
**Version**: 1.0 (Field Testing)
**Status**: ✅ **READY FOR FIELD DEPLOYMENT**

**Good luck with your field testing!** 🚀
