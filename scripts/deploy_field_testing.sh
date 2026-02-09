#!/bin/bash
# Master deployment script for Traffic-Eye field testing

set -e  # Exit on error

echo "======================================================"
echo "   TRAFFIC-EYE FIELD TESTING DEPLOYMENT"
echo "======================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_DIR="/home/yashcs/traffic-eye"
cd "$PROJECT_DIR"

# Check if running as yashcs user
if [ "$(whoami)" != "yashcs" ]; then
    echo -e "${RED}Error: Must run as user 'yashcs'${NC}"
    exit 1
fi

echo -e "${GREEN}[1/10] Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y \
    python3-venv python3-pip \
    gpsd gpsd-clients python3-gps \
    v4l-utils \
    bc \
    sqlite3 \
    nginx

echo -e "${GREEN}[2/10] Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install flask psutil  # For web dashboard

echo -e "${GREEN}[3/10] Setting up GPS...${NC}"
bash scripts/setup_gps.sh || echo -e "${YELLOW}GPS setup incomplete (device may not be connected)${NC}"

echo -e "${GREEN}[4/10] Setting up camera...${NC}"
bash scripts/setup_camera.sh || echo -e "${YELLOW}Camera setup incomplete${NC}"

echo -e "${GREEN}[5/10] Installing Tailscale VPN...${NC}"
if ! command -v tailscale &> /dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
    echo -e "${YELLOW}Please run: sudo tailscale up${NC}"
    echo -e "${YELLOW}Then authenticate via the provided URL${NC}"
else
    echo "Tailscale already installed"
fi

echo -e "${GREEN}[6/10] Setting up systemd services...${NC}"
# Install service files
sudo cp systemd/traffic-eye-field.service /etc/systemd/system/
sudo cp systemd/traffic-eye-dashboard.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (auto-start on boot)
sudo systemctl enable traffic-eye-field.service
sudo systemctl enable traffic-eye-dashboard.service

echo -e "${GREEN}[7/10] Creating data directories...${NC}"
mkdir -p data/evidence
mkdir -p data/captures
mkdir -p logs

echo -e "${GREEN}[8/10] Setting up cron jobs for cleanup...${NC}"
# Add cleanup job (runs daily at 3 AM)
(crontab -l 2>/dev/null | grep -v "cleanup_old_evidence"; echo "0 3 * * * $PROJECT_DIR/scripts/cleanup_old_evidence.sh >> $PROJECT_DIR/logs/cleanup.log 2>&1") | crontab -

echo -e "${GREEN}[9/10] Configuring auto-login (optional)...${NC}"
# This allows Pi to boot directly without login (useful for field deployment)
read -p "Enable auto-login for user yashcs? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo raspi-config nonint do_boot_behaviour B2  # Console auto-login
    echo "Auto-login enabled"
fi

echo -e "${GREEN}[10/10] Final checks...${NC}"
bash scripts/check_power.sh

echo ""
echo "======================================================"
echo -e "${GREEN}✅ FIELD TESTING DEPLOYMENT COMPLETE${NC}"
echo "======================================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Setup Tailscale VPN:"
echo "   sudo tailscale up"
echo "   (Follow the authentication link)"
echo ""
echo "2. Get your Tailscale IP:"
echo "   tailscale ip -4"
echo ""
echo "3. Start services:"
echo "   sudo systemctl start traffic-eye-field"
echo "   sudo systemctl start traffic-eye-dashboard"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status traffic-eye-field"
echo "   journalctl -u traffic-eye-field -f"
echo ""
echo "5. Access dashboard from iPad:"
echo "   http://<tailscale-ip>:8080"
echo ""
echo "6. Test auto-start:"
echo "   sudo reboot"
echo "   (Services should start automatically)"
echo ""
echo "7. iPad Apps for monitoring:"
echo "   - Termius (SSH client)"
echo "   - Blink Shell (SSH)"
echo "   - Safari (Web dashboard)"
echo ""
echo "======================================================"
echo -e "${YELLOW}⚠️  IMPORTANT: Connect GPS and Camera before starting!${NC}"
echo "======================================================"
