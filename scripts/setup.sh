#!/usr/bin/env bash
# =============================================================================
# Traffic-Eye: Automated Raspberry Pi Deployment Script
# =============================================================================
#
# Installs and configures Traffic-Eye on a fresh Raspberry Pi OS Lite (64-bit,
# Bookworm). Designed to be idempotent -- safe to run multiple times.
#
# Usage:
#   sudo bash scripts/setup.sh            # Full install
#   sudo bash scripts/setup.sh --skip-reboot  # Install without final reboot prompt
#
# Prerequisites:
#   - Raspberry Pi 4 (4GB+ RAM) or Pi 5
#   - Raspberry Pi OS Lite 64-bit (Bookworm)
#   - Internet connection
#   - Pi Camera Module connected
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
readonly SCRIPT_VERSION="1.0.0"
readonly PROJECT_DIR="/opt/traffic-eye"
readonly DATA_DIR="/var/lib/traffic-eye"
readonly LOG_DIR="/var/log/traffic-eye"
readonly VENV_DIR="${PROJECT_DIR}/venv"
readonly ENV_FILE="/etc/traffic-eye.env"
readonly BOOT_CONFIG="/boot/firmware/config.txt"
readonly BOOT_CONFIG_LEGACY="/boot/config.txt"
readonly MIN_GPU_MEM=128
readonly REQUIRED_DISK_MB=500

# Derive source directory from this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")"

# ---------------------------------------------------------------------------
# Color helpers (degrade gracefully if not a terminal)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()    { echo -e "\n${BLUE}${BOLD}>>> $*${NC}"; }
log_substep() { echo -e "    ${BOLD}-${NC} $*"; }

# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
on_error() {
    local line=$1
    log_error "Script failed at line ${line}."
    log_error "Review the output above for details."
    log_error "You can safely re-run this script after fixing the issue."
    exit 1
}
trap 'on_error ${LINENO}' ERR

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
preflight_checks() {
    log_step "Preflight checks"

    # Must run as root
    if [ "$(id -u)" -ne 0 ]; then
        log_error "This script must be run as root. Use: sudo bash $0"
        exit 1
    fi

    # Determine the real (non-root) user who invoked sudo
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        DEPLOY_USER="$SUDO_USER"
    else
        DEPLOY_USER="$(logname 2>/dev/null || echo "pi")"
    fi
    DEPLOY_GROUP="$(id -gn "$DEPLOY_USER" 2>/dev/null || echo "$DEPLOY_USER")"
    log_substep "Deploy user: ${DEPLOY_USER} (group: ${DEPLOY_GROUP})"

    # Check if running on a Raspberry Pi
    if grep -q "Raspberry\|BCM" /proc/cpuinfo 2>/dev/null; then
        PI_MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Unknown Pi")
        log_substep "Detected: ${PI_MODEL}"
        IS_PI=true
    else
        log_warn "This does not appear to be a Raspberry Pi."
        log_warn "Hardware-specific steps (camera, GPU memory) will be skipped."
        IS_PI=false
    fi

    # Check architecture
    ARCH=$(uname -m)
    log_substep "Architecture: ${ARCH}"
    if [ "$ARCH" != "aarch64" ] && [ "$IS_PI" = true ]; then
        log_warn "Expected aarch64 (64-bit OS). Some packages may not work on 32-bit."
    fi

    # Check available disk space
    AVAIL_MB=$(df -BM --output=avail / | tail -1 | tr -d 'M ')
    log_substep "Available disk space: ${AVAIL_MB}MB"
    if [ "$AVAIL_MB" -lt "$REQUIRED_DISK_MB" ]; then
        log_error "Insufficient disk space. Need at least ${REQUIRED_DISK_MB}MB, have ${AVAIL_MB}MB."
        exit 1
    fi

    # Check internet connectivity
    if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
        log_substep "Internet connectivity: OK"
    else
        log_warn "No internet connectivity detected. Package installation may fail."
    fi

    # Check source directory
    if [ ! -d "$SRC_DIR/src" ]; then
        log_error "Source directory not found at ${SRC_DIR}/src"
        log_error "Run this script from the project root: sudo bash scripts/setup.sh"
        exit 1
    fi
    log_substep "Source directory: ${SRC_DIR}"

    log_info "Preflight checks passed."
}

