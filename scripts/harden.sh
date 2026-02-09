#!/usr/bin/env bash
# =============================================================================
# Traffic-Eye: Security Hardening Script
# =============================================================================
#
# Applies security hardening to a Raspberry Pi running Traffic-Eye.
# Run after setup.sh. Each step is optional and asks for confirmation
# unless --yes is passed.
#
# Usage:
#   sudo bash scripts/harden.sh           # Interactive mode
#   sudo bash scripts/harden.sh --yes     # Apply all without prompts
#   sudo bash scripts/harden.sh --dry-run # Show what would be done
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AUTO_YES=false
DRY_RUN=false
SSH_PORT=22

for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=true ;;
        --dry-run|-n) DRY_RUN=true ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
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

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()  { echo -e "\n${BLUE}${BOLD}>>> $*${NC}"; }

confirm() {
    if [ "$AUTO_YES" = true ]; then
        return 0
    fi
    local prompt="$1 [y/N] "
    read -rp "$prompt" answer
    [[ "$answer" =~ ^[Yy]$ ]]
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY RUN] $*"
        return 0
    fi
    "$@"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run as root. Use: sudo bash $0"
    exit 1
fi

DEPLOY_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "pi")}"

echo ""
echo -e "${BOLD}Traffic-Eye Security Hardening${NC}"
echo -e "Running as: root (deploy user: ${DEPLOY_USER})"
echo -e "Mode: $([ "$DRY_RUN" = true ] && echo "DRY RUN" || echo "LIVE")"
echo ""

# ---------------------------------------------------------------------------
# Step 1: System Updates
# ---------------------------------------------------------------------------
log_step "Step 1: System Updates"

if confirm "Apply all pending security updates?"; then
    log_info "Updating system packages..."
    run_cmd apt-get update -qq
    run_cmd apt-get upgrade -y
    log_info "System updated."
else
    log_warn "Skipping system updates."
fi

# ---------------------------------------------------------------------------
# Step 2: UFW Firewall
# ---------------------------------------------------------------------------
log_step "Step 2: UFW Firewall"

if confirm "Configure UFW firewall (deny all incoming, allow SSH on port ${SSH_PORT})?"; then
    if ! command -v ufw >/dev/null 2>&1; then
        log_info "Installing UFW..."
        run_cmd apt-get install -y ufw
    fi

    log_info "Configuring UFW rules..."
    run_cmd ufw default deny incoming
    run_cmd ufw default allow outgoing

    # Allow SSH
    run_cmd ufw allow "${SSH_PORT}/tcp" comment "SSH"

    # Allow GPS network receiver (if using phone GPS over WiFi)
    # Only on local network
    if confirm "  Allow UDP port 10110 for network GPS receiver (local only)?"; then
        run_cmd ufw allow from 192.168.0.0/16 to any port 10110 proto udp comment "GPS-network"
        run_cmd ufw allow from 10.0.0.0/8 to any port 10110 proto udp comment "GPS-network"
    fi

    # Enable UFW
    if [ "$DRY_RUN" = false ]; then
        echo "y" | ufw enable
    else
        echo "  [DRY RUN] ufw enable"
    fi

    log_info "UFW firewall configured and enabled."
    ufw status verbose 2>/dev/null || true
else
    log_warn "Skipping firewall configuration."
fi

# ---------------------------------------------------------------------------
# Step 3: SSH Hardening
# ---------------------------------------------------------------------------
log_step "Step 3: SSH Hardening"

SSHD_CONFIG="/etc/ssh/sshd_config"

if confirm "Harden SSH configuration?"; then
    # Backup original
    if [ ! -f "${SSHD_CONFIG}.backup-original" ]; then
        run_cmd cp "$SSHD_CONFIG" "${SSHD_CONFIG}.backup-original"
    fi

    log_info "Applying SSH hardening..."

    # Create a drop-in config for our hardening
    hardening_conf="/etc/ssh/sshd_config.d/traffic-eye-hardening.conf"
    if [ "$DRY_RUN" = false ]; then
        cat > "$hardening_conf" << 'SSHCONF'
# Traffic-Eye SSH Hardening
# Applied by scripts/harden.sh

# Disable root login
PermitRootLogin no

