#!/usr/bin/env python3
"""
Test script for the live dashboard with simulated camera feed.
Simulates detection frames being sent to the dashboard.
"""

import sys
sys.path.insert(0, '/home/yashcs/traffic-eye')

import cv2
import time
import numpy as np
from pathlib import Path
from src.web.frame_publisher import FramePublisher

def create_demo_frame(width=640, height=480, frame_num=0):
    """Create a demo frame with moving objects."""
    frame = np.random.randint(50, 100, (height, width, 3), dtype=np.uint8)

    # Add title
    cv2.putText(frame, "Traffic-Eye Demo Feed", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # Add moving objects
    offset = (frame_num * 5) % width

    # Person
    x1, y1 = offset, height // 4
    x2, y2 = offset + 100, height // 2
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Motorcycle
    x3, y3 = (offset + 200) % width, height // 3
    x4, y4 = (offset + 350) % width, 2 * height // 3
    cv2.rectangle(frame, (x3, y3), (x4, y4), (255, 165, 0), 2)

    return frame, [
        {
            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
            'class_name': 'person',
            'confidence': 0.85 + (frame_num % 10) * 0.01
        },
        {
            'x1': x3, 'y1': y3, 'x2': x4, 'y2': y4,
            'class_name': 'motorcycle',
            'confidence': 0.90 + (frame_num % 10) * 0.01
        }
    ]

def load_real_frames():
    """Load real frames from captures if available."""
    captures_dir = Path('/home/yashcs/traffic-eye/data/captures')
    if captures_dir.exists():
        captures = sorted(captures_dir.glob('*.jpg'))
        if captures:
            frames = []
            for cap_path in captures[:20]:  # Load up to 20 frames
                frame = cv2.imread(str(cap_path))
                if frame is not None:
                    frames.append(frame)
            return frames
    return None

def main():
    print("=== Traffic-Eye Live Dashboard Test ===")
    print()
    print("Starting frame publisher...")

    publisher = FramePublisher(dashboard_url="http://localhost:8080")

    if not publisher.enabled:
        print("❌ Dashboard not available!")
        print("   Start the dashboard first:")
        print("   python src/web/dashboard_live.py")
        return

    print("✅ Connected to dashboard")
    print()
    print("Sending demo frames...")
    print("Press Ctrl+C to stop")
    print()

    # Try to load real frames
    real_frames = load_real_frames()

    frame_num = 0
    try:
        while True:
            if real_frames:
                # Use real frames
                frame = real_frames[frame_num % len(real_frames)]
                # Add mock detections
                h, w = frame.shape[:2]
                detections = [
                    {
                        'x1': w//4, 'y1': h//4, 'x2': w//2, 'y2': h//2,
                        'class_name': 'person',
                        'confidence': 0.85 + (frame_num % 10) * 0.01
                    },
                    {
                        'x1': w//2, 'y1': h//3, 'x2': 3*w//4, 'y2': 2*h//3,
                        'class_name': 'motorcycle',
                        'confidence': 0.92 + (frame_num % 10) * 0.005
                    }
                ]
            else:
                # Generate demo frames
                frame, detections = create_demo_frame(frame_num=frame_num)

            # Publish frame
            publisher.publish_frame(frame, detections)

            frame_num += 1
            print(f"\rFrame {frame_num} published (detections: {len(detections)})", end='')

            # ~15 FPS
            time.sleep(0.066)

    except KeyboardInterrupt:
        print("\n\n✅ Stopped")
        print(f"Total frames sent: {frame_num}")

if __name__ == "__main__":
    main()