# ---------------------------------------------------------------------------
# Step 1: System packages
# ---------------------------------------------------------------------------
install_system_packages() {
    log_step "Step 1/8: Installing system packages"

    log_substep "Updating package lists..."
    apt-get update -qq

    local packages=(
        # Python
        python3-pip
        python3-venv
        python3-dev
        python3-setuptools
        # Camera (Pi-specific, but harmless to install elsewhere)
        python3-picamera2
        python3-libcamera
        libcamera-tools
        # Media
        ffmpeg
        # GPS
        gpsd
        gpsd-clients
        # I2C tools (for sensor expansion)
        i2c-tools
        python3-smbus
        # Build dependencies for native Python packages
        build-essential
        libatlas-base-dev
        libjpeg-dev
        libopenjp2-7
        libssl-dev
        libffi-dev
        # System utilities
        git
        curl
        htop
        iotop
        lsof
        # Monitoring
        bc
    )

    log_substep "Installing ${#packages[@]} packages..."
    # Use --no-install-recommends to save disk space on Pi
    apt-get install -y --no-install-recommends "${packages[@]}" 2>&1 | \
        while IFS= read -r line; do
            # Show only package installation progress, not verbose apt output
            if [[ "$line" == *"Setting up"* ]] || [[ "$line" == *"is already the newest"* ]]; then
                echo "    $line"
            fi
        done || {
            log_warn "Some packages may have failed to install. Continuing..."
        }

    log_info "System packages installed."
}

# ---------------------------------------------------------------------------
# Step 2: Pi hardware configuration
# ---------------------------------------------------------------------------
configure_pi_hardware() {
    log_step "Step 2/8: Configuring Pi hardware"

    if [ "$IS_PI" != true ]; then
        log_substep "Skipping hardware configuration (not a Raspberry Pi)."
        return 0
    fi

    # Determine boot config path (Bookworm uses /boot/firmware/, older uses /boot/)
    local boot_config=""
    if [ -f "$BOOT_CONFIG" ]; then
        boot_config="$BOOT_CONFIG"
    elif [ -f "$BOOT_CONFIG_LEGACY" ]; then
        boot_config="$BOOT_CONFIG_LEGACY"
    else
        log_warn "Boot config not found. Skipping GPU/camera configuration."
        return 0
    fi
    log_substep "Boot config: ${boot_config}"

    NEEDS_REBOOT=false

    # Enable camera interface (non-interactive)
    log_substep "Enabling camera interface..."
    if command -v raspi-config >/dev/null 2>&1; then
        raspi-config nonint do_camera 0 2>/dev/null || true
    fi

    # On Bookworm, camera uses libcamera by default (no dtoverlay needed).
    # But ensure the legacy camera stack is disabled.
    if grep -q "^start_x=1" "$boot_config" 2>/dev/null; then
        log_substep "Disabling legacy camera stack (libcamera is preferred)..."
        sed -i 's/^start_x=1/# start_x=1  # Disabled by traffic-eye setup/' "$boot_config"
        NEEDS_REBOOT=true
    fi

    # Configure GPU memory (minimum 128MB for camera processing)
    local current_gpu_mem
    current_gpu_mem=$(grep -oP '^gpu_mem=\K\d+' "$boot_config" 2>/dev/null || echo "0")
    if [ "$current_gpu_mem" -lt "$MIN_GPU_MEM" ]; then
        if grep -q "^gpu_mem=" "$boot_config" 2>/dev/null; then
            log_substep "Updating GPU memory from ${current_gpu_mem}MB to ${MIN_GPU_MEM}MB..."
            sed -i "s/^gpu_mem=.*/gpu_mem=${MIN_GPU_MEM}/" "$boot_config"
        else
            log_substep "Setting GPU memory to ${MIN_GPU_MEM}MB..."
            echo "" >> "$boot_config"
            echo "# Traffic-Eye: GPU memory for camera processing" >> "$boot_config"
            echo "gpu_mem=${MIN_GPU_MEM}" >> "$boot_config"
        fi
        NEEDS_REBOOT=true
    else
        log_substep "GPU memory already set to ${current_gpu_mem}MB (>= ${MIN_GPU_MEM}MB). OK."
    fi

    # Enable I2C interface (for future sensor expansion)
    if command -v raspi-config >/dev/null 2>&1; then
        log_substep "Enabling I2C interface..."
        raspi-config nonint do_i2c 0 2>/dev/null || true
    fi

    if [ "$NEEDS_REBOOT" = true ]; then
        log_warn "Hardware configuration changed. A reboot is required."
    fi

    log_info "Pi hardware configured."
}

