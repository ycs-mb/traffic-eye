# Traffic-Eye Deployment Guide

Complete guide for deploying Traffic-Eye on a Raspberry Pi 4 in production.

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [OS Installation](#os-installation)
3. [Pre-Configuration](#pre-configuration)
4. [Automated Setup](#automated-setup)
5. [Post-Installation](#post-installation)
6. [Security Hardening](#security-hardening)
7. [Service Management](#service-management)
8. [Monitoring and Health Checks](#monitoring-and-health-checks)
9. [GPS Setup](#gps-setup)
10. [Troubleshooting](#troubleshooting)
11. [Maintenance](#maintenance)
12. [Performance Expectations](#performance-expectations)

---

## Hardware Requirements

### Bill of Materials

| Component | Specification | Estimated Cost (INR) |
|-----------|--------------|---------------------|
| Raspberry Pi 4 | 4GB or 8GB RAM | 3,500 - 5,500 |
| Pi Camera Module v2 | 8MP, CSI connector | 2,000 |
| MicroSD Card | 64GB, A2 class (SanDisk Extreme recommended) | 600 |
| Power Supply | Official Pi 4 USB-C, 5V/3A | 500 |
| Heatsink + Fan | Aluminum heatsink kit or active cooler | 200 - 500 |
| Case | With camera mount, ventilated | 300 |
| NEO-6M GPS Module | UART, optional | 300 |
| Power Bank | 10000mAh, 5V/3A output (for mobile deployment) | 1,000 |

**Total: approximately 4,000 - 10,000 INR** depending on configuration.

### Important Notes

- **RAM**: 4GB is the minimum. 8GB is recommended if running cloud verification.
- **SD Card**: Use A2-rated cards. Avoid cheap cards -- they fail under sustained writes.
- **Power**: Undervoltage is the number one cause of instability. Always use the official power supply or a quality 5V/3A adapter with a short, thick cable (20-22 AWG).
- **Cooling**: The Pi 4 will thermal-throttle under sustained ML inference. A heatsink and fan are mandatory for production.

---

## OS Installation

### Step 1: Download Raspberry Pi Imager

Download from [https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/) on your computer (Windows, macOS, or Linux).

### Step 2: Flash the SD Card

1. Insert the MicroSD card into your computer.
2. Open Raspberry Pi Imager.
3. Click **Choose OS** > **Raspberry Pi OS (other)** > **Raspberry Pi OS Lite (64-bit)**.
   - Must be the **64-bit Bookworm** version.
   - Use Lite (no desktop) -- Traffic-Eye is headless.
4. Click **Choose Storage** and select your SD card.
5. Click the **gear icon** (or Ctrl+Shift+X) to open Advanced Options.

### Step 3: Advanced Options (Pre-Configuration)

Configure these settings in the Imager before flashing:

| Setting | Value |
|---------|-------|
| Set hostname | `traffic-eye` (or your preferred name) |
| Enable SSH | Yes, use password authentication (switch to keys later) |
| Set username and password | Create a user (e.g., `yashcs`). Do NOT use the default `pi`. |
| Configure wireless LAN | Enter your WiFi SSID and password |
| Set locale settings | Your timezone and keyboard layout |

Click **Save**, then **Write**.

### Step 4: First Boot

1. Insert the SD card into the Pi.
2. Connect the camera module to the CSI port (with the Pi powered off).
3. Connect Ethernet (recommended for initial setup) or rely on WiFi configured above.
4. Connect power. Wait 1-2 minutes for first boot.
5. Find the Pi on your network: `ping traffic-eye.local` or check your router's DHCP list.
6. SSH in: `ssh yashcs@traffic-eye.local`

---

## Pre-Configuration

Before running the setup script, verify the basic system is working.

```bash
# Verify you are on 64-bit Bookworm
cat /etc/os-release
uname -m  # Should show: aarch64

# Check internet connectivity
ping -c 3 google.com

# Check camera is detected
libcamera-hello --list-cameras
# Should show at least one camera

# Check available disk space
df -h /
# Should have at least 500MB free (ideally 10GB+)

# Check power status
vcgencmd get_throttled
# Should show: throttled=0x0 (no issues)

# Check temperature
vcgencmd measure_temp
```

---

## Automated Setup

### Step 1: Clone the Repository

```bash
# Clone to a temporary location
git clone <repo-url> /tmp/traffic-eye
cd /tmp/traffic-eye
```

Or copy the project files to the Pi via SCP:

```bash
# From your development machine:
scp -r /path/to/traffic-eye yashcs@traffic-eye.local:/tmp/traffic-eye
```

### Step 2: Run the Setup Script

```bash
sudo bash /tmp/traffic-eye/scripts/setup.sh
```

The script performs these steps automatically:

1. **Preflight checks** -- verifies Pi hardware, disk space, internet, source files
2. **System packages** -- installs Python, picamera2, ffmpeg, gpsd, i2c-tools, build tools
3. **Hardware configuration** -- enables camera, sets GPU memory to 128MB, enables I2C
4. **Directory structure** -- creates `/opt/traffic-eye`, `/var/lib/traffic-eye`, `/var/log/traffic-eye`
5. **Python environment** -- creates venv with `--system-site-packages`, installs all dependencies
6. **Project files** -- copies source code, config, models, tests to `/opt/traffic-eye`
7. **systemd services** -- installs and enables `traffic-eye.service` and `traffic-eye-sender.timer`
8. **log2ram** -- installs log2ram to reduce SD card writes
9. **Health monitoring** -- installs health check cron job (runs every 15 minutes)

The script is **idempotent** -- safe to run multiple times. It will skip steps that are already completed.

### Step 3: Reboot (if prompted)

If hardware configuration changed (GPU memory, camera), the script will prompt for a reboot:

```bash
sudo reboot
```

---

## Post-Installation

### Place Model Files

The setup script creates the models directory but does not download model files. Copy them manually:

```bash
# From your development machine:
scp yolov8n_int8.tflite yashcs@traffic-eye.local:/opt/traffic-eye/models/
scp helmet_cls_int8.tflite yashcs@traffic-eye.local:/opt/traffic-eye/models/
```

See `models/README.md` for instructions on training and converting models.

### Configure Credentials

Edit the environment file:

```bash
sudo nano /etc/traffic-eye.env
```

Uncomment and fill in:

```
TRAFFIC_EYE_EMAIL_PASSWORD=your-gmail-app-password
TRAFFIC_EYE_CLOUD_API_KEY=your-gemini-api-key
```

For Gmail, you need an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

### Test in Mock Mode

Verify the installation works without hardware dependencies:

```bash
source /opt/traffic-eye/venv/bin/activate
cd /opt/traffic-eye
python -m src.main --config config/settings_pi.yaml --mock
```

You should see log output indicating the detection loop is running. Press Ctrl+C to stop.

### Test with Camera

```bash
# Quick camera test
libcamera-hello -t 5000

# Run Traffic-Eye with real camera
source /opt/traffic-eye/venv/bin/activate
cd /opt/traffic-eye
python -m src.main --config config/settings_pi.yaml
```

---

## Security Hardening

After the basic setup is working, apply security hardening:

```bash
sudo bash /opt/traffic-eye/scripts/harden.sh
```

This interactive script offers:

1. **System updates** -- applies all pending security patches
2. **UFW firewall** -- denies all incoming connections except SSH
3. **SSH hardening** -- disables root login, limits auth attempts, strong crypto
4. **fail2ban** -- blocks IPs after 3 failed SSH attempts for 1 hour
5. **Default user lockdown** -- locks the `pi` user if you are using a different account
6. **Disable unused services** -- Bluetooth, Avahi, ModemManager, triggerhappy
7. **Kernel hardening** -- anti-spoofing, SYN cookies, restricted dmesg
8. **Automatic security updates** -- unattended-upgrades for Debian security patches

Use `--yes` to apply all without prompts, or `--dry-run` to preview changes.

### SSH Key Setup (Strongly Recommended)

On your local machine:

```bash
# Generate a key pair (if you do not have one)
ssh-keygen -t ed25519 -C "traffic-eye-pi"

# Copy the public key to the Pi
ssh-copy-id -i ~/.ssh/id_ed25519.pub yashcs@traffic-eye.local

# Verify key-based login works
ssh yashcs@traffic-eye.local

# Then on the Pi, disable password authentication:
sudo sed -i 's/# PasswordAuthentication no/PasswordAuthentication no/' \
    /etc/ssh/sshd_config.d/traffic-eye-hardening.conf
sudo systemctl reload sshd
```

---

## Service Management

### Starting and Stopping

```bash
# Start the main detection service
sudo systemctl start traffic-eye

# Start the email/cloud sender timer
sudo systemctl start traffic-eye-sender.timer

# Stop the service
sudo systemctl stop traffic-eye

# Restart after config changes
sudo systemctl restart traffic-eye
```

### Viewing Logs

```bash
# Follow live logs
sudo journalctl -u traffic-eye -f

# View last 100 lines
sudo journalctl -u traffic-eye -n 100 --no-pager

# View errors only
sudo journalctl -u traffic-eye -p err

# View sender logs
sudo journalctl -u traffic-eye-sender

# View logs since last boot
sudo journalctl -u traffic-eye -b
```

### Checking Status

```bash
# Service status
sudo systemctl status traffic-eye

# Timer status (sender)
sudo systemctl list-timers traffic-eye-sender.timer

# Check if services are enabled for boot
sudo systemctl is-enabled traffic-eye
sudo systemctl is-enabled traffic-eye-sender.timer
```

### Service Configuration

The main service file is at `/etc/systemd/system/traffic-eye.service`. Key features:

- **Watchdog**: The service must send a heartbeat every 30 seconds or systemd restarts it
- **Auto-restart**: Restarts automatically on failure, with a 10-second delay
- **Resource limits**: Maximum 2GB RAM, 90% CPU quota
- **Security**: Runs with strict filesystem protection, no privilege escalation
- **Rate limiting**: Maximum 5 restarts in 5 minutes before giving up

After editing service files:

```bash
sudo systemctl daemon-reload
sudo systemctl restart traffic-eye
```

---

## Monitoring and Health Checks

### Automatic Monitoring

The health check script runs every 15 minutes via cron and monitors:

- CPU temperature (warning at 70C, critical at 80C)
- Undervoltage and throttling status
- Disk space usage (warning at 80%, critical at 90%)
- Service status and uptime
- Recent errors in journal
- Memory and swap usage

View health check output:

```bash
# View health log
cat /var/log/traffic-eye/health.log

# View alerts only
cat /var/log/traffic-eye/alerts.log

# Run health check manually
sudo bash /opt/traffic-eye/scripts/health_check.sh

# Get JSON output (for integration with monitoring systems)
sudo bash /opt/traffic-eye/scripts/health_check.sh --json
```

### Email Alerts

To receive email alerts on critical issues, add to `/etc/traffic-eye.env`:

```
TRAFFIC_EYE_ALERT_EMAIL=your-email@example.com
```

Requires `mailutils` or `sendmail` to be installed and configured on the Pi.

### Manual Diagnostics

```bash
# Quick system check
vcgencmd measure_temp          # CPU temperature
vcgencmd get_throttled         # Power/thermal status (0x0 = healthy)
vcgencmd measure_volts core    # Core voltage
free -h                        # Memory usage
df -h                          # Disk usage
uptime                         # Load average

# Process monitoring
htop                           # Interactive process viewer
sudo iotop -o                  # I/O usage (SD card writes)
```

---

## GPS Setup

### Hardware Connection (NEO-6M via UART)

| GPS Pin | Pi Pin |
|---------|--------|
| VCC | Pin 1 (3.3V) |
| GND | Pin 6 (GND) |
| TX | Pin 10 (GPIO15 / UART RX) |
| RX | Pin 8 (GPIO14 / UART TX) |

### Software Configuration

```bash
# Enable serial port (disable login shell on serial, enable hardware serial)
sudo raspi-config
# Interface Options > Serial Port > No (login shell) > Yes (hardware)

# Configure gpsd
sudo nano /etc/default/gpsd
```

Set:

```
DEVICES="/dev/ttyAMA0"
GPSD_OPTIONS="-n"
START_DAEMON="true"
```

Then:

```bash
sudo systemctl enable gpsd
sudo systemctl start gpsd

# Test GPS
cgps -s
# Wait for a fix (may take 1-5 minutes outdoors)
```

### Using Phone GPS (Network GPS)

Alternatively, use a phone app to send GPS data over WiFi:

1. Install a NMEA GPS app on your phone (e.g., "GPS2IP" on iOS, "Share GPS" on Android)
2. Configure it to send NMEA data via UDP to the Pi's IP on port 10110
3. Set in `config/settings_pi.yaml`:

```yaml
gps:
  source: "network"
  network_host: "0.0.0.0"
  network_port: 10110
  network_protocol: "udp"
```

---

## Troubleshooting

### Service Will Not Start

```bash
# Check detailed status
sudo systemctl status traffic-eye

# Check recent logs
sudo journalctl -u traffic-eye -n 50 --no-pager

# Test manually
source /opt/traffic-eye/venv/bin/activate
cd /opt/traffic-eye
python -m src.main --config config/settings_pi.yaml
```

Common causes:
- **Missing model files**: Check `/opt/traffic-eye/models/` has the `.tflite` files
- **Permission errors**: Run `sudo chown -R yashcs:yashcs /opt/traffic-eye /var/lib/traffic-eye`
- **Camera not available**: Run `libcamera-hello --list-cameras` to verify
- **Import errors**: Run `source /opt/traffic-eye/venv/bin/activate && pip list` to check dependencies

### Camera Not Working

```bash
# Check camera detection
libcamera-hello --list-cameras

# Check if camera module is connected
vcgencmd get_camera
# supported=1 detected=1 means OK

# Check boot config
grep -i camera /boot/firmware/config.txt

# Check kernel messages
dmesg | grep -i camera
```

### Undervoltage / Throttling

```bash
# Check current status
vcgencmd get_throttled

# Decode the flags:
# 0x0     = Healthy (no issues)
# 0x50005 = Undervoltage now + throttled now + both occurred in past
```

Solutions:
- Use the official Raspberry Pi power supply (5V/3A USB-C)
- Use a short, thick USB cable
- Remove unnecessary USB devices
- Add heatsinks and a fan

### High Temperature

```bash
vcgencmd measure_temp
```

If above 80C:
- Add a heatsink to the CPU and RAM chips
- Install an active fan
- Ensure the case has ventilation
- Consider reducing `detection.num_threads` in the config
- Traffic-Eye has built-in thermal throttling (configurable in `thermal` section)

### SD Card Issues

Signs of SD card problems: read-only filesystem, random crashes, corrupted database.

Prevention:
- log2ram is installed by the setup script (reduces writes)
- Use quality SD cards (SanDisk Extreme, Samsung EVO)
- Never pull power without shutting down: `sudo shutdown -h now`
- Monitor writes: `sudo iotop -o`

Recovery:
```bash
# Check filesystem
sudo fsck -f /dev/mmcblk0p2

# If read-only, remount
sudo mount -o remount,rw /
```

### Out of Memory

```bash
free -h
# If swap is heavily used, consider:

# 1. Reduce frame buffer size in config
# 2. Lower camera resolution
# 3. Enable zram compression
sudo apt install zram-tools
```

---

## Maintenance

### Backups

Create a backup of the SD card periodically:

```bash
# On another machine with the SD card inserted:
sudo dd if=/dev/sdX of=traffic-eye-backup-$(date +%Y%m%d).img bs=4M status=progress
```

Or back up just the data and config:

```bash
# On the Pi:
tar czf /tmp/traffic-eye-backup.tar.gz \
    /opt/traffic-eye/config/ \
    /var/lib/traffic-eye/db/ \
    /etc/traffic-eye.env
```

### Updating Traffic-Eye

```bash
# Stop the service
sudo systemctl stop traffic-eye

# Pull latest code
cd /tmp/traffic-eye
git pull

# Re-run setup (idempotent)
sudo bash scripts/setup.sh --skip-reboot

# Restart
sudo systemctl start traffic-eye
```

### Log Management

Logs are managed by log2ram (in-memory) and logrotate (7-day retention with compression).

```bash
# Check log sizes
du -sh /var/log/traffic-eye/

# View rotated logs
ls -la /var/log/traffic-eye/

# Force log rotation
sudo logrotate -f /etc/logrotate.d/traffic-eye
```

---

## Performance Expectations

### Raspberry Pi 4 (4GB RAM)

| Metric | Expected Value |
|--------|---------------|
| Detection FPS | 4-6 fps (YOLOv8n INT8, 4 threads) |
| Base memory usage | ~300 MB |
| With frame buffer | ~450 MB |
| CPU usage (detection active) | 70-85% |
| CPU temperature (with heatsink) | 55-65C |
| CPU temperature (with fan) | 45-55C |
| SD card writes | Minimal (log2ram enabled) |
| Battery life (10000mAh) | 3-4 hours (full load) |
| Battery life (duty cycling) | 6+ hours |
| Boot to detection running | ~45 seconds |

### Optimization Tips

1. **Reduce resolution**: Change `camera.resolution` from `[1280, 720]` to `[960, 540]` for faster inference at the cost of detection range.
2. **Increase frame skip**: Change `camera.process_every_nth_frame` from 5 to 8 to reduce CPU load.
3. **Reduce buffer**: Lower `camera.buffer_seconds` to reduce memory usage.
4. **Use INT8 models**: Always use quantized INT8 TFLite models on the Pi.
5. **Disable unused features**: If not using GPS or cloud verification, disable them in config.
