#!/usr/bin/env python3
"""
Test script to verify USB webcam detection and streaming.
Tests different video device indices to find the working webcam.
"""

import cv2
import sys
import time

def test_camera_device(device_id):
    """Test a specific camera device."""
    print(f"\n{'='*60}")
    print(f"Testing /dev/video{device_id}")
    print('='*60)

    cap = cv2.VideoCapture(device_id)

    if not cap.isOpened():
        print(f"❌ Could not open /dev/video{device_id}")
        return False

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)

    # Get actual properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    backend = cap.getBackendName()

    print("✅ Camera opened successfully")
    print(f"   Backend: {backend}")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")

    # Try to capture a few frames
    print("\nCapturing test frames...")
    success_count = 0
    fail_count = 0

    for i in range(10):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            success_count += 1
            if i == 0:
                print(f"   Frame shape: {frame.shape}")
                print(f"   Frame dtype: {frame.dtype}")
        else:
            fail_count += 1
        time.sleep(0.1)

    cap.release()

    print(f"\nResults: {success_count}/10 frames captured successfully")

    if success_count >= 8:
        print(f"✅ /dev/video{device_id} is WORKING")
        return True
    else:
        print(f"⚠️  /dev/video{device_id} has issues ({fail_count} failures)")
        return False

def main():
    print("\n" + "="*60)
    print("  USB Webcam Detection Test")
    print("="*60)

    # Test common device indices
    devices_to_test = [0, 1, 2]
    working_devices = []

    for device_id in devices_to_test:
        if test_camera_device(device_id):
            working_devices.append(device_id)

    print("\n" + "="*60)
    print("  Summary")
    print("="*60)

    if working_devices:
        print(f"\n✅ Working camera devices: {working_devices}")
        print(f"\n📝 Recommended device: /dev/video{working_devices[0]}")
        print("\nTo use this camera, the system will automatically fall back to")
        print("OpenCV VideoCapture since Picamera2 is not available.")
        return 0
    else:
        print("\n❌ No working camera devices found!")
        print("\nTroubleshooting:")
        print("  1. Check USB connection")
        print("  2. Run: v4l2-ctl --list-devices")
        print("  3. Check user permissions: groups (should include 'video')")
        print("  4. Try: sudo chmod 666 /dev/video*")
        return 1

if __name__ == "__main__":
    sys.exit(main())
