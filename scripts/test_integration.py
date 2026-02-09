#!/usr/bin/env python3
"""End-to-end integration test for traffic-eye."""

import sys
import os
sys.path.insert(0, '/home/yashcs/traffic-eye')

import cv2
import numpy as np
from src.config import load_config
from src.detection.tracker import IOUTracker
from src.capture.buffer import CircularFrameBuffer
from src.platform_factory import create_detector, create_helmet_classifier
from src.violation.rules import RuleEngine
from src.ocr.gemini_ocr import GeminiOCR

def test_detection_pipeline():
    """Test object detection."""
    print("Testing detection pipeline...")
    config = load_config('config')
    detector = create_detector(config)

    # Create test image
    img = np.ones((720, 1280, 3), dtype=np.uint8) * 128

    # Run detection
    detections = detector.detect(img, frame_id=0)
    print(f"✅ Detection works: {len(detections)} objects detected")
    return True

def test_helmet_classifier():
    """Test helmet classifier."""
    print("Testing helmet classifier...")
    config = load_config('config')
    classifier = create_helmet_classifier(config)

    # Create test image
    img = np.ones((100, 100, 3), dtype=np.uint8) * 128

    # Run classifier
    has_helmet, conf = classifier.classify(img)
    print(f"✅ Helmet classifier works: has_helmet={has_helmet}, conf={conf:.2f}")
    return True

def test_gemini_ocr():
    """Test Gemini Cloud OCR."""
    print("Testing Gemini Cloud OCR...")

    api_key = os.environ.get('TRAFFIC_EYE_CLOUD_API_KEY')
    if not api_key:
        print("⚠️  API key not set, skipping OCR test")
        return False

    ocr = GeminiOCR(api_key=api_key)

    # Create test plate image
    img = np.ones((100, 300, 3), dtype=np.uint8) * 255
    cv2.putText(img, 'MH12AB1234', (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)

    # Run OCR
    text, conf = ocr.extract_plate_text(img)
    print(f"✅ Gemini OCR works: text={text}, conf={conf:.2f}")
    return True

def test_violation_rules():
    """Test violation rule engine."""
    print("Testing violation rules...")

    rule_engine = RuleEngine(speed_gate_kmh=5.0, max_reports_per_hour=20)
    print(f"✅ Rule engine initialized")
    return True

def main():
    print("=" * 60)
    print("TRAFFIC-EYE END-TO-END INTEGRATION TEST")
    print("=" * 60)
    print()

    tests = [
        ("Detection Pipeline", test_detection_pipeline),
        ("Helmet Classifier", test_helmet_classifier),
        ("Gemini Cloud OCR", test_gemini_ocr),
        ("Violation Rules", test_violation_rules),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
            print()
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = False
            print()

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
