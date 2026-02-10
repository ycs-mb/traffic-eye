#!/usr/bin/env python3
"""Check actual camera resolution being captured."""

import cv2


def check_resolution(device_id=1):
    print(f"Opening /dev/video{device_id}...")
    cap = cv2.VideoCapture(device_id)

    if not cap.isOpened():
        print(f"❌ Could not open /dev/video{device_id}")
        return False

    # Set desired resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

    # Get actual resolution
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)

    print("\n✅ Camera Configuration:")
    print(f"   Resolution: {actual_width}x{actual_height}")
    print(f"   FPS: {actual_fps}")

    # Capture a frame to verify
    print("\nCapturing test frame...")
    ret, frame = cap.read()

    if ret and frame is not None:
        print("✅ Frame captured successfully")
        print(f"   Frame shape: {frame.shape}")
        print(f"   Dimensions: {frame.shape[1]}x{frame.shape[0]}")

        if frame.shape[1] == 1280 and frame.shape[0] == 720:
            print("\n🎉 SUCCESS: Camera is capturing at full 720p resolution!")
        else:
            print(f"\n⚠️  WARNING: Expected 1280x720, got {frame.shape[1]}x{frame.shape[0]}")
    else:
        print("❌ Failed to capture frame")

    cap.release()
    return True

if __name__ == "__main__":
    check_resolution()