# ---------------------------------------------------------------------------
# Step 3: Directory structure
# ---------------------------------------------------------------------------
create_directories() {
    log_step "Step 3/8: Creating directory structure"

    local dirs=(
        "$PROJECT_DIR"
        "$PROJECT_DIR/models"
        "$PROJECT_DIR/config"
        "$DATA_DIR"
        "$DATA_DIR/evidence"
        "$DATA_DIR/queue"
        "$DATA_DIR/captures"
        "$DATA_DIR/db"
        "$LOG_DIR"
    )

    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_substep "Created: ${dir}"
        else
            log_substep "Exists:  ${dir}"
        fi
    done

    # Set ownership
    chown -R "${DEPLOY_USER}:${DEPLOY_GROUP}" "$PROJECT_DIR"
    chown -R "${DEPLOY_USER}:${DEPLOY_GROUP}" "$DATA_DIR"
    chown -R "${DEPLOY_USER}:${DEPLOY_GROUP}" "$LOG_DIR"

    log_info "Directory structure ready."
}

# ---------------------------------------------------------------------------
# Step 4: Python virtual environment and dependencies
# ---------------------------------------------------------------------------
setup_python_env() {
    log_step "Step 4/8: Setting up Python environment"

    # Create virtual environment with system site-packages
    # This is required so picamera2 (system-installed) is accessible
    if [ ! -f "${VENV_DIR}/bin/python" ]; then
        log_substep "Creating virtual environment at ${VENV_DIR}..."
        python3 -m venv --system-site-packages "$VENV_DIR"
    else
        log_substep "Virtual environment already exists at ${VENV_DIR}."
    fi

    # Activate venv for subsequent pip commands
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"

    log_substep "Upgrading pip..."
    pip install --upgrade pip setuptools wheel --quiet 2>&1 | tail -1 || true

    # Core dependencies from pyproject.toml
    log_substep "Installing core Python dependencies..."
    pip install --quiet \
        "pyyaml>=6.0" \
        "opencv-python-headless>=4.8" \
        "numpy>=1.24" \
        "Pillow>=10.0" \
        "jinja2>=3.1" \
        "psutil>=5.9" \
        "httpx>=0.25" \
        "schedule>=1.2" \
        "pynmea2>=1.18" \
        "geopy>=2.4" \
        2>&1 | tail -3

    # Pi-specific optional dependencies
    log_substep "Installing Pi-specific dependencies..."
    pip install --quiet "gps3" 2>&1 | tail -1 || log_warn "gps3 installation failed (non-critical)"

    # tflite-runtime: try multiple sources
    log_substep "Installing TFLite runtime..."
    if pip install --quiet "tflite-runtime" 2>/dev/null; then
        log_substep "tflite-runtime installed from PyPI."
    elif pip install --quiet "tflite-runtime" \
         --extra-index-url https://google-coral.github.io/py-repo/ 2>/dev/null; then
        log_substep "tflite-runtime installed from Coral repo."
    else
        log_warn "tflite-runtime not available for this platform."
        log_warn "Detection will not work without it. See models/README.md."
    fi

    # Install dev/test dependencies
    log_substep "Installing test dependencies..."
    pip install --quiet pytest pytest-cov 2>&1 | tail -1 || true

    # Install the project itself in editable mode (if pyproject.toml present)
    if [ -f "${PROJECT_DIR}/pyproject.toml" ]; then
        log_substep "Installing traffic-eye package..."
        pip install --quiet -e "${PROJECT_DIR}" 2>&1 | tail -1 || true
    fi

    deactivate

    # Set ownership of venv
    chown -R "${DEPLOY_USER}:${DEPLOY_GROUP}" "$VENV_DIR"

    log_info "Python environment ready."
}

