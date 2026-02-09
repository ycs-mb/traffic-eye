"""License plate OCR using PaddleOCR with preprocessing pipeline.

This module provides a complete OCR pipeline for extracting text from license
plate images. The pipeline consists of:

1. Input validation: Check for valid image format and dimensions
2. Preprocessing: Grayscale conversion, adaptive thresholding, deskewing
3. OCR: PaddleOCR text extraction
4. Post-processing: Validation using validators.py

Design principles:
- Small, composable functions (each <30 lines)
- Fail gracefully (return None on error, don't crash)
- Log warnings for debugging
- Validate inputs at boundaries
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray

# Lazy import PaddleOCR to avoid initialization overhead
_PADDLE_OCR = None

logger = logging.getLogger(__name__)

# Constants
MIN_IMAGE_SIZE = 20  # Minimum width/height in pixels
MAX_IMAGE_SIZE = 4000  # Maximum width/height in pixels
DEFAULT_OCR_CONFIDENCE = 0.6  # Minimum confidence threshold


def _get_ocr_engine():
    """Lazy initialization of PaddleOCR engine.

    Returns:
        PaddleOCR instance configured for English text.
    """
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        try:
            from paddleocr import PaddleOCR
            # PaddleOCR 2.x API
            _PADDLE_OCR = PaddleOCR(
                use_angle_cls=True,  # Enable angle classification for rotation
                lang='en',           # English character recognition
                use_gpu=False,       # CPU-only for Raspberry Pi
                show_log=False,      # Suppress verbose logs
            )
            logger.info("PaddleOCR engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    return _PADDLE_OCR


def validate_image(image: NDArray[np.uint8]) -> bool:
    """Validate that the input is a valid image array.

    Args:
        image: Input image as numpy array.

    Returns:
        True if valid, False otherwise.
    """
    if image is None or not isinstance(image, np.ndarray):
        logger.warning("Invalid image: not a numpy array")
        return False

    if image.size == 0:
        logger.warning("Invalid image: empty array")
        return False

    if len(image.shape) not in [2, 3]:
        logger.warning(f"Invalid image: unexpected shape {image.shape}")
        return False

    h, w = image.shape[:2]
    if h < MIN_IMAGE_SIZE or w < MIN_IMAGE_SIZE:
        logger.warning(f"Invalid image: too small ({w}x{h})")
        return False

    if h > MAX_IMAGE_SIZE or w > MAX_IMAGE_SIZE:
        logger.warning(f"Invalid image: too large ({w}x{h})")
        return False

    return True


def convert_to_grayscale(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Convert image to grayscale for better OCR accuracy.

    Grayscale conversion reduces noise and improves contrast for text detection.
    If the image is already grayscale, it's returned unchanged.

    Args:
        image: BGR or grayscale image.

    Returns:
        Grayscale image.
    """
    if len(image.shape) == 2:
        # Already grayscale
        return image

    if image.shape[2] == 3:
        # Convert BGR to grayscale
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Unexpected format, take first channel
    logger.warning(f"Unexpected image shape {image.shape}, using first channel")
    return image[:, :, 0]


