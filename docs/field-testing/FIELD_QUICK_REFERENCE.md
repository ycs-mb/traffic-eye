# 🚦 Traffic-Eye Field Testing - Quick Reference Card

**Print this and keep in vehicle for quick reference**

---

## ⚡ Quick Start (3 Steps)

1. **Connect power** → Wait 60 seconds
2. **iPad**: Connect to Tailscale VPN
3. **Open dashboard**: `http://<TAILSCALE_IP>:8080`

✅ **Done!** System runs automatically.

---

## 📱 iPad Access

### Dashboard URL
```
http://100.x.x.x:8080
(Replace with your Tailscale IP)
```

### SSH Access
```bash
ssh yashcs@100.x.x.x
Password: [your-password]
```

---

## 🔧 Essential Commands (via iPad SSH)

### Check Service Status
```bash
sudo systemctl status traffic-eye-field
```

### View Live Logs
```bash
journalctl -u traffic-eye-field -f
```

### Restart Service
```bash
sudo systemctl restart traffic-eye-field
```

### Check Power Health
```bash
vcgencmd measure_temp
vcgencmd get_throttled
# 0x0 = healthy
# anything else = power issue
```

### Check GPS
```bash
cgps
# Wait for "Status: 3D FIX"
```

### Check Disk Space
```bash
df -h
```

### Safe Shutdown
```bash
sudo systemctl stop traffic-eye-field
sudo shutdown -h now
# Wait 30 seconds, then unplug power
```

---

## ⚠️ Warning Signs

| Issue | Symptom | Quick Fix |
|-------|---------|-----------|
| **Undervoltage** | Rainbow square on screen | Use better power supply |
| **Overheating** | Temp > 80°C | Add cooling, reduce FPS |
| **No GPS fix** | Status != 3D FIX | Move to window, wait 5 min |
| **Service crashed** | Dashboard shows "inactive" | `sudo systemctl restart traffic-eye-field` |
| **Low disk space** | < 2GB free | Run: `bash scripts/cleanup_old_evidence.sh` |

---

## 📊 Normal Operating Parameters

| Metric | Normal Range | Warning | Critical |
|--------|--------------|---------|----------|
| CPU Usage | 40-70% | 70-85% | > 85% |
| CPU Temp | 50-70°C | 70-80°C | > 80°C |
| Memory | 50-70% | 70-85% | > 85% |
| Disk Space | > 10GB free | 5-10GB | < 5GB |

---

## 🔋 Power Options

### Power Bank
- **Required**: 5V/3A output (USB-C PD recommended)
- **Runtime**: ~8-10 hours (26800mAh)
- **Check**: Solid red power LED (not flickering)

### Car DC Supply
- **Required**: 12V cigarette lighter adapter, 5V/3A output
- **Warning**: Engine must be running (prevents car battery drain)
- **Check**: No voltage warning in dashboard

---

## 📸 Camera & GPS Tips

### Camera Position
- Mount at windshield level
- Clear view of road ahead
- Avoid direct sunlight on lens
- Secure cable to prevent movement

### GPS Position
- Near window (clear sky view)
- Away from metal objects
- Wait 1-5 minutes for first fix
- Fix quality improves over time

---

## 🆘 Emergency Contacts

**Project**: Traffic-Eye Field Testing
**Platform**: Raspberry Pi 4 (4GB)
**System**: Raspberry Pi OS 64-bit

**Support**:
- GitHub: [your-repo]
- Documentation: `/home/yashcs/traffic-eye/docs/`

---

## 📝 Quick Testing Checklist

Before driving:
- [ ] Power LED solid (not flickering)
- [ ] Dashboard accessible from iPad
- [ ] Service status = "active"
- [ ] GPS shows "3D FIX"
- [ ] Temperature < 70°C
- [ ] Disk space > 5GB

During test:
- [ ] Check dashboard every 10 minutes
- [ ] Note any violations detected
- [ ] Monitor temperature
- [ ] Record any issues

After test:
- [ ] Stop service gracefully
- [ ] Shutdown properly
- [ ] Disconnect power after 30 seconds
- [ ] Review logs and data

---

**Version**: 1.0 (2026-02-09)
**Deployment**: Field Testing

Print Date: ___________
Tested By: ___________
