"""Tests for IoU tracker."""

from datetime import datetime, timezone

from src.detection.tracker import IOUTracker
from src.models import BoundingBox, Detection


def _make_detection(x1, y1, x2, y2, cls="car", conf=0.9, fid=0):
    return Detection(
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf, class_name=cls),
        frame_id=fid,
        timestamp=datetime.now(timezone.utc),
    )


class TestIOUTracker:
    def test_first_frame_assigns_ids(self):
        tracker = IOUTracker()
        dets = [_make_detection(0, 0, 50, 50), _make_detection(100, 100, 150, 150)]
        result = tracker.update(dets)
        assert result[0].track_id == 1
        assert result[1].track_id == 2

    def test_matching_across_frames(self):
        tracker = IOUTracker(iou_threshold=0.3)
        # Frame 1
        dets1 = [_make_detection(0, 0, 100, 100)]
        tracker.update(dets1)
        # Frame 2: slight movement
        dets2 = [_make_detection(10, 10, 110, 110, fid=1)]
        result = tracker.update(dets2)
        assert result[0].track_id == 1  # Same track

    def test_new_track_for_non_overlapping(self):
        tracker = IOUTracker(iou_threshold=0.3)
        dets1 = [_make_detection(0, 0, 50, 50)]
        tracker.update(dets1)
        # Frame 2: completely different location
        dets2 = [_make_detection(200, 200, 250, 250, fid=1)]
        result = tracker.update(dets2)
        assert result[0].track_id == 2  # New track

    def test_track_removal_after_missing(self):
        tracker = IOUTracker(iou_threshold=0.3, max_missing_frames=2)
        dets1 = [_make_detection(0, 0, 100, 100)]
        tracker.update(dets1)

        # 3 frames with no detections
        for i in range(3):
            tracker.update([])

        assert len(tracker.all_tracks) == 0

    def test_active_tracks(self):
        tracker = IOUTracker()
        dets = [_make_detection(0, 0, 100, 100)]
        tracker.update(dets)
        assert len(tracker.active_tracks) == 1

        tracker.update([])  # No detections
        assert len(tracker.active_tracks) == 0
        assert len(tracker.all_tracks) == 1  # Still tracked but missing

    def test_multiple_objects(self):
        tracker = IOUTracker()
        dets = [
            _make_detection(0, 0, 50, 50),
            _make_detection(100, 100, 150, 150),
            _make_detection(200, 200, 250, 250),
        ]
        result = tracker.update(dets)
        ids = {d.track_id for d in result}
        assert len(ids) == 3

    def test_reset(self):
        tracker = IOUTracker()
        tracker.update([_make_detection(0, 0, 50, 50)])
        assert len(tracker.all_tracks) == 1
        tracker.reset()
        assert len(tracker.all_tracks) == 0
