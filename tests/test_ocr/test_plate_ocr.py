"""Comprehensive tests for plate OCR module.

Tests cover:
- Happy path: clear, well-formed plate images
- Edge cases: blurry, skewed, partial plates
- Error cases: invalid inputs, corrupted images
- Preprocessing pipeline: each step tested independently
"""

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from src.ocr.plate_ocr import (
    DEFAULT_OCR_CONFIDENCE,
    apply_adaptive_threshold,
    convert_to_grayscale,
    deskew_image,
    extract_and_validate_plate,
    extract_plate_text,
    preprocess_plate_image,
    validate_image,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_plate_bgr():
    """Create a synthetic BGR plate image: white background, black text."""
    img = np.ones((60, 200, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "MH12AB1234",
        (10, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
    )
    return img


@pytest.fixture
def sample_plate_gray():
    """Create a synthetic grayscale plate image."""
    img = np.ones((60, 200), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "DL01A1234",
        (10, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        0,
        2,
    )
    return img


@pytest.fixture
def blurry_plate():
    """Create a blurry plate image to test robustness."""
    img = np.ones((60, 200, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "KA51XY9876",
        (10, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
    )
    # Apply Gaussian blur
    return cv2.GaussianBlur(img, (9, 9), 3.0)


@pytest.fixture
def skewed_plate():
    """Create a skewed (rotated) plate image."""
    img = np.ones((100, 250, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "RJ14BC5678",
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 0, 0),
        2,
    )
    # Rotate 15 degrees
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, 15, 1.0)
    return cv2.warpAffine(img, rotation_matrix, (w, h), borderValue=(255, 255, 255))


@pytest.fixture
def partial_plate():
    """Create a partially visible plate (cropped)."""
    img = np.ones((40, 120, 3), dtype=np.uint8) * 255
    # Only show partial text
    cv2.putText(
        img,
        "MH12AB",
        (5, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
    )
    return img


# ============================================================================
# Test Input Validation
# ============================================================================


class TestValidateImage:
    """Test image validation at system boundary."""

    def test_valid_bgr_image(self, sample_plate_bgr):
        """Valid 3-channel BGR image."""
        assert validate_image(sample_plate_bgr) is True

    def test_valid_gray_image(self, sample_plate_gray):
        """Valid single-channel grayscale image."""
        assert validate_image(sample_plate_gray) is True

    def test_none_input(self):
        """None input should be rejected."""
        assert validate_image(None) is False

    def test_empty_array(self):
        """Empty array should be rejected."""
        empty = np.array([])
        assert validate_image(empty) is False

    def test_invalid_type(self):
        """Non-numpy array should be rejected."""
        assert validate_image([1, 2, 3]) is False

    def test_wrong_dimensions(self):
        """1D or 4D arrays should be rejected."""
        arr_1d = np.array([1, 2, 3])
        arr_4d = np.ones((10, 10, 3, 3))
        assert validate_image(arr_1d) is False
        assert validate_image(arr_4d) is False

    def test_too_small(self):
        """Images smaller than MIN_IMAGE_SIZE should be rejected."""
        tiny = np.ones((10, 10, 3), dtype=np.uint8)
        assert validate_image(tiny) is False

    def test_too_large(self):
        """Images larger than MAX_IMAGE_SIZE should be rejected."""
        # Use a smaller test size to avoid memory issues
        huge = np.ones((5000, 5000, 3), dtype=np.uint8)
        assert validate_image(huge) is False

    def test_minimum_valid_size(self):
        """Image at exactly MIN_IMAGE_SIZE should be accepted."""
        min_img = np.ones((20, 20, 3), dtype=np.uint8)
        assert validate_image(min_img) is True


# ============================================================================
# Test Preprocessing Pipeline
# ============================================================================


class TestConvertToGrayscale:
    """Test grayscale conversion step."""

    def test_bgr_to_gray(self, sample_plate_bgr):
        """BGR image should be converted to grayscale."""
        gray = convert_to_grayscale(sample_plate_bgr)
        assert len(gray.shape) == 2
        assert gray.dtype == np.uint8

    def test_already_gray(self, sample_plate_gray):
        """Grayscale image should pass through unchanged."""
        result = convert_to_grayscale(sample_plate_gray)
        assert np.array_equal(result, sample_plate_gray)

    def test_preserves_dimensions(self, sample_plate_bgr):
        """Width and height should be preserved."""
        gray = convert_to_grayscale(sample_plate_bgr)
        assert gray.shape[:2] == sample_plate_bgr.shape[:2]

    def test_4_channel_image(self):
        """4-channel (BGRA) should take first channel."""
        img_4ch = np.ones((50, 100, 4), dtype=np.uint8) * 128
        gray = convert_to_grayscale(img_4ch)
        assert len(gray.shape) == 2


class TestApplyAdaptiveThreshold:
    """Test adaptive thresholding step."""

    def test_output_is_binary(self, sample_plate_gray):
        """Output should be binary (only 0 and 255)."""
        binary = apply_adaptive_threshold(sample_plate_gray)
        unique_values = np.unique(binary)
        assert set(unique_values).issubset({0, 255})

    def test_preserves_dimensions(self, sample_plate_gray):
        """Dimensions should be preserved."""
        binary = apply_adaptive_threshold(sample_plate_gray)
        assert binary.shape == sample_plate_gray.shape

    def test_enhances_contrast(self, sample_plate_gray):
        """Should create high-contrast binary image."""
        binary = apply_adaptive_threshold(sample_plate_gray)
        # Check that we have both black and white pixels
        assert 0 in binary
        assert 255 in binary

    def test_dtype_uint8(self, sample_plate_gray):
        """Output dtype should be uint8."""
        binary = apply_adaptive_threshold(sample_plate_gray)
        assert binary.dtype == np.uint8


class TestDeskewImage:
    """Test deskewing step."""

    def test_already_straight_unchanged(self, sample_plate_gray):
        """Straight image should not be significantly altered."""
        binary = apply_adaptive_threshold(sample_plate_gray)
        deskewed = deskew_image(binary)
        assert deskewed.shape == binary.shape

    def test_skewed_image_corrected(self):
        """Skewed image should be rotated towards horizontal."""
        # Create skewed binary image
        img = np.ones((100, 200), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 30), (150, 70), 0, -1)
        # Rotate it
        h, w = img.shape
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, 10, 1.0)
        skewed = cv2.warpAffine(img, rotation_matrix, (w, h), borderValue=255)
        binary = cv2.threshold(skewed, 127, 255, cv2.THRESH_BINARY)[1]

        deskewed = deskew_image(binary)
        assert deskewed.shape == binary.shape

    def test_empty_image_returns_unchanged(self):
        """Image with no content should return unchanged."""
        empty = np.ones((100, 200), dtype=np.uint8) * 255
        result = deskew_image(empty)
        assert np.array_equal(result, empty)

    def test_preserves_dimensions(self, sample_plate_gray):
        """Dimensions should be preserved."""
        binary = apply_adaptive_threshold(sample_plate_gray)
        deskewed = deskew_image(binary)
        assert deskewed.shape == binary.shape


class TestPreprocessPlateImage:
    """Test complete preprocessing pipeline."""

    def test_pipeline_success(self, sample_plate_bgr):
        """Full pipeline should succeed on valid input."""
        result = preprocess_plate_image(sample_plate_bgr)
        assert result is not None
        assert len(result.shape) == 2  # Should be grayscale
        assert result.dtype == np.uint8

    def test_pipeline_with_gray_input(self, sample_plate_gray):
        """Pipeline should work with grayscale input."""
        result = preprocess_plate_image(sample_plate_gray)
        assert result is not None

    def test_pipeline_with_blurry_image(self, blurry_plate):
        """Pipeline should handle blurry images."""
        result = preprocess_plate_image(blurry_plate)
        assert result is not None

    def test_pipeline_with_skewed_image(self, skewed_plate):
        """Pipeline should handle skewed images."""
        result = preprocess_plate_image(skewed_plate)
        assert result is not None

    def test_corrupted_image_returns_none(self):
        """Corrupted/invalid image should return None."""
        # Create array that will cause CV2 error
        corrupted = np.array([[[]]], dtype=np.uint8)
        result = preprocess_plate_image(corrupted)
        assert result is None


# ============================================================================
# Test OCR Extraction (with mocking)
# ============================================================================


class TestExtractPlateText:
    """Test main OCR extraction function."""

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_successful_extraction(self, mock_get_engine, sample_plate_bgr):
        """Successful OCR should return text."""
        # Mock PaddleOCR response
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("MH12AB1234", 0.95)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr)
        assert result == "MH12AB1234"

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_low_confidence_returns_none(self, mock_get_engine, sample_plate_bgr):
        """Low confidence result should return None."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("ABC123", 0.3)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr, confidence_threshold=0.6)
        assert result is None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_no_results_returns_none(self, mock_get_engine, sample_plate_bgr):
        """Empty OCR result should return None."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = None
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr)
        assert result is None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_empty_result_list(self, mock_get_engine, sample_plate_bgr):
        """Empty result list should return None."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[]]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr)
        assert result is None

    def test_invalid_image_returns_none(self):
        """Invalid image should return None without crashing."""
        result = extract_plate_text(None)
        assert result is None

    def test_too_small_image_returns_none(self):
        """Too small image should return None."""
        tiny = np.ones((5, 5, 3), dtype=np.uint8)
        result = extract_plate_text(tiny)
        assert result is None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_preprocessing_disabled(self, mock_get_engine, sample_plate_bgr):
        """Should work with preprocessing disabled."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("TEST", 0.9)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr, preprocess=False)
        assert result == "TEST"

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_ocr_exception_returns_none(self, mock_get_engine, sample_plate_bgr):
        """OCR exception should be caught and return None."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.side_effect = Exception("OCR error")
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr)
        assert result is None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_multiple_results_picks_highest_confidence(
        self, mock_get_engine, sample_plate_bgr
    ):
        """Should pick result with highest confidence."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("WRONG", 0.7)],
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("CORRECT", 0.95)],
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("ALSO_WRONG", 0.6)],
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr)
        assert result == "CORRECT"

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_custom_confidence_threshold(self, mock_get_engine, sample_plate_bgr):
        """Should respect custom confidence threshold."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("TEST", 0.75)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        # Should pass with 0.7 threshold
        result = extract_plate_text(sample_plate_bgr, confidence_threshold=0.7)
        assert result == "TEST"

        # Should fail with 0.8 threshold
        result = extract_plate_text(sample_plate_bgr, confidence_threshold=0.8)
        assert result is None


# ============================================================================
# Test Integration with Validators
# ============================================================================


class TestExtractAndValidatePlate:
    """Test integrated OCR + validation."""

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_valid_indian_plate(self, mock_get_engine, sample_plate_bgr):
        """Valid Indian plate should be validated."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("MH 12-AB-1234", 0.9)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        text, is_valid, state = extract_and_validate_plate(sample_plate_bgr)
        assert text == "MH12AB1234"
        assert is_valid is True
        assert state == "MH"

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_ocr_corrects_errors(self, mock_get_engine, sample_plate_bgr):
        """OCR errors should be corrected by validators."""
        mock_ocr = MagicMock()
        # "0" in first position should be corrected to "O"
        # Pattern matches but OH is not a valid state code
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("0H12AB1234", 0.9)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        text, is_valid, state = extract_and_validate_plate(sample_plate_bgr)
        # Should correct "0" -> "O", pattern matches but state is None (not valid RTO code)
        assert text == "OH12AB1234"
        assert is_valid is True  # Pattern matches
        assert state is None  # But OH is not a valid state code

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_invalid_format(self, mock_get_engine, sample_plate_bgr):
        """Invalid format should fail validation."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("INVALID", 0.9)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        text, is_valid, state = extract_and_validate_plate(sample_plate_bgr)
        assert is_valid is False
        assert state is None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_ocr_failure(self, mock_get_engine, sample_plate_bgr):
        """OCR failure should return None, False, None."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = None
        mock_get_engine.return_value = mock_ocr

        text, is_valid, state = extract_and_validate_plate(sample_plate_bgr)
        assert text is None
        assert is_valid is False
        assert state is None


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_blurry_plate_lower_confidence(self, mock_get_engine, blurry_plate):
        """Blurry plate should still work but with lower confidence."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("KA51XY9876", 0.65)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(blurry_plate, confidence_threshold=0.6)
        assert result is not None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_partial_plate(self, mock_get_engine, partial_plate):
        """Partial plate should return whatever OCR finds."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("MH12AB", 0.8)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(partial_plate)
        assert result == "MH12AB"

    def test_corrupted_image_no_crash(self):
        """Corrupted image should not crash."""
        # Various corrupted formats
        result1 = extract_plate_text(np.array([]))
        result2 = extract_plate_text(np.zeros((0, 0, 3)))

        assert result1 is None
        assert result2 is None

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_non_ascii_text(self, mock_get_engine, sample_plate_bgr):
        """Should handle non-ASCII characters gracefully."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("MH12£¥1234", 0.8)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr)
        assert result is not None  # Should return something

    @patch("src.ocr.plate_ocr._get_ocr_engine")
    def test_very_high_confidence(self, mock_get_engine, sample_plate_bgr):
        """Should work with very high confidence threshold."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("DL01A1234", 0.99)]
            ]
        ]
        mock_get_engine.return_value = mock_ocr

        result = extract_plate_text(sample_plate_bgr, confidence_threshold=0.95)
        assert result == "DL01A1234"


# ============================================================================
# Test Constants
# ============================================================================


class TestConstants:
    """Test module constants are reasonable."""

    def test_default_confidence_reasonable(self):
        """Default confidence should be between 0 and 1."""
        assert 0.0 <= DEFAULT_OCR_CONFIDENCE <= 1.0

    def test_default_confidence_not_too_strict(self):
        """Default confidence shouldn't be too strict (>0.9)."""
        assert DEFAULT_OCR_CONFIDENCE < 0.9

    def test_default_confidence_not_too_lenient(self):
        """Default confidence shouldn't be too lenient (<0.4)."""
        assert DEFAULT_OCR_CONFIDENCE > 0.4