# ---------------------------------------------------------------------------
# Step 5: Copy project files
# ---------------------------------------------------------------------------
copy_project_files() {
    log_step "Step 5/8: Copying project files"

    if [ ! -d "${SRC_DIR}/src" ]; then
        log_error "Source directory not found: ${SRC_DIR}/src"
        return 1
    fi

    # Copy source code
    log_substep "Copying src/..."
    cp -r "${SRC_DIR}/src" "${PROJECT_DIR}/"

    # Copy config files
    log_substep "Copying config/..."
    cp -r "${SRC_DIR}/config" "${PROJECT_DIR}/"

    # Copy models directory (may be empty / contain placeholders)
    log_substep "Copying models/..."
    cp -r "${SRC_DIR}/models" "${PROJECT_DIR}/" 2>/dev/null || true

    # Copy tests
    log_substep "Copying tests/..."
    cp -r "${SRC_DIR}/tests" "${PROJECT_DIR}/"

    # Copy build config
    log_substep "Copying pyproject.toml..."
    cp "${SRC_DIR}/pyproject.toml" "${PROJECT_DIR}/"

    # Copy scripts (including this one, for future re-runs)
    log_substep "Copying scripts/..."
    cp -r "${SRC_DIR}/scripts" "${PROJECT_DIR}/"

    # Generate Pi-specific configuration
    log_substep "Generating Pi-specific configuration..."
    cat > "${PROJECT_DIR}/config/settings_pi.yaml" << 'PICONFIG'
camera:
  resolution: [1280, 720]
  fps: 30
  process_every_nth_frame: 5
  buffer_seconds: 10

detection:
  model_path: "/opt/traffic-eye/models/yolov8n_int8.tflite"
  confidence_threshold: 0.5
  nms_threshold: 0.45
  num_threads: 4
  target_classes:
    - person
    - motorcycle
    - car
    - truck
    - bus
    - bicycle
    - traffic light

helmet:
  model_path: "/opt/traffic-eye/models/helmet_cls_int8.tflite"
  confidence_threshold: 0.85

ocr:
  engine: "paddleocr"
  confidence_threshold: 0.6

violations:
  cooldown_seconds: 30
  max_reports_per_hour: 20

gps:
  required: false
  speed_gate_kmh: 5

reporting:
  evidence_dir: "/var/lib/traffic-eye/evidence"
  queue_dir: "/var/lib/traffic-eye/queue"
  best_frames_count: 3
  clip_before_seconds: 2
  clip_after_seconds: 3
  email:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender: ""
    password_env: "TRAFFIC_EYE_EMAIL_PASSWORD"
    recipients: []

cloud:
  provider: "gemini"
  api_key_env: "TRAFFIC_EYE_CLOUD_API_KEY"
  confidence_threshold: 0.96
  max_retries: 3
  timeout_seconds: 30

storage:
  max_usage_percent: 80
  evidence_retention_days: 30
  non_violation_retention_hours: 1

thermal:
  throttle_temp_c: 75
  pause_temp_c: 80
  pause_duration_seconds: 30

logging:
  level: "INFO"
  json_format: false
  log_dir: "/var/log/traffic-eye"

platform: "pi"
PICONFIG

    # Create environment file template (if not exists)
    if [ ! -f "$ENV_FILE" ]; then
        log_substep "Creating environment file template at ${ENV_FILE}..."
        cat > "$ENV_FILE" << 'ENVFILE'
# Traffic-Eye environment variables
# Fill in your credentials and uncomment the lines below.
#
# SMTP password for sending violation email reports
#TRAFFIC_EYE_EMAIL_PASSWORD=your-smtp-app-password
#
# API key for cloud verification (Gemini or OpenAI)
#TRAFFIC_EYE_CLOUD_API_KEY=your-api-key
ENVFILE
        chmod 600 "$ENV_FILE"
        log_substep "Environment file permissions set to 600 (root-only read)."
    else
        log_substep "Environment file already exists at ${ENV_FILE}."
    fi

    # Fix ownership on everything we copied
    chown -R "${DEPLOY_USER}:${DEPLOY_GROUP}" "$PROJECT_DIR"

    log_info "Project files copied."
}

