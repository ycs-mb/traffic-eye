"""Object detection abstraction with mock and TFLite implementations."""

from __future__ import annotations

import json
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from src.models import BoundingBox, Detection

logger = logging.getLogger(__name__)


class DetectorBase(ABC):
    """Abstract base class for object detection."""

    @abstractmethod
    def load_model(self, model_path: str) -> None:
        """Load detection model from disk."""

    @abstractmethod
    def detect(self, frame: np.ndarray, frame_id: int = 0) -> list[Detection]:
        """Run detection on a frame. Returns list of detections."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""


class MockDetector(DetectorBase):
    """Returns pre-configured or random detection results for testing.

    Two modes:
    - JSON file mode: Load detections from a JSON file keyed by frame_id.
    - Random mode: Generate random bounding boxes each frame.
    """

    def __init__(
        self,
        detections_file: Optional[str] = None,
        random_mode: bool = False,
        random_classes: Optional[list[str]] = None,
        random_max_objects: int = 5,
        confidence_range: tuple[float, float] = (0.5, 0.99),
    ):
        self._detections_map: dict[int, list[Detection]] = {}
        self._detections_file = detections_file
        self._random_mode = random_mode
        self._random_classes = random_classes or [
            "person", "motorcycle", "car", "truck", "traffic light"
        ]
        self._random_max_objects = random_max_objects
        self._confidence_range = confidence_range
        self._loaded = False

    def load_model(self, model_path: str = "") -> None:
        if self._detections_file:
            self._load_from_json(self._detections_file)
        self._loaded = True
        logger.info("Mock detector loaded (random_mode=%s)", self._random_mode)

    def _load_from_json(self, path: str) -> None:
        """Load detections from JSON file.

        Expected format:
        {
            "0": [{"x1": 100, "y1": 200, "x2": 300, "y2": 400,
                   "confidence": 0.9, "class_name": "person"}],
            "1": [...]
        }
        """
        data = json.loads(Path(path).read_text())
        for frame_id_str, dets in data.items():
            frame_id = int(frame_id_str)
            self._detections_map[frame_id] = [
                Detection(
                    bbox=BoundingBox(
                        x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"],
                        confidence=d["confidence"],
                        class_name=d["class_name"],
                        class_id=d.get("class_id", 0),
                    ),
                    frame_id=frame_id,
                    timestamp=datetime.now(timezone.utc),
                )
                for d in dets
            ]

    def detect(self, frame: np.ndarray, frame_id: int = 0) -> list[Detection]:
        if not self._loaded:
            return []

        # JSON file mode
        if frame_id in self._detections_map:
            return self._detections_map[frame_id]

        # Random mode
        if self._random_mode:
            return self._generate_random(frame, frame_id)

        return []

    def _generate_random(self, frame: np.ndarray, frame_id: int) -> list[Detection]:
        h, w = frame.shape[:2]
        num_objects = random.randint(0, self._random_max_objects)
        detections = []

        for _ in range(num_objects):
            cls = random.choice(self._random_classes)
            bw = random.randint(30, w // 3)
            bh = random.randint(30, h // 3)
            x1 = random.randint(0, w - bw)
            y1 = random.randint(0, h - bh)
            conf = random.uniform(*self._confidence_range)

            detections.append(Detection(
                bbox=BoundingBox(
                    x1=float(x1), y1=float(y1),
                    x2=float(x1 + bw), y2=float(y1 + bh),
                    confidence=conf,
                    class_name=cls,
                ),
                frame_id=frame_id,
                timestamp=datetime.now(timezone.utc),
            ))

        return detections

    def is_loaded(self) -> bool:
        return self._loaded

    def set_detections(self, frame_id: int, detections: list[Detection]) -> None:
        """Manually set detections for a specific frame (for testing)."""
        self._detections_map[frame_id] = detections


class TFLiteDetector(DetectorBase):
    """TFLite-based YOLOv8 detector.

    Handles YOLOv8 TFLite output format: (1, 84, N) where 84 = 4 (xywh) + 80 (COCO classes).
    The 4 box values are center_x, center_y, width, height in pixel coordinates
    relative to the model input size. The 80 class values are raw scores (no sigmoid needed
    for ultralytics TFLite export — already applied).

    Import-guarded: only usable when tflite-runtime or ai-edge-litert is installed.
    """

    # COCO class names (80 classes, indexed 0-79)
    COCO_CLASSES = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
        "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
        "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
        "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
        "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
        "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
        "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
        "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
        "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
        "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
        "hair drier", "toothbrush",
    ]

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.45,
        num_threads: int = 4,
        target_classes: tuple[str, ...] | None = None,
    ):
        self._confidence_threshold = confidence_threshold
        self._nms_threshold = nms_threshold
        self._num_threads = num_threads
        self._target_classes = set(target_classes) if target_classes else None
        self._interpreter = None
        self._input_details = None
        self._output_details = None
        self._input_h = 0
        self._input_w = 0
        self._loaded = False

    def load_model(self, model_path: str) -> None:
        try:
            import tflite_runtime.interpreter as tflite
        except ImportError:
            try:
                import ai_edge_litert.interpreter as tflite
            except ImportError:
                try:
                    import tensorflow.lite as tflite
                except ImportError:
                    raise ImportError(
                        "Neither tflite-runtime nor tensorflow is installed. "
                        "Install with: pip install tflite-runtime"
                    )

        self._interpreter = tflite.Interpreter(
            model_path=model_path,
            num_threads=self._num_threads,
        )
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()
        input_shape = self._input_details[0]["shape"]
        self._input_h = input_shape[1]
        self._input_w = input_shape[2]
        self._loaded = True

        logger.info(
            "TFLite detector loaded: %s (input=%dx%d, output=%s)",
            model_path, self._input_w, self._input_h,
            self._output_details[0]["shape"],
        )

    def detect(self, frame: np.ndarray, frame_id: int = 0) -> list[Detection]:
        if not self._loaded or self._interpreter is None:
            return []

        import cv2

        frame_h, frame_w = frame.shape[:2]

        # Preprocess: resize to model input, normalize to [0, 1]
        resized = cv2.resize(frame, (self._input_w, self._input_h))

        input_dtype = self._input_details[0]["dtype"]
        if input_dtype == np.uint8:
            input_data = np.expand_dims(resized, axis=0)
        else:
            input_data = np.expand_dims(resized.astype(np.float32) / 255.0, axis=0)

        self._interpreter.set_tensor(self._input_details[0]["index"], input_data)
        self._interpreter.invoke()

        output = self._interpreter.get_tensor(self._output_details[0]["index"])
        return self._parse_yolov8_output(output, frame_w, frame_h, frame_id)

    def _parse_yolov8_output(
        self,
        output: np.ndarray,
        frame_w: int,
        frame_h: int,
        frame_id: int,
    ) -> list[Detection]:
        """Parse YOLOv8 output tensor (1, 84, N) into Detection objects with NMS.

        Output layout per prediction (column):
          [0:4]  = cx, cy, w, h (in model input pixel coords)
          [4:84] = class scores for 80 COCO classes
        """
        # (1, 84, N) -> (84, N) -> (N, 84) for easier row iteration
        if output.ndim == 3:
            output = output[0]
        predictions = output.T  # (N, 84)

        # Extract boxes and class scores
        boxes_xywh = predictions[:, :4]  # (N, 4) — cx, cy, w, h (normalized 0-1)
        class_scores = predictions[:, 4:]  # (N, 80)

        # Get best class per prediction
        class_ids = np.argmax(class_scores, axis=1)  # (N,)
        confidences = class_scores[np.arange(len(class_ids)), class_ids]  # (N,)

        # Filter by confidence threshold
        mask = confidences >= self._confidence_threshold
        if not mask.any():
            return []

        boxes_xywh = boxes_xywh[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]

        # Convert normalized xywh (center) to xyxy (corners) in original frame coords
        cx = boxes_xywh[:, 0] * frame_w
        cy = boxes_xywh[:, 1] * frame_h
        w = boxes_xywh[:, 2] * frame_w
        h = boxes_xywh[:, 3] * frame_h
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2

        # Clip to frame bounds
        x1 = np.clip(x1, 0, frame_w)
        y1 = np.clip(y1, 0, frame_h)
        x2 = np.clip(x2, 0, frame_w)
        y2 = np.clip(y2, 0, frame_h)

        # NMS
        indices = self._nms(x1, y1, x2, y2, confidences, self._nms_threshold)

        now = datetime.now(timezone.utc)
        detections = []

        for i in indices:
            cid = int(class_ids[i])
            class_name = self.COCO_CLASSES[cid] if cid < len(self.COCO_CLASSES) else str(cid)

            # Filter to target classes if specified
            if self._target_classes and class_name not in self._target_classes:
                continue

            detections.append(Detection(
                bbox=BoundingBox(
                    x1=float(x1[i]),
                    y1=float(y1[i]),
                    x2=float(x2[i]),
                    y2=float(y2[i]),
                    confidence=float(confidences[i]),
                    class_name=class_name,
                    class_id=cid,
                ),
                frame_id=frame_id,
                timestamp=now,
            ))

        return detections

    @staticmethod
    def _nms(
        x1: np.ndarray, y1: np.ndarray,
        x2: np.ndarray, y2: np.ndarray,
        scores: np.ndarray, threshold: float,
    ) -> list[int]:
        """Greedy Non-Maximum Suppression."""
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []

        while order.size > 0:
            i = order[0]
            keep.append(int(i))

            if order.size == 1:
                break

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

            remaining = np.where(iou <= threshold)[0]
            order = order[remaining + 1]

        return keep

    def is_loaded(self) -> bool:
        return self._loaded
