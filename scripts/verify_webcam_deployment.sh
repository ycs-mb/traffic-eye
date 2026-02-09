#!/bin/bash
# Comprehensive verification script for USB webcam deployment

set -e

echo "============================================================"
echo "  Traffic-Eye USB Webcam Deployment Verification"
echo "============================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check video devices
echo "1. Checking video devices..."
if ls /dev/video* > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Video devices found:${NC}"
    ls -la /dev/video* | head -5
    echo "   (showing first 5 devices)"
else
    echo -e "${RED}❌ No video devices found!${NC}"
    exit 1
fi
echo ""

# 2. Check user in video group
echo "2. Checking user permissions..."
if groups | grep -q video; then
    echo -e "${GREEN}✅ User is in 'video' group${NC}"
else
    echo -e "${YELLOW}⚠️  User NOT in 'video' group${NC}"
    echo "   Run: sudo usermod -a -G video $USER"
    echo "   Then logout and login again"
fi
echo ""

# 3. List USB devices
echo "3. USB webcam detection..."
if command -v v4l2-ctl &> /dev/null; then
    v4l2-ctl --list-devices 2>&1 | grep -A 2 "usb" || echo "No USB camera found via v4l2-ctl"
else
    echo -e "${YELLOW}⚠️  v4l2-ctl not installed${NC}"
    echo "   Install with: sudo apt install v4l-utils"
fi
echo ""

# 4. Test camera with Python script
echo "4. Testing webcam with Python..."
cd /home/yashcs/traffic-eye
source venv/bin/activate

python3 scripts/test_webcam.py
echo ""

# 5. Check if dashboard service exists
echo "5. Checking systemd service..."
if systemctl list-unit-files | grep -q traffic-eye-dashboard; then
    echo -e "${GREEN}✅ traffic-eye-dashboard service exists${NC}"
    systemctl status traffic-eye-dashboard --no-pager || true
else
    echo -e "${YELLOW}⚠️  Service not installed${NC}"
fi
echo ""

# 6. Check OpenCV installation
echo "6. Verifying OpenCV installation..."
python3 -c "import cv2; print(f'✅ OpenCV version: {cv2.__version__}')" || {
    echo -e "${RED}❌ OpenCV not installed!${NC}"
    echo "   Install with: pip install opencv-python"
    exit 1
}
echo ""

# 7. Summary
echo "============================================================"
echo "  Deployment Summary"
echo "============================================================"
echo ""
echo "Camera Type: USB Webcam (SNAP U2)"
echo "Device: /dev/video1"
echo "Backend: OpenCV VideoCapture"
echo "Resolution: 640x480"
echo "FPS: 15-30"
echo ""
echo "Dashboard: http://100.107.114.5:8080"
echo ""
echo -e "${GREEN}✅ USB webcam deployment verification complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Test dashboard manually: python src/web/dashboard_camera.py"
echo "  2. If working, restart service: sudo systemctl restart traffic-eye-dashboard"
echo "  3. Check logs: sudo journalctl -u traffic-eye-dashboard -f"
echo ""