# ---------------------------------------------------------------------------
# Step 6: systemd services
# ---------------------------------------------------------------------------
install_systemd_services() {
    log_step "Step 6/8: Installing systemd services"

    local service_dir="${SRC_DIR}/systemd"
    if [ ! -d "$service_dir" ]; then
        log_warn "No systemd directory found at ${service_dir}. Skipping."
        return 0
    fi

    # Copy service files
    for unit_file in "${service_dir}"/*.service "${service_dir}"/*.timer; do
        [ -f "$unit_file" ] || continue
        local basename
        basename=$(basename "$unit_file")
        log_substep "Installing ${basename}..."
        cp "$unit_file" "/etc/systemd/system/${basename}"
    done

    # Reload systemd
    log_substep "Reloading systemd daemon..."
    systemctl daemon-reload

    # Enable services (but do not start yet -- user may need to configure first)
    log_substep "Enabling traffic-eye.service..."
    systemctl enable traffic-eye.service 2>/dev/null || true

    log_substep "Enabling traffic-eye-sender.timer..."
    systemctl enable traffic-eye-sender.timer 2>/dev/null || true

    log_info "systemd services installed and enabled."
    log_info "Services will start on next boot, or start manually with:"
    log_info "  sudo systemctl start traffic-eye"
}

# ---------------------------------------------------------------------------
# Step 7: log2ram (reduce SD card writes)
# ---------------------------------------------------------------------------
setup_log2ram() {
    log_step "Step 7/8: Setting up log2ram (SD card longevity)"

    if command -v log2ram >/dev/null 2>&1; then
        log_substep "log2ram is already installed."
    else
        log_substep "Installing log2ram..."
        # log2ram is not in the default repos; install from the official GitHub
        if curl -fsSL https://github.com/azlux/log2ram/archive/master.tar.gz -o /tmp/log2ram.tar.gz 2>/dev/null; then
            tar -xzf /tmp/log2ram.tar.gz -C /tmp/
            cd /tmp/log2ram-master
            chmod +x install.sh
            ./install.sh 2>&1 | tail -5 || log_warn "log2ram install script returned non-zero."
            cd - >/dev/null
            rm -rf /tmp/log2ram-master /tmp/log2ram.tar.gz
        else
            log_warn "Could not download log2ram. Skipping."
            log_warn "Install manually: https://github.com/azlux/log2ram"
            return 0
        fi
    fi

    # Configure log2ram
    local log2ram_conf="/etc/log2ram.conf"
    if [ -f "$log2ram_conf" ]; then
        log_substep "Configuring log2ram..."
        # Set RAM size for logs to 100MB (default is 40MB)
        sed -i 's/^SIZE=.*/SIZE=100M/' "$log2ram_conf" 2>/dev/null || true
        # Use rsync for better sync
        sed -i 's/^USE_RSYNC=.*/USE_RSYNC=true/' "$log2ram_conf" 2>/dev/null || true
        # Enable compression
        sed -i 's/^COMP_ALG=.*/COMP_ALG=zstd/' "$log2ram_conf" 2>/dev/null || true
        sed -i 's/^LOG_DISK_SIZE=.*/LOG_DISK_SIZE=200M/' "$log2ram_conf" 2>/dev/null || true
        log_substep "log2ram configured: 100MB RAM, zstd compression."
    fi

    # Enable log2ram service
    systemctl enable log2ram 2>/dev/null || true

    # Set up logrotate for traffic-eye logs
    log_substep "Configuring logrotate for traffic-eye..."
    cat > /etc/logrotate.d/traffic-eye << 'LOGROTATE'
/var/log/traffic-eye/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        systemctl reload traffic-eye.service > /dev/null 2>&1 || true
    endscript
}
LOGROTATE

    log_info "log2ram and logrotate configured."
}

