#!/usr/bin/env bash
# =============================================================================
# setup_github_runner.sh — Install GitHub Actions Self-Hosted Runner on Pi
# =============================================================================
# Run this script ON THE RASPBERRY PI to set up the self-hosted GitHub runner.
# 
# Usage:
#   ./scripts/setup_github_runner.sh <RUNNER_TOKEN>
#
# Get your runner token from:
#   https://github.com/ycs-mb/traffic-eye/settings/actions/runners/new
# =============================================================================

set -euo pipefail

RUNNER_VERSION="2.321.0"  # Check GitHub for latest version
RUNNER_DIR="$HOME/actions-runner"
REPO_URL="https://github.com/ycs-mb/traffic-eye"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Check if token is provided
if [ $# -eq 0 ]; then
    err "Missing runner token!"
    echo ""
    echo "Usage: $0 <RUNNER_TOKEN>"
    echo ""
    echo "Get your token from:"
    echo "  https://github.com/ycs-mb/traffic-eye/settings/actions/runners/new"
    echo "  → Select 'Linux' and 'ARM64'"
    echo "  → Copy the token from the configuration command"
    echo ""
    exit 1
fi

RUNNER_TOKEN="$1"

info "=== GitHub Actions Runner Setup ==="
echo ""

# Step 1: Create directory
info "Creating runner directory at ${RUNNER_DIR}..."
mkdir -p "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

# Step 2: Download runner
info "Downloading GitHub Actions runner v${RUNNER_VERSION} (ARM64)..."
if [ ! -f "actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz" ]; then
    curl -o "actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz" -L \
        "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
else
    warn "Runner archive already exists, skipping download."
fi

# Step 3: Extract
info "Extracting runner..."
tar xzf "actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"

# Step 4: Configure
info "Configuring runner..."
./config.sh \
    --url "${REPO_URL}" \
    --token "${RUNNER_TOKEN}" \
    --name "raspi-$(hostname)" \
    --labels raspberry-pi \
    --work _work \
    --unattended \
    --replace

# Step 5: Install dependencies (if needed)
info "Installing runner dependencies..."
sudo ./bin/installdependencies.sh || warn "Dependency installation had warnings (may be safe to ignore)"

# Step 6: Install as systemd service
info "Installing as systemd service..."
sudo ./svc.sh install

# Step 7: Start service
info "Starting runner service..."
sudo ./svc.sh start

# Step 8: Verify
sleep 3
if sudo ./svc.sh status | grep -q "active (running)"; then
    echo ""
    info "✅ GitHub Actions runner installed and running!"
    echo ""
    info "Runner details:"
    echo "  Name:   raspi-$(hostname)"
    echo "  Labels: self-hosted, Linux, ARM64, raspberry-pi"
    echo "  Repo:   ${REPO_URL}"
    echo ""
    info "Verify in GitHub:"
    echo "  https://github.com/ycs-mb/traffic-eye/settings/actions/runners"
    echo ""
else
    err "Runner service failed to start. Check logs with:"
    echo "  sudo journalctl -u actions.runner.* -f"
    exit 1
fi
