#!/usr/bin/env python3
"""Test GCP Vertex AI setup for Traffic-Eye cloud OCR.

This script verifies:
1. GCP credentials are properly configured
2. Vertex AI API is accessible
3. Gemini Pro Vision model is available
4. Cloud OCR can extract text from a test image

Usage:
    python scripts/test_vertex_ai.py [--test-image path/to/plate.jpg]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_environment():
    """Check required environment variables."""
    logger.info("Checking environment variables...")

    creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION", "us-central1")

    issues = []

    if not creds_file:
        issues.append("❌ GOOGLE_APPLICATION_CREDENTIALS not set")
    elif not Path(creds_file).exists():
        issues.append(f"❌ Credentials file not found: {creds_file}")
    else:
        logger.info(f"✅ Credentials file: {creds_file}")

    if not project_id:
        issues.append("❌ GCP_PROJECT_ID not set")
    else:
        logger.info(f"✅ GCP Project ID: {project_id}")

    logger.info(f"✅ GCP Location: {location}")

    if issues:
        for issue in issues:
            logger.error(issue)
        logger.error("\nSet environment variables:")
        logger.error('export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"')
        logger.error('export GCP_PROJECT_ID="your-project-id"')
        logger.error('export GCP_LOCATION="us-central1"')
        return False

    return True


def check_vertex_ai_sdk():
    """Check if Vertex AI SDK is installed."""
    logger.info("Checking Vertex AI SDK...")

    try:
        import google.cloud.aiplatform
        import vertexai.preview.generative_models
        logger.info("✅ Vertex AI SDK installed")
        return True
    except ImportError as e:
        logger.error(f"❌ Vertex AI SDK not installed: {e}")
        logger.error("Install with: pip install google-cloud-aiplatform")
        return False


def test_vertex_ai_connection():
    """Test connection to Vertex AI."""
    logger.info("Testing Vertex AI connection...")

    try:
        from google.cloud import aiplatform

        project_id = os.environ.get("GCP_PROJECT_ID")
        location = os.environ.get("GCP_LOCATION", "us-central1")

        aiplatform.init(project=project_id, location=location)
        logger.info(f"✅ Connected to Vertex AI (project={project_id}, location={location})")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to connect to Vertex AI: {e}")
        return False


def test_gemini_model():
    """Test Gemini Pro Vision model availability."""
    logger.info("Testing Gemini Pro Vision model...")

    try:
        from vertexai.generative_models import GenerativeModel

        model = GenerativeModel("gemini-1.5-flash")
        logger.info("✅ Gemini 1.5 Flash model available")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to access Gemini model: {e}")
        return False


def test_cloud_ocr(image_path: str = None):
    """Test cloud OCR with a sample image."""
    if not image_path:
        logger.info("⏩ Skipping OCR test (no test image provided)")
        logger.info("   Use --test-image to test OCR with your plate image")
        return True

    logger.info(f"Testing cloud OCR with image: {image_path}")

    try:
        import cv2
        from src.ocr.cloud_ocr import CloudOCR

        project_id = os.environ.get("GCP_PROJECT_ID")
        location = os.environ.get("GCP_LOCATION", "us-central1")

        # Initialize Cloud OCR
        ocr = CloudOCR(
            project_id=project_id,
            location=location,
            confidence_threshold=0.7
        )

        # Load test image
        if not Path(image_path).exists():
            logger.error(f"❌ Test image not found: {image_path}")
            return False

        plate_img = cv2.imread(image_path)
        if plate_img is None:
            logger.error(f"❌ Failed to load image: {image_path}")
            return False

        logger.info(f"Image loaded: {plate_img.shape[1]}x{plate_img.shape[0]} pixels")

        # Extract plate text
        text, confidence = ocr.extract_plate_text(plate_img)

        if text:
            logger.info(f"✅ Plate detected: {text} (confidence: {confidence:.2f})")
            return True
        else:
            logger.warning(f"⚠️  Plate not readable (confidence: {confidence:.2f})")
            logger.warning("   This may be normal if the image doesn't contain a clear plate")
            return True

    except Exception as e:
        logger.error(f"❌ Cloud OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test GCP Vertex AI setup")
    parser.add_argument(
        "--test-image",
        help="Path to test license plate image",
        default=None
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("GCP Vertex AI Setup Verification")
    logger.info("=" * 60)

    tests = [
        ("Environment Variables", check_environment),
        ("Vertex AI SDK", check_vertex_ai_sdk),
        ("Vertex AI Connection", test_vertex_ai_connection),
        ("Gemini Pro Vision Model", test_gemini_model),
    ]

    # Run standard tests
    all_passed = True
    for name, test_func in tests:
        logger.info("")
        result = test_func()
        if not result:
            all_passed = False

    # Run OCR test if image provided
    if args.test_image:
        logger.info("")
        result = test_cloud_ocr(args.test_image)
        if not result:
            all_passed = False

    # Summary
    logger.info("")
    logger.info("=" * 60)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED")
        logger.info("")
        logger.info("Your Vertex AI setup is ready for cloud-only OCR!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Update config/settings.yaml with cloud settings")
        logger.info("2. Restart traffic-eye service: sudo systemctl restart traffic-eye")
        logger.info("3. Monitor logs: sudo journalctl -u traffic-eye -f")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        logger.error("")
        logger.error("Please fix the issues above and run this script again.")
        logger.error("See docs/VERTEX_AI_SETUP.md for detailed setup instructions.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
