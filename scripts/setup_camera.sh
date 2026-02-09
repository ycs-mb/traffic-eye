#!/bin/bash
# Camera setup and testing script

echo "=== Camera Detection & Setup ==="

# Check if Pi Camera is connected
if vcgencmd get_camera | grep -q "detected=1"; then
    echo "✅ Pi Camera Module detected"
    CAMERA_TYPE="picamera"

    # Test camera with libcamera
    echo "Testing camera capture..."
    libcamera-hello --list-cameras

    echo ""
    echo "Taking test photo..."
    libcamera-jpeg -o /tmp/camera_test.jpg --width 640 --height 480 -t 1000

    if [ -f /tmp/camera_test.jpg ]; then
        echo "✅ Camera test successful: /tmp/camera_test.jpg"
        ls -lh /tmp/camera_test.jpg
    else
        echo "❌ Camera test failed"
        exit 1
    fi
else
    echo "⚠️  Pi Camera not detected, checking USB cameras..."
    CAMERA_TYPE="usb"

    # List USB video devices
    for dev in /dev/video*; do
        if [ -e "$dev" ]; then
            echo "Found: $dev"
            v4l2-ctl --device=$dev --all 2>/dev/null | head -20
        fi
    done
fi

echo ""
echo "Camera setup complete. Type: $CAMERA_TYPE"
echo ""
echo "To update config/settings.yaml:"
echo "  camera:"
echo "    source: 0  # or 'picamera' for Pi Camera"
echo "    fps: 15"
echo "    resolution: [1280, 720]"
