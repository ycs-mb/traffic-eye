#!/bin/bash
# Quick test to verify live video stream is working

echo "============================================================"
echo "  Testing Live Video Stream"
echo "============================================================"
echo ""

# 1. Check if service is running
echo "1. Checking dashboard service..."
if systemctl is-active --quiet traffic-eye-dashboard; then
    echo "✅ Service is running"
else
    echo "❌ Service is NOT running"
    echo "   Start with: sudo systemctl start traffic-eye-dashboard"
    exit 1
fi
echo ""

# 2. Check if port 8080 is listening
echo "2. Checking port 8080..."
if ss -tuln | grep -q ":8080 "; then
    echo "✅ Port 8080 is listening"
else
    echo "❌ Port 8080 is NOT listening"
    exit 1
fi
echo ""

# 3. Test API endpoint
echo "3. Testing API endpoint..."
response=$(curl -s http://localhost:8080/api/status)
if [ $? -eq 0 ]; then
    echo "✅ API responding:"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
else
    echo "❌ API not responding"
    exit 1
fi
echo ""

# 4. Test video feed (get first few bytes)
echo "4. Testing video feed..."
timeout 2 curl -s http://localhost:8080/video_feed | head -c 1000 > /tmp/video_test.dat
if [ -s /tmp/video_test.dat ]; then
    size=$(wc -c < /tmp/video_test.dat)
    echo "✅ Video feed streaming (received ${size} bytes)"
    # Check for JPEG signature
    if xxd -l 4 /tmp/video_test.dat | grep -q "ffd8"; then
        echo "✅ Valid JPEG data detected"
    fi
else
    echo "❌ No video data received"
    exit 1
fi
rm -f /tmp/video_test.dat
echo ""

# 5. Check which camera device is in use
echo "5. Checking camera device..."
device=$(sudo fuser /dev/video* 2>&1 | grep -oE "video[0-9]+" | head -1)
if [ -n "$device" ]; then
    echo "✅ Camera in use: /dev/$device"
else
    echo "⚠️  No camera device detected in use"
fi
echo ""

# 6. Summary
echo "============================================================"
echo "  Summary"
echo "============================================================"
echo ""
echo "Dashboard URL: http://100.107.114.5:8080"
echo ""
echo "✅ All checks passed! Live stream is working."
echo ""
echo "Access the dashboard from your browser to see the live feed."
echo ""