def apply_adaptive_threshold(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Apply adaptive thresholding to enhance text contrast.

    Adaptive thresholding is superior to global thresholding for license plates
    because it handles varying lighting conditions (shadows, glare, night).
    Uses Gaussian weighted sum for smoother results.

    Args:
        image: Grayscale image.

    Returns:
        Binary (black/white) image with enhanced text.
    """
    # Block size: neighborhood area for threshold calculation
    # Must be odd number; 11 works well for typical plate text size
    block_size = 11

    # C: constant subtracted from weighted mean
    # Lower values = more white pixels (aggressive thresholding)
    c_value = 2

    return cv2.adaptiveThreshold(
        image,
        255,  # Max value for white pixels
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c_value,
    )


def deskew_image(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Deskew image to correct rotation and improve OCR accuracy.

    Uses projection profile method to detect skew angle, then rotates to
    correct it. This handles plates that are slightly tilted in the frame.

    Args:
        image: Binary (thresholded) image.

    Returns:
        Deskewed image.
    """
    # Calculate skew angle using moments
    coords = cv2.findNonZero(cv2.bitwise_not(image))
    if coords is None or len(coords) < 5:
        # Not enough points to calculate angle
        return image

    angle = cv2.minAreaRect(coords)[-1]

    # Adjust angle to [-45, 45] range
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    # Skip rotation for very small angles (< 0.5 degrees)
    if abs(angle) < 0.5:
        return image

    # Rotate image to correct skew
    h, w = image.shape
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image,
        rotation_matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return rotated


def preprocess_plate_image(image: NDArray[np.uint8]) -> Optional[NDArray[np.uint8]]:
    """Run the complete preprocessing pipeline.

    Pipeline steps:
    1. Convert to grayscale (reduce noise)
    2. Apply adaptive threshold (enhance contrast)
    3. Deskew (correct rotation)

    Args:
        image: Input plate crop (BGR or grayscale).

    Returns:
        Preprocessed image ready for OCR, or None if preprocessing fails.
    """
    try:
        gray = convert_to_grayscale(image)
        threshold = apply_adaptive_threshold(gray)
        deskewed = deskew_image(threshold)
        return deskewed
    except Exception as e:
        logger.warning(f"Preprocessing failed: {e}")
        return None


def extract_plate_text(
    image: NDArray[np.uint8],
    confidence_threshold: float = DEFAULT_OCR_CONFIDENCE,
    preprocess: bool = True,
) -> Optional[str]:
    """Extract text from a license plate image using PaddleOCR.

    This is the main entry point for plate OCR. It handles the complete pipeline:
    1. Input validation
    2. Optional preprocessing (recommended)
    3. OCR text extraction
    4. Confidence filtering

    The function fails gracefully - it returns None rather than crashing on errors.
    Warnings are logged for debugging purposes.

    Args:
        image: Plate crop as numpy array (BGR or grayscale).
        confidence_threshold: Minimum OCR confidence (0.0-1.0). Default 0.6.
        preprocess: Whether to apply preprocessing pipeline. Default True.

    Returns:
        Extracted text string (raw, not validated), or None if OCR fails.

    Examples:
        >>> plate_crop = cv2.imread("plate.jpg")
        >>> text = extract_plate_text(plate_crop)
        >>> if text:
        ...     from src.ocr.validators import process_plate
        ...     corrected, is_valid, state = process_plate(text)
    """
    # Step 1: Validate input
    if not validate_image(image):
        return None

    # Step 2: Preprocess if requested
    processed_image = image
    if preprocess:
        processed = preprocess_plate_image(image)
        if processed is None:
            logger.warning("Preprocessing failed, trying OCR on original image")
        else:
            processed_image = processed

    # Step 3: Run OCR
    try:
        ocr_engine = _get_ocr_engine()
        result = ocr_engine.ocr(processed_image, cls=True)

        if not result or not result[0]:
            logger.debug("PaddleOCR returned no results")
            return None

        # Extract text with highest confidence
        best_text = None
        best_confidence = 0.0

        for line in result[0]:
            if line and len(line) >= 2:
                text, confidence = line[1]
                if confidence > best_confidence:
                    best_text = text
                    best_confidence = confidence

        # Step 4: Check confidence threshold
        if best_confidence < confidence_threshold:
            logger.debug(
                f"OCR confidence {best_confidence:.2f} below threshold "
                f"{confidence_threshold:.2f}"
            )
            return None

        logger.info(f"OCR result: '{best_text}' (confidence: {best_confidence:.2f})")
        return best_text

    except Exception as e:
        logger.error(f"OCR extraction failed: {e}", exc_info=True)
        return None


def extract_and_validate_plate(
    image: NDArray[np.uint8],
    confidence_threshold: float = DEFAULT_OCR_CONFIDENCE,
) -> tuple[Optional[str], bool, Optional[str]]:
    """Extract plate text and validate it as an Indian license plate.

    This is a convenience function that combines OCR extraction with validation.
    It calls extract_plate_text() followed by validators.process_plate().

    Args:
        image: Plate crop as numpy array.
        confidence_threshold: Minimum OCR confidence.

    Returns:
        (corrected_text, is_valid, state_code) tuple.
        Returns (None, False, None) if OCR fails.

    Examples:
        >>> plate_crop = cv2.imread("plate.jpg")
        >>> text, valid, state = extract_and_validate_plate(plate_crop)
        >>> if valid:
        ...     print(f"Detected {state} plate: {text}")
    """
    from src.ocr.validators import process_plate

    raw_text = extract_plate_text(image, confidence_threshold)
    if raw_text is None:
        return None, False, None

    return process_plate(raw_text)
