#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Traffic-Eye Mac → Raspi Deployment Tool
# =============================================================================
# Usage:
#   ./scripts/deploy.sh <command>
#
# Commands:
#   setup        — First-time setup: copy SSH key, verify git on Pi
#   git-deploy   — Push to GitHub then pull on Pi (primary workflow)
#   quick-sync   — rsync changed files directly to Pi (fast iteration)
#   ssh          — Open SSH session to Pi
#   status       — Check Pi service status and health
#   restart      — Restart traffic-eye services on Pi
#   logs         — Tail live logs from Pi
#   install-deps — Install/update Python dependencies on Pi
# =============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
RASPI_HOST="raspi-te"                     # SSH alias (defined in ~/.ssh/config)
RASPI_USER="yashcs"
RASPI_IP="100.107.114.5"                  # Tailscale IP
RASPI_PROJECT_DIR="/home/yashcs/traffic-eye"
LOCAL_PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ── Helper Functions ───────────────────────────────────────────────────────────

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

run_on_pi() {
    ssh "${RASPI_HOST}" "$@"
}

check_ssh() {
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${RASPI_HOST}" "echo ok" &>/dev/null; then
        err "Cannot connect to Raspi via SSH alias '${RASPI_HOST}'"
        err "Run: ./scripts/deploy.sh setup"
        exit 1
    fi
}

# ── Commands ───────────────────────────────────────────────────────────────────

cmd_setup() {
    info "=== First-Time Setup ==="
    echo ""

    # Step 1: Check SSH config
    if ! grep -q "Host ${RASPI_HOST}" ~/.ssh/config 2>/dev/null; then
        info "Adding SSH config entry for '${RASPI_HOST}'..."
        cat >> ~/.ssh/config <<EOF

# Traffic-Eye Raspberry Pi (Tailscale)
Host ${RASPI_HOST}
    HostName ${RASPI_IP}
    User ${RASPI_USER}
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
    StrictHostKeyChecking accept-new
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF
        ok "SSH config entry added."
    else
        ok "SSH config entry '${RASPI_HOST}' already exists."
    fi

    # Step 2: Copy SSH key
    info "Copying SSH public key to Raspi (you'll need to enter password: 'ycs')..."
    ssh-copy-id -i ~/.ssh/id_ed25519.pub "${RASPI_HOST}" || {
        warn "ssh-copy-id failed. You may need to do this manually:"
        echo "  cat ~/.ssh/id_ed25519.pub | ssh ${RASPI_USER}@${RASPI_IP} 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'"
        return 1
    }
    ok "SSH key copied successfully."

    # Step 3: Verify passwordless SSH
    info "Verifying passwordless SSH..."
    if ssh -o BatchMode=yes "${RASPI_HOST}" "echo 'Passwordless SSH works!'" 2>/dev/null; then
        ok "Passwordless SSH verified!"
    else
        err "Passwordless SSH not working. Check your key setup."
        return 1
    fi

    # Step 4: Verify git repo on Pi
    info "Checking git repo on Raspi..."
    if run_on_pi "test -d ${RASPI_PROJECT_DIR}/.git"; then
        ok "Git repo found at ${RASPI_PROJECT_DIR}"
        local pi_remote
        pi_remote=$(run_on_pi "cd ${RASPI_PROJECT_DIR} && git remote get-url origin 2>/dev/null || echo 'NONE'")
        info "Pi remote: ${pi_remote}"
    else
        warn "No git repo found at ${RASPI_PROJECT_DIR}"
        info "Cloning repo on Raspi..."
        run_on_pi "git clone git@github.com:ycs-mb/traffic-eye.git ${RASPI_PROJECT_DIR}" || {
            warn "Git clone via SSH failed. Trying HTTPS..."
            run_on_pi "git clone https://github.com/ycs-mb/traffic-eye.git ${RASPI_PROJECT_DIR}"
        }
        ok "Repo cloned on Raspi."
    fi

    # Step 5: Verify Python venv on Pi
    info "Checking Python virtual environment on Raspi..."
    if run_on_pi "test -f ${RASPI_PROJECT_DIR}/venv/bin/python"; then
        ok "Python venv exists."
    else
        warn "No venv found. Creating one..."
        run_on_pi "cd ${RASPI_PROJECT_DIR} && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip"
        ok "Python venv created."
    fi

    echo ""
    ok "=== Setup Complete ==="
    info "You can now use:"
    info "  ./scripts/deploy.sh git-deploy    # Push & pull via GitHub"
    info "  ./scripts/deploy.sh quick-sync    # rsync files directly"
    info "  ./scripts/deploy.sh ssh           # SSH into Pi"
}

