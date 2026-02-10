"""Simple IoU-based multi-object tracker."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.models import BoundingBox, Detection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """A tracked object across frames."""
    track_id: int
    bbox: BoundingBox
    class_name: str
    age: int = 0
    missing_frames: int = 0
    total_visible: int = 1


class IOUTracker:
    """Greedy IoU-based multi-object tracker.

    Assigns consistent track IDs to detections across frames
    by matching bounding boxes using Intersection over Union.
    """

    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_missing_frames: int = 5,
    ):
        self._iou_threshold = iou_threshold
        self._max_missing_frames = max_missing_frames
        self._tracks: list[Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection]) -> list[Detection]:
        """Match detections to existing tracks and assign track IDs.

        Args:
            detections: Detections from current frame.

        Returns:
            Same detections with track_id assigned.
        """
        if not self._tracks:
            # First frame: create tracks for all detections
            for det in detections:
                det.track_id = self._next_id
                self._tracks.append(Track(
                    track_id=self._next_id,
                    bbox=det.bbox,
                    class_name=det.bbox.class_name,
                ))
                self._next_id += 1
            return detections

        # Compute IoU matrix
        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        assignments: list[tuple[int, int, float]] = []

        for di, det in enumerate(detections):
            for ti, track in enumerate(self._tracks):
                iou = det.bbox.iou(track.bbox)
                if iou >= self._iou_threshold:
                    assignments.append((ti, di, iou))

        # Greedy assignment: sort by IoU descending, assign best matches first
        assignments.sort(key=lambda x: x[2], reverse=True)

        for ti, di, iou in assignments:
            if ti in matched_tracks or di in matched_dets:
                continue
            # Match found
            track = self._tracks[ti]
            det = detections[di]
            det.track_id = track.track_id
            track.bbox = det.bbox
            track.class_name = det.bbox.class_name
            track.age += 1
            track.missing_frames = 0
            track.total_visible += 1
            matched_tracks.add(ti)
            matched_dets.add(di)

        # Create new tracks for unmatched detections
        for di, det in enumerate(detections):
            if di not in matched_dets:
                det.track_id = self._next_id
                self._tracks.append(Track(
                    track_id=self._next_id,
                    bbox=det.bbox,
                    class_name=det.bbox.class_name,
                ))
                self._next_id += 1

        # Increment missing count for unmatched tracks
        for ti, track in enumerate(self._tracks):
            if ti not in matched_tracks:
                track.missing_frames += 1

        # Remove stale tracks
        self._tracks = [
            t for t in self._tracks
            if t.missing_frames <= self._max_missing_frames
        ]

        return detections

    def reset(self) -> None:
        """Clear all tracks."""
        self._tracks.clear()
        self._next_id = 1

    @property
    def active_tracks(self) -> list[Track]:
        """Get currently active tracks."""
        return [t for t in self._tracks if t.missing_frames == 0]

    @property
    def all_tracks(self) -> list[Track]:
        return list(self._tracks)
