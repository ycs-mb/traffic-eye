#!/bin/bash
# GPS module setup and testing script

echo "=== GPS Setup ==="

# Install gpsd if not present
if ! command -v gpsd &> /dev/null; then
    echo "Installing gpsd..."
    sudo apt update
    sudo apt install -y gpsd gpsd-clients python3-gps
fi

# Detect USB GPS device
GPS_DEVICE=""
for dev in /dev/ttyUSB* /dev/ttyACM*; do
    if [ -e "$dev" ]; then
        echo "Found GPS device candidate: $dev"
        GPS_DEVICE=$dev
        break
    fi
done

if [ -z "$GPS_DEVICE" ]; then
    echo "❌ No GPS device found on /dev/ttyUSB* or /dev/ttyACM*"
    echo "   Connect USB GPS module and try again"
    exit 1
fi

echo "✅ Using GPS device: $GPS_DEVICE"

# Configure gpsd
echo "Configuring gpsd..."
sudo systemctl stop gpsd.socket
sudo systemctl stop gpsd

sudo tee /etc/default/gpsd > /dev/null <<EOF
# Default settings for gpsd
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$GPS_DEVICE"
USBAUTO="true"
GPSD_SOCKET="/var/run/gpsd.sock"
EOF

# Restart gpsd
sudo systemctl enable gpsd
sudo systemctl start gpsd
sudo systemctl start gpsd.socket

sleep 3

# Test GPS
echo ""
echo "Testing GPS (waiting 30 seconds for fix)..."
echo "Note: GPS needs clear sky view. May take 1-5 minutes for first fix."
echo ""

timeout 30 gpsmon

echo ""
echo "Quick GPS status:"
gpspipe -w -n 10 | head -20

echo ""
echo "✅ GPS setup complete"
echo ""
echo "To test GPS manually:"
echo "  cgps           # Terminal GPS monitor"
echo "  gpsmon         # Detailed GPS monitor"
echo "  gpspipe -w     # Raw NMEA/JSON data"
