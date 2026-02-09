# scripts/

Setup, deployment, and utility scripts for Traffic-Eye.

## Files

| File | Purpose | Run As |
|------|---------|--------|
| `setup.sh` | Automated Raspberry Pi deployment | `sudo` |
| `harden.sh` | Security hardening (firewall, SSH, fail2ban) | `sudo` |
| `health_check.sh` | System health monitoring | `sudo` (via cron) |
| `export_yolov8n_tflite.py` | Export YOLOv8n to TFLite format | user |

## setup.sh -- Pi Deployment

Fully automated setup script that installs Traffic-Eye on a fresh Raspberry Pi OS Lite (64-bit, Bookworm). Designed to be **idempotent** -- safe to run multiple times.

### Usage

```bash
sudo bash scripts/setup.sh               # Full install
sudo bash scripts/setup.sh --skip-reboot  # No reboot prompt
```

### What It Does (8 Steps)

1. **Preflight checks** -- verifies root, Pi detection, disk space, internet, source directory
2. **System packages** -- installs python3-venv, picamera2, ffmpeg, gpsd, i2c-tools, build-essential, and more
3. **Pi hardware** -- enables camera (non-interactive raspi-config), sets GPU memory to 128MB, enables I2C
4. **Directory structure** -- creates `/opt/traffic-eye`, `/var/lib/traffic-eye`, `/var/log/traffic-eye`
5. **Python environment** -- creates venv with `--system-site-packages`, installs all pip dependencies
6. **Project files** -- copies src, config, models, tests, scripts; generates `settings_pi.yaml`
7. **systemd services** -- installs and enables service units and timers
8. **log2ram** -- installs log2ram for SD card longevity, configures logrotate
9. **Health monitoring** -- installs cron job for 15-minute health checks

### Features

- Color-coded progress output with step indicators
- Comprehensive error handling with line-number reporting
- ERR trap for clean failure messages
- Idempotent: checks for existing directories, venv, and configs before creating
- Supports non-Pi platforms (skips hardware steps gracefully)
- Creates `/etc/traffic-eye.env` template for credentials

## harden.sh -- Security Hardening

Interactive security hardening script. Each step asks for confirmation.

### Usage

```bash
sudo bash scripts/harden.sh           # Interactive
sudo bash scripts/harden.sh --yes     # Apply all
sudo bash scripts/harden.sh --dry-run # Preview only
```

### What It Does

1. **System updates** -- applies pending security patches
2. **UFW firewall** -- deny incoming, allow SSH, optionally allow GPS UDP
3. **SSH hardening** -- disable root login, limit retries, strong ciphers
4. **fail2ban** -- bans IPs after 3 failed SSH attempts
5. **Default user** -- locks `pi` account or forces password change
6. **Disable services** -- Bluetooth, Avahi, ModemManager, triggerhappy
7. **Kernel hardening** -- sysctl parameters (anti-spoofing, SYN cookies)
8. **Auto updates** -- unattended-upgrades for security patches

## health_check.sh -- Health Monitoring

Monitors system health. Runs via cron every 15 minutes (installed by setup.sh).

### Usage

```bash
sudo bash scripts/health_check.sh            # Text output
sudo bash scripts/health_check.sh --json     # JSON output
sudo bash scripts/health_check.sh --verbose  # Verbose mode
```

### Checks

| Check | Warning | Critical |
|-------|---------|----------|
| CPU temperature | >= 70C | >= 80C |
| Disk usage | >= 80% | >= 90% |
| Memory usage | >= 85% | -- |
| Undervoltage | -- | Active now |
| Throttling | Historical | Active now |
| Service status | Not enabled | Enabled but stopped |
| Journal errors | > 10 in 15min | -- |

### Output

- Text report to stdout (logged to `/var/log/traffic-eye/health.log`)
- Critical alerts written to `/var/log/traffic-eye/alerts.log`
- Optional email alerts (configure `TRAFFIC_EYE_ALERT_EMAIL` in `/etc/traffic-eye.env`)
- JSON mode for integration with external monitoring systems

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | OK -- all checks passed |
| 1 | WARNING -- non-critical issues |
| 2 | CRITICAL -- immediate attention needed |
| 3 | UNKNOWN -- check failed to run |