# Disable password authentication (use SSH keys only)
# Uncomment the line below AFTER setting up SSH keys:
# PasswordAuthentication no

# Disable empty passwords
PermitEmptyPasswords no

# Limit authentication attempts
MaxAuthTries 3
MaxSessions 3

# Timeout for idle sessions (5 minutes)
ClientAliveInterval 300
ClientAliveCountMax 2

# Disable X11 forwarding (not needed for headless Pi)
X11Forwarding no

# Disable TCP forwarding (uncomment if not needed)
# AllowTcpForwarding no

# Only allow specific user(s)
# Uncomment and adjust after verifying your username:
# AllowUsers yashcs

# Use strong crypto
KexAlgorithms curve25519-sha256@libssh.org,curve25519-sha256
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com
SSHCONF
    fi

    # Validate SSH config before restarting
    if [ "$DRY_RUN" = false ]; then
        if sshd -t 2>/dev/null; then
            systemctl reload sshd 2>/dev/null || systemctl reload ssh 2>/dev/null || true
            log_info "SSH configuration applied and service reloaded."
        else
            log_error "SSH config validation failed. Reverting..."
            rm -f "$hardening_conf"
            log_error "Hardening config removed. SSH unchanged."
        fi
    fi

    echo ""
    echo -e "${YELLOW}IMPORTANT: SSH Key Setup Guide${NC}"
    echo ""
    echo "  On your LOCAL machine (laptop/desktop), run:"
    echo ""
    echo "    ssh-keygen -t ed25519 -C \"traffic-eye-pi\""
    echo "    ssh-copy-id -i ~/.ssh/id_ed25519.pub ${DEPLOY_USER}@<pi-ip-address>"
    echo ""
    echo "  After confirming key-based login works, enable password-less SSH:"
    echo "    sudo sed -i 's/# PasswordAuthentication no/PasswordAuthentication no/' ${hardening_conf:-/etc/ssh/sshd_config.d/traffic-eye-hardening.conf}"
    echo "    sudo systemctl reload sshd"
    echo ""
else
    log_warn "Skipping SSH hardening."
fi

# ---------------------------------------------------------------------------
# Step 4: fail2ban
# ---------------------------------------------------------------------------
log_step "Step 4: fail2ban (SSH brute-force protection)"

if confirm "Install and configure fail2ban?"; then
    if ! command -v fail2ban-client >/dev/null 2>&1; then
        log_info "Installing fail2ban..."
        run_cmd apt-get install -y fail2ban
    fi

    # Create local jail config
    if [ "$DRY_RUN" = false ]; then
        cat > /etc/fail2ban/jail.local << JAIL
# Traffic-Eye fail2ban configuration
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 3
backend  = systemd

[sshd]
enabled = true
port    = ${SSH_PORT}
filter  = sshd
maxretry = 3
bantime  = 3600
JAIL
    fi

    run_cmd systemctl enable fail2ban
    run_cmd systemctl restart fail2ban

    log_info "fail2ban installed and configured."
    fail2ban-client status 2>/dev/null || true
else
    log_warn "Skipping fail2ban."
fi

# ---------------------------------------------------------------------------
# Step 5: Disable Default Pi User
# ---------------------------------------------------------------------------
log_step "Step 5: Default User Security"

if id "pi" >/dev/null 2>&1 && [ "$DEPLOY_USER" != "pi" ]; then
    if confirm "Lock the default 'pi' user account (you are using '${DEPLOY_USER}')?"; then
        run_cmd passwd -l pi
        log_info "Default 'pi' user account locked."
    fi
elif id "pi" >/dev/null 2>&1 && [ "$DEPLOY_USER" = "pi" ]; then
    log_warn "You are using the default 'pi' user."
    echo "  It is recommended to:"
    echo "    1. Create a new user:  sudo adduser myuser"
    echo "    2. Add to sudo group:  sudo usermod -aG sudo,gpio,video,i2c,dialout myuser"
    echo "    3. Re-run setup.sh and this script as the new user"
    echo ""
    if confirm "Force password change for 'pi' user on next login?"; then
        run_cmd passwd -e pi
        log_info "Password change will be required on next login."
    fi
fi

# ---------------------------------------------------------------------------
# Step 6: Disable Unused Services
# ---------------------------------------------------------------------------
log_step "Step 6: Disable Unused Services"

