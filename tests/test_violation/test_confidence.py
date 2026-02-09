"""Tests for confidence aggregation."""

from src.violation.confidence import ConfidenceAggregator


class TestConfidenceAggregator:
    def test_compute_all_high(self):
        agg = ConfidenceAggregator()
        result = agg.compute(
            detection_conf=0.95,
            classification_conf=0.95,
            temporal_ratio=1.0,
            ocr_conf=0.95,
        )
        assert 0.94 < result <= 0.96

    def test_compute_without_ocr(self):
        agg = ConfidenceAggregator()
        result = agg.compute(
            detection_conf=0.9,
            classification_conf=0.9,
            temporal_ratio=1.0,
        )
        assert 0.85 < result < 0.95

    def test_compute_all_zero(self):
        agg = ConfidenceAggregator()
        result = agg.compute(0.0, 0.0, 0.0)
        assert result == 0.0

    def test_compute_clamped(self):
        agg = ConfidenceAggregator()
        result = agg.compute(1.0, 1.0, 2.0)  # temporal > 1
        assert result <= 1.0

    def test_meets_local_threshold(self):
        assert ConfidenceAggregator.meets_local_threshold(0.96) is True
        assert ConfidenceAggregator.meets_local_threshold(0.97) is True
        assert ConfidenceAggregator.meets_local_threshold(0.95) is False

    def test_needs_cloud_verification(self):
        assert ConfidenceAggregator.needs_cloud_verification(0.80) is True
        assert ConfidenceAggregator.needs_cloud_verification(0.70) is True
        assert ConfidenceAggregator.needs_cloud_verification(0.96) is False
        assert ConfidenceAggregator.needs_cloud_verification(0.69) is False

    def test_should_discard(self):
        assert ConfidenceAggregator.should_discard(0.50) is True
        assert ConfidenceAggregator.should_discard(0.69) is True
        assert ConfidenceAggregator.should_discard(0.70) is False
        assert ConfidenceAggregator.should_discard(0.96) is False

    def test_custom_weights(self):
        weights = {"detection": 0.5, "classification": 0.5, "temporal": 0.0, "ocr": 0.0}
        agg = ConfidenceAggregator(weights=weights)
        result = agg.compute(1.0, 0.0, 1.0)
        assert 0.49 < result < 0.51
