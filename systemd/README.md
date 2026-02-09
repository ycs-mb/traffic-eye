# systemd/

Systemd service and timer files for running Traffic-Eye as a managed background service on Raspberry Pi.

## Files

| File | Purpose |
|------|---------|
| `traffic-eye.service` | Main detection service (always running) |
| `traffic-eye-sender.service` | Email and cloud queue processor (oneshot) |
| `traffic-eye-sender.timer` | Timer that triggers the sender every 5 minutes |

## traffic-eye.service

The main detection loop. Runs continuously, processing camera frames and detecting violations.

### Key Settings

| Setting | Value | Description |
|---------|-------|-------------|
| Type | notify | Supports sd_notify watchdog |
| User | yashcs | Non-root user |
| WorkingDirectory | /opt/traffic-eye | Project root |
| Restart | on-failure | Auto-restart after crashes |
| RestartSec | 10 | Wait 10 seconds before restart |
| WatchdogSec | 30 | Must send heartbeat within 30s |
| MemoryMax | 2G | Hard memory limit |
| MemoryHigh | 1536M | Soft memory limit (triggers reclaim) |
| CPUQuota | 90% | CPU usage cap |
| TasksMax | 64 | Maximum spawned tasks |
| StartLimitBurst | 5 | Max 5 restarts per 5 minutes |

### Security Hardening

| Directive | Effect |
|-----------|--------|
| `ProtectSystem=strict` | Filesystem is read-only except allowed paths |
| `ReadWritePaths` | Only `/var/lib/traffic-eye` and `/var/log/traffic-eye` are writable |
| `ReadOnlyPaths` | `/opt/traffic-eye` is explicitly read-only |
| `ProtectHome=true` | Home directories are inaccessible |
| `NoNewPrivileges=true` | Cannot escalate privileges |
| `PrivateTmp=true` | Isolated /tmp namespace |
| `ProtectKernelTunables=true` | No writing to /proc/sys |
| `ProtectKernelModules=true` | Cannot load kernel modules |
| `ProtectControlGroups=true` | Cannot modify cgroups |
| `RestrictRealtime=true` | Cannot use realtime scheduling |
| `RestrictSUIDSGID=true` | Cannot create SUID/SGID files |
| `RestrictNamespaces=true` | Cannot create new namespaces |
| `SystemCallArchitectures=native` | Only native syscalls allowed |

### Device Access

The service needs access to camera and optionally GPS/I2C devices:

| Device | Purpose |
|--------|---------|
| `/dev/video*` | Camera (V4L2) |
| `/dev/vchiq` | Pi camera (VideoCore) |
| `/dev/gpiomem` | GPIO access |
| `/dev/i2c-*` | I2C sensors |
| `/dev/ttyAMA*`, `/dev/ttyS*` | UART GPS |

The service user is added to supplementary groups: `video`, `gpio`, `i2c`, `dialout`.

### Dependencies

- `After=network.target gpsd.service multi-user.target camera.service`
- `Wants=gpsd.service` -- requests GPS daemon (non-fatal if absent)

### Environment

- `PYTHONUNBUFFERED=1` -- ensure Python output is not buffered
- `TRAFFIC_EYE_CONFIG` -- path to config file
- `EnvironmentFile=-/etc/traffic-eye.env` -- credentials (the `-` means no error if missing)

## traffic-eye-sender.service

Oneshot service that processes pending email and cloud verification queues. Triggered by the timer.

### What it Does

1. Loads the Pi-specific config
2. Connects to the SQLite database
3. Processes the email queue (sends pending violation reports)
4. Closes the database

### Conditions

- `ConditionPathExists=/var/lib/traffic-eye/db` -- only runs if the database directory exists (i.e., after the main service has run at least once)

### Security

Same hardening as the main service. Additionally uses a 5-minute timeout for cloud API calls.

## traffic-eye-sender.timer

Triggers `traffic-eye-sender.service` on a schedule.

| Setting | Value | Description |
|---------|-------|-------------|
| OnBootSec | 2min | First run 2 minutes after boot |
| OnUnitActiveSec | 5min | Then every 5 minutes |
| Persistent | true | Run missed triggers after sleep/downtime |
| RandomizedDelaySec | 30 | Jitter to avoid thundering herd |

## Installation

The `scripts/setup.sh` script automatically installs these files. To install manually:

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload
```

## Usage

```bash
# Enable and start the main detection service
sudo systemctl enable traffic-eye
sudo systemctl start traffic-eye

# Enable and start the sender timer
sudo systemctl enable traffic-eye-sender.timer
sudo systemctl start traffic-eye-sender.timer

# Check status
sudo systemctl status traffic-eye
sudo systemctl status traffic-eye-sender.timer

# View logs
sudo journalctl -u traffic-eye -f              # Follow main service logs
sudo journalctl -u traffic-eye-sender -f        # Follow sender logs
sudo journalctl -u traffic-eye --since "1 hour ago"
sudo journalctl -u traffic-eye -p err           # Errors only

# Stop the service
sudo systemctl stop traffic-eye

# Disable auto-start on boot
sudo systemctl disable traffic-eye
```

## Customizing the User

The services run as user `yashcs`. To change this:

1. Edit both `.service` files:
   ```ini
   User=your-username
   Group=your-username
   ```

2. Ensure the user is in the required groups:
   ```bash
   sudo usermod -aG video,gpio,i2c,dialout your-username
   ```

3. Ensure the user has access to:
   - `/opt/traffic-eye/` (read)
   - `/var/lib/traffic-eye/` (read+write)
   - `/var/log/traffic-eye/` (read+write)

4. Reload and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart traffic-eye
   ```

## Adding Environment Variables

Credentials are stored in `/etc/traffic-eye.env` (created by setup.sh):

```bash
sudo nano /etc/traffic-eye.env
```

Add:

```
TRAFFIC_EYE_EMAIL_PASSWORD=your-smtp-app-password
TRAFFIC_EYE_CLOUD_API_KEY=your-gemini-api-key
TRAFFIC_EYE_ALERT_EMAIL=alerts@example.com
```

The file has permissions `600` (root-only read). The `-` prefix on `EnvironmentFile` means the service will start even if the file does not exist.

## Architecture

```
                          systemd
                       /          \
              traffic-eye       traffic-eye-sender.timer
              (always on)              |
                  |               (every 5 min)
                  |                    |
            Detection Loop     traffic-eye-sender
            - Camera capture   - Process email queue
            - ML inference     - Send pending reports
            - Rule evaluation
            - Evidence save
                  |                    |
                  v                    v
            /var/lib/traffic-eye/
            +-- db/traffic_eye.db  (shared SQLite - WAL mode)
            +-- evidence/          (JPEG frames, video clips)
            +-- queue/             (offline evidence queue)
            +-- captures/          (periodic frame snapshots)
```

Both services share the same SQLite database using WAL mode, which allows concurrent readers and writers safely.