# List of services that are typically not needed on a headless traffic cam
UNUSED_SERVICES=(
    "bluetooth.service"
    "hciuart.service"
    "avahi-daemon.service"
    "triggerhappy.service"
    "ModemManager.service"
)

for svc in "${UNUSED_SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null || systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        if confirm "Disable unused service: ${svc}?"; then
            run_cmd systemctl stop "$svc" 2>/dev/null || true
            run_cmd systemctl disable "$svc" 2>/dev/null || true
            run_cmd systemctl mask "$svc" 2>/dev/null || true
            log_info "Disabled: ${svc}"
        fi
    fi
done

# Disable Bluetooth in boot config
if [ -f /boot/firmware/config.txt ]; then
    if ! grep -q "^dtoverlay=disable-bt" /boot/firmware/config.txt 2>/dev/null; then
        if confirm "Disable Bluetooth hardware in boot config?"; then
            if [ "$DRY_RUN" = false ]; then
                echo "" >> /boot/firmware/config.txt
                echo "# Disabled by traffic-eye hardening" >> /boot/firmware/config.txt
                echo "dtoverlay=disable-bt" >> /boot/firmware/config.txt
            fi
            log_info "Bluetooth hardware will be disabled on next boot."
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Step 7: Kernel Hardening (sysctl)
# ---------------------------------------------------------------------------
log_step "Step 7: Kernel Hardening"

if confirm "Apply kernel security parameters (sysctl)?"; then
    if [ "$DRY_RUN" = false ]; then
        cat > /etc/sysctl.d/99-traffic-eye-hardening.conf << 'SYSCTL'
# Traffic-Eye kernel hardening

# Prevent IP spoofing
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Do not send ICMP redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Ignore broadcast pings
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Enable SYN cookies (prevent SYN flood)
net.ipv4.tcp_syncookies = 1

# Disable IPv6 (if not used)
# Uncomment if you do not need IPv6:
# net.ipv6.conf.all.disable_ipv6 = 1
# net.ipv6.conf.default.disable_ipv6 = 1

# Restrict dmesg access
kernel.dmesg_restrict = 1

# Restrict kernel pointer exposure
kernel.kptr_restrict = 2
SYSCTL
        sysctl --system --quiet 2>/dev/null || true
    fi
    log_info "Kernel security parameters applied."
else
    log_warn "Skipping kernel hardening."
fi

# ---------------------------------------------------------------------------
# Step 8: Automatic Security Updates
# ---------------------------------------------------------------------------
log_step "Step 8: Automatic Security Updates"

if confirm "Enable automatic security updates (unattended-upgrades)?"; then
    run_cmd apt-get install -y unattended-upgrades apt-listchanges

    if [ "$DRY_RUN" = false ]; then
        # Enable automatic security updates
        cat > /etc/apt/apt.conf.d/20auto-upgrades << 'AUTOUPGRADE'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
AUTOUPGRADE

        # Configure to only install security updates
        cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'UNATTENDED'
Unattended-Upgrade::Origins-Pattern {
    "origin=Debian,codename=${distro_codename},label=Debian-Security";
    "origin=Raspbian,codename=${distro_codename},label=Raspbian";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
UNATTENDED
    fi

    log_info "Automatic security updates enabled."
else
    log_warn "Skipping automatic updates."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}=============================================${NC}"
echo -e "${GREEN}${BOLD}   Security Hardening Complete${NC}"
echo -e "${GREEN}${BOLD}=============================================${NC}"
echo ""
echo "Applied hardening measures. Review the changes above."
echo ""
echo "Additional manual steps recommended:"
echo "  1. Set up SSH keys (see guide above)"
echo "  2. Enable PasswordAuthentication=no after key setup"
echo "  3. Review /etc/ssh/sshd_config.d/traffic-eye-hardening.conf"
echo "  4. Consider setting up a VPN (Tailscale or WireGuard) for remote access"
echo "  5. Run: sudo lynis audit system  (if lynis is installed) for a full audit"
echo ""
echo "To check firewall status:    sudo ufw status verbose"
echo "To check fail2ban status:    sudo fail2ban-client status sshd"
echo "To check blocked IPs:        sudo fail2ban-client status sshd"
echo ""