cmd_git_deploy() {
    info "=== Git Deploy: Mac → GitHub → Raspi ==="
    check_ssh

    # Step 1: Check for uncommitted changes locally
    cd "${LOCAL_PROJECT_DIR}"
    if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet HEAD 2>/dev/null; then
        warn "You have uncommitted local changes!"
        echo ""
        git status --short
        echo ""
        read -p "Commit and push? (y/N): " -r reply
        if [[ "${reply}" =~ ^[Yy]$ ]]; then
            read -p "Commit message: " -r msg
            git add -A
            git commit -m "${msg:-'deploy update'}"
        else
            err "Aborting. Commit your changes first."
            return 1
        fi
    fi

    # Step 2: Push to GitHub
    info "Pushing to GitHub..."
    git push origin main
    ok "Pushed to GitHub."

    # Step 3: Pull on Raspi
    info "Pulling on Raspi..."
    run_on_pi "cd ${RASPI_PROJECT_DIR} && git fetch origin && git reset --hard origin/main"
    ok "Raspi updated to latest main."

    # Step 4: Check if deps changed
    local deps_changed
    deps_changed=$(run_on_pi "cd ${RASPI_PROJECT_DIR} && git diff HEAD~1 --name-only -- pyproject.toml requirements.txt 2>/dev/null || echo ''")
    if [[ -n "${deps_changed}" ]]; then
        warn "Dependencies changed. Installing..."
        cmd_install_deps
    fi

    ok "=== Git Deploy Complete ==="
}

cmd_quick_sync() {
    info "=== Quick Sync: rsync Mac → Raspi ==="
    check_ssh

    # rsync with sensible excludes (mirrors .gitignore + extras)
    rsync -avz --delete \
        --exclude='.git/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.venv/' \
        --exclude='venv/' \
        --exclude='.env' \
        --exclude='.env.local' \
        --exclude='data/evidence/*' \
        --exclude='data/queue/*' \
        --exclude='data/logs/*' \
        --exclude='data/captures/*' \
        --exclude='data/*.db' \
        --exclude='data/*.db-*' \
        --exclude='.DS_Store' \
        --exclude='.coverage' \
        --exclude='htmlcov/' \
        --exclude='.pytest_cache/' \
        --exclude='.claude/' \
        --exclude='.agent/' \
        --exclude='*.egg-info/' \
        --exclude='.idea/' \
        --exclude='.vscode/' \
        "${LOCAL_PROJECT_DIR}/" \
        "${RASPI_HOST}:${RASPI_PROJECT_DIR}/"

    ok "=== Quick Sync Complete ==="
    info "Files synced. Run './scripts/deploy.sh restart' to apply."
}

cmd_ssh() {
    info "Connecting to Raspi..."
    ssh "${RASPI_HOST}"
}

cmd_status() {
    info "=== Raspi Status ==="
    check_ssh

    echo ""
    info "── System ──"
    run_on_pi "hostname && uname -srm && uptime"
    echo ""

    info "── Temperature ──"
    run_on_pi "vcgencmd measure_temp 2>/dev/null || echo 'N/A (not a Pi?)'"
    echo ""

    info "── Services ──"
    run_on_pi "systemctl is-active traffic-eye-dashboard 2>/dev/null && echo 'Dashboard: RUNNING' || echo 'Dashboard: STOPPED'"
    run_on_pi "systemctl is-active traffic-eye-field 2>/dev/null && echo 'Field: RUNNING' || echo 'Field: STOPPED'"
    echo ""

    info "── Git Status ──"
    run_on_pi "cd ${RASPI_PROJECT_DIR} && git log --oneline -3 && echo '' && git status --short"
    echo ""

    info "── Disk ──"
    run_on_pi "df -h / | tail -1"
    echo ""

    info "── Memory ──"
    run_on_pi "free -h | head -2"
}

cmd_restart() {
    info "=== Restarting Services on Raspi ==="
    check_ssh

    run_on_pi "sudo systemctl restart traffic-eye-dashboard 2>/dev/null && echo 'Dashboard restarted' || echo 'Dashboard service not found'"
    run_on_pi "sudo systemctl restart traffic-eye-field 2>/dev/null && echo 'Field service restarted' || echo 'Field service not found'"

    ok "Services restarted."
}

cmd_logs() {
    info "=== Tailing Raspi Logs (Ctrl+C to stop) ==="
    check_ssh

    local service="${1:-traffic-eye-dashboard}"
    ssh "${RASPI_HOST}" "sudo journalctl -u ${service} -f --no-pager -n 50"
}

cmd_install_deps() {
    info "=== Installing Dependencies on Raspi ==="
    check_ssh

    run_on_pi "cd ${RASPI_PROJECT_DIR} && source venv/bin/activate && pip install -e '.[pi]' --quiet"
    ok "Dependencies installed."
}

# ── Main Entry Point ──────────────────────────────────────────────────────────

usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  setup         First-time setup (SSH key, verify git, venv)"
    echo "  git-deploy    Push to GitHub → Pull on Raspi (primary)"
    echo "  quick-sync    rsync files directly to Raspi (fast)"
    echo "  ssh           Open SSH session to Raspi"
    echo "  status        Check Raspi health & service status"
    echo "  restart       Restart traffic-eye services"
    echo "  logs [svc]    Tail Raspi service logs"
    echo "  install-deps  Install/update Python deps on Raspi"
    echo ""
}

case "${1:-}" in
    setup)        cmd_setup ;;
    git-deploy)   cmd_git_deploy ;;
    quick-sync)   cmd_quick_sync ;;
    ssh)          cmd_ssh ;;
    status)       cmd_status ;;
    restart)      cmd_restart ;;
    logs)         cmd_logs "${2:-}" ;;
    install-deps) cmd_install_deps ;;
    -h|--help|"") usage ;;
    *)
        err "Unknown command: $1"
        usage
        exit 1
        ;;
esac
