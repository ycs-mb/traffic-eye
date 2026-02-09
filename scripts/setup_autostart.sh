#!/bin/bash
# Setup auto-start services for Traffic-Eye

set -e

echo "============================================================"
echo "  Traffic-Eye Auto-Start Setup"
echo "============================================================"
echo ""

cd /home/yashcs/traffic-eye

# Check if running as yashcs user
if [ "$(whoami)" != "yashcs" ]; then
    echo "❌ Error: Must run as user 'yashcs'"
    exit 1
fi

echo "📋 Checking current service status..."
echo ""

# Check if services are already installed
if systemctl list-unit-files | grep -q traffic-eye-dashboard; then
    echo "✅ Services already installed"
else
    echo "⚠️  Services not installed yet"
fi

echo ""
echo "📦 Installing systemd services..."

# Copy service files to systemd
sudo cp systemd/traffic-eye-dashboard.service /etc/systemd/system/
# Optionally install main service (commented out for dashboard-only mode)
# sudo cp systemd/traffic-eye-field.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

echo "✅ Service files installed"
echo ""
echo "🔄 Enabling auto-start on boot..."

# Enable dashboard to start on boot
sudo systemctl enable traffic-eye-dashboard.service

# Optionally enable main service
# sudo systemctl enable traffic-eye-field.service

echo "✅ Auto-start enabled"
echo ""
echo "📊 Current status:"
echo ""

# Show service status
systemctl status traffic-eye-dashboard --no-pager | head -10

echo ""
echo "============================================================"
echo "  ✅ Auto-Start Configuration Complete"
echo "============================================================"
echo ""
echo "Services configured to start on boot:"
echo "  • traffic-eye-dashboard (Live Camera Dashboard)"
echo ""
echo "To start services now without rebooting:"
echo "  sudo systemctl start traffic-eye-dashboard"
echo ""
echo "To check status:"
echo "  sudo systemctl status traffic-eye-dashboard"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u traffic-eye-dashboard -f"
echo ""
echo "To test auto-start:"
echo "  sudo reboot"
echo ""
echo "After reboot, dashboard will be available at:"
echo "  http://100.107.114.5:8080"
echo ""
echo "============================================================"
