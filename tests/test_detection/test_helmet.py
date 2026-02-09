"""Tests for helmet classifier module."""

from __future__ import annotations

import numpy as np
import pytest


class TestMockHelmetClassifier:
    """Tests for MockHelmetClassifier."""

    def test_default_returns_no_helmet(self):
        from src.detection.helmet import MockHelmetClassifier

        clf = MockHelmetClassifier()
        clf.load_model()
        has_helmet, conf = clf.classify(np.zeros((64, 64, 3), dtype=np.uint8))
        assert has_helmet is False
        assert conf == pytest.approx(0.92)

    def test_set_result_overrides(self):
        from src.detection.helmet import MockHelmetClassifier

        clf = MockHelmetClassifier()
        clf.load_model()
        clf.set_result(True, 0.85)
        has_helmet, conf = clf.classify(np.zeros((64, 64, 3), dtype=np.uint8))
        assert has_helmet is True
        assert conf == pytest.approx(0.85)

    def test_is_loaded(self):
        from src.detection.helmet import MockHelmetClassifier

        clf = MockHelmetClassifier()
        assert clf.is_loaded() is False
        clf.load_model()
        assert clf.is_loaded() is True


class TestTFLiteHelmetClassifier:
    """Tests for TFLiteHelmetClassifier with real model."""

    MODEL_PATH = "models/helmet_cls_int8.tflite"

    @pytest.fixture
    def classifier(self):
        from src.detection.helmet import TFLiteHelmetClassifier

        clf = TFLiteHelmetClassifier(
            input_size=(96, 96), num_threads=4, confidence_threshold=0.5
        )
        clf.load_model(self.MODEL_PATH)
        return clf

    def test_model_loads(self, classifier):
        assert classifier.is_loaded() is True

    def test_classify_returns_tuple(self, classifier):
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        result = classifier.classify(img)
        assert isinstance(result, tuple)
        assert len(result) == 2
        has_helmet, confidence = result
        assert isinstance(has_helmet, bool)
        assert 0.0 <= confidence <= 1.0

    def test_classify_different_input_sizes(self, classifier):
        """Model should handle any input size (resize internally)."""
        for size in [(32, 32), (96, 96), (200, 150), (640, 480)]:
            img = np.random.randint(0, 255, (*size, 3), dtype=np.uint8)
            result = classifier.classify(img)
            assert isinstance(result, tuple)

    def test_helmet_image_detected(self, classifier):
        """Test that synthetic helmet images are classified correctly."""
        import cv2

        img = cv2.imread("data/helmet_test/helmet/helmet_0000.jpg")
        if img is None:
            pytest.skip("Test image not available")
        has_helmet, conf = classifier.classify(img)
        assert has_helmet is True, f"Expected helmet detection, got score implying no helmet"
        assert conf > 0.5

    def test_no_helmet_image_detected(self, classifier):
        """Test that synthetic no-helmet images are classified correctly."""
        import cv2

        img = cv2.imread("data/helmet_test/no_helmet/no_helmet_0000.jpg")
        if img is None:
            pytest.skip("Test image not available")
        has_helmet, conf = classifier.classify(img)
        assert has_helmet is False, f"Expected no helmet detection"
        assert conf > 0.5

    def test_not_loaded_returns_default(self):
        from src.detection.helmet import TFLiteHelmetClassifier

        clf = TFLiteHelmetClassifier()
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        has_helmet, conf = clf.classify(img)
        assert has_helmet is False
        assert conf == 0.0

    def test_missing_model_raises(self):
        from src.detection.helmet import TFLiteHelmetClassifier

        clf = TFLiteHelmetClassifier()
        with pytest.raises(FileNotFoundError):
            clf.load_model("/nonexistent/model.tflite")