# ---------------------------------------------------------------------------
# Step 8: Health check and cron
# ---------------------------------------------------------------------------
install_health_check() {
    log_step "Step 8/8: Installing health monitoring"

    local health_script="${PROJECT_DIR}/scripts/health_check.sh"
    if [ -f "${SRC_DIR}/scripts/health_check.sh" ]; then
        log_substep "Health check script found in source. Copying..."
        cp "${SRC_DIR}/scripts/health_check.sh" "$health_script"
        chmod +x "$health_script"
    else
        log_substep "Health check script not found in source. It will be installed separately."
    fi

    # Install cron job for health checks (every 15 minutes)
    local cron_file="/etc/cron.d/traffic-eye-health"
    log_substep "Installing health check cron job..."
    cat > "$cron_file" << CRON
# Traffic-Eye health monitoring -- runs every 15 minutes
*/15 * * * * root ${PROJECT_DIR}/scripts/health_check.sh >> /var/log/traffic-eye/health.log 2>&1
CRON
    chmod 644 "$cron_file"

    log_info "Health monitoring installed (runs every 15 minutes)."
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}=============================================${NC}"
    echo -e "${GREEN}${BOLD}   Traffic-Eye Setup Complete (v${SCRIPT_VERSION})${NC}"
    echo -e "${GREEN}${BOLD}=============================================${NC}"
    echo ""
    echo -e "  Project directory:  ${BOLD}${PROJECT_DIR}${NC}"
    echo -e "  Data directory:     ${BOLD}${DATA_DIR}${NC}"
    echo -e "  Log directory:      ${BOLD}${LOG_DIR}${NC}"
    echo -e "  Virtual env:        ${BOLD}${VENV_DIR}${NC}"
    echo -e "  Environment file:   ${BOLD}${ENV_FILE}${NC}"
    echo -e "  Deploy user:        ${BOLD}${DEPLOY_USER}${NC}"
    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo ""
    echo "  1. Place TFLite model files in ${PROJECT_DIR}/models/:"
    echo "       - yolov8n_int8.tflite    (object detection)"
    echo "       - helmet_cls_int8.tflite  (helmet classifier)"
    echo ""
    echo "  2. Configure credentials in ${ENV_FILE}:"
    echo "       sudo nano ${ENV_FILE}"
    echo ""
    echo "  3. Test in mock mode:"
    echo "       source ${VENV_DIR}/bin/activate"
    echo "       cd ${PROJECT_DIR}"
    echo "       python -m src.main --config config/settings_pi.yaml --mock"
    echo ""
    echo "  4. Start the service:"
    echo "       sudo systemctl start traffic-eye"
    echo "       sudo systemctl start traffic-eye-sender.timer"
    echo ""
    echo "  5. Monitor:"
    echo "       sudo journalctl -u traffic-eye -f"
    echo "       sudo systemctl status traffic-eye"
    echo ""

    if [ "${NEEDS_REBOOT:-false}" = true ]; then
        echo -e "  ${YELLOW}${BOLD}** A REBOOT IS REQUIRED for hardware changes to take effect. **${NC}"
        echo ""
        if [[ "${1:-}" != "--skip-reboot" ]]; then
            read -rp "  Reboot now? [y/N] " answer
            if [[ "$answer" =~ ^[Yy]$ ]]; then
                log_info "Rebooting..."
                reboot
            fi
        fi
    fi

    echo -e "  Run ${BOLD}sudo bash ${PROJECT_DIR}/scripts/harden.sh${NC} for security hardening."
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo -e "${BOLD}Traffic-Eye Deployment Script v${SCRIPT_VERSION}${NC}"
    echo -e "${BOLD}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""

    local start_time
    start_time=$(date +%s)

    preflight_checks
    install_system_packages
    configure_pi_hardware
    create_directories
    setup_python_env
    copy_project_files
    install_systemd_services
    setup_log2ram
    install_health_check

    local elapsed=$(( $(date +%s) - start_time ))
    log_info "Total setup time: ${elapsed} seconds."

    print_summary "$@"
}

main "$@"
