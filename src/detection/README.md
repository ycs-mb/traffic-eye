# src/detection/

Object detection, classification, and tracking modules. Handles the ML inference portion of the pipeline.

## Files

| File | Purpose |
|------|---------|
| `detector.py` | Object detection (YOLOv8n TFLite + mock) |
| `helmet.py` | Binary helmet classifier (MobileNetV3 TFLite + mock) |
| `signal.py` | Traffic signal color detection via HSV analysis |
| `tracker.py` | IoU-based multi-object tracker |

## detector.py - Object Detection

Detects objects (persons, vehicles, traffic lights) in camera frames.

### Interface

```python
class DetectorBase(ABC):
    def load_model(model_path: str) -> None
    def detect(frame: ndarray, frame_id: int) -> list[Detection]
    def is_loaded() -> bool
```

### TFLiteDetector

Runs YOLOv8n INT8 inference using TFLite Runtime:
- Input: BGR frame resized to model input dimensions
- Normalization: auto-detected (uint8 or float32)
- Output parsing: handles common YOLO output format `(1, N, 6)` where columns are `[x1, y1, x2, y2, confidence, class_id]`
- Coordinates are scaled back to original frame dimensions
- Filtered by `confidence_threshold` from config

### MockDetector

Two modes for testing:
- **JSON file mode**: Load pre-defined detections from a JSON file keyed by frame ID
- **Random mode**: Generate random bounding boxes with random classes each frame

### Model Requirements

The `yolov8n_int8.tflite` model must be placed in the `models/` directory. To create it:

1. Export from Ultralytics YOLOv8:
   ```python
   from ultralytics import YOLO
   model = YOLO("yolov8n.pt")
   model.export(format="tflite", int8=True)
   ```

2. Copy the resulting `.tflite` file to `models/yolov8n_int8.tflite`

## helmet.py - Helmet Classifier

Binary classifier that determines whether a cropped head region shows a helmet.

### Interface

```python
class HelmetClassifierBase(ABC):
    def load_model(model_path: str) -> None
    def classify(head_crop: ndarray) -> (bool, float)  # (has_helmet, confidence)
    def is_loaded() -> bool
```

### TFLiteHelmetClassifier

- Input: head crop resized to 96x96 (configurable)
- Model: MobileNetV3-based binary classifier, INT8 quantized
- Output: sigmoid score. > 0.5 = helmet present
- Returns `(has_helmet, confidence)` where confidence is always the certainty of the prediction

### MockHelmetClassifier

Returns configurable results. Default: `(False, 0.92)` (no helmet with 92% confidence). Useful for testing the violation pipeline without a real model.

### Training the Helmet Model

Train a custom helmet classifier using a dataset of helmet/no-helmet head crops:

```python
# See scripts/train_helmet.py for the training pipeline
# Export to TFLite INT8 after training
```

## signal.py - Traffic Signal Classifier

Lightweight HSV color analysis to determine traffic signal state. No ML model required.

### How it Works

1. Receives a cropped traffic signal image
2. Applies a circular mask (traffic lights are circular) to reduce housing noise
3. Converts to HSV color space
4. Counts pixels in predefined color ranges:
   - **Red**: H 0-10 and H 170-180 (red wraps around in HSV)
   - **Yellow**: H 15-35
   - **Green**: H 40-90
5. Returns the dominant color if its pixel ratio exceeds `min_pixel_ratio` (default 5%)

### Usage

```python
classifier = TrafficSignalClassifier()
state = classifier.classify(signal_crop)  # Returns SignalState enum
```

### Limitations

- Requires the traffic signal to be reasonably visible and well-lit
- Performance degrades at night or in heavy rain
- HSV ranges may need tuning for specific locations

## tracker.py - IoU Tracker

Simple greedy Intersection-over-Union tracker that assigns consistent track IDs to detected objects across frames.

### Algorithm

1. **First frame**: Create a new track for every detection
2. **Subsequent frames**:
   - Compute IoU between each detection and each existing track
   - Sort matches by IoU descending
   - Greedily assign: best IoU match first, skip already-matched pairs
   - Create new tracks for unmatched detections
   - Increment `missing_frames` for unmatched tracks
   - Remove tracks missing for more than `max_missing_frames` (default: 5)

### Usage

```python
tracker = IOUTracker(iou_threshold=0.3, max_missing_frames=5)
detections = tracker.update(detections)  # Returns same detections with track_id set
```

### Why IoU Tracking?

More sophisticated trackers (DeepSORT, ByteTrack) are too expensive for Pi 4 at the required frame rate. IoU tracking is O(N*M) per frame and sufficient for urban traffic scenes where objects don't move drastically between frames at 4-6 fps.

## Pipeline Flow

```
Frame -> TFLiteDetector.detect()
           |
           v
     IOUTracker.update()  -- assigns track IDs
           |
           v
     For each "person" detection:
         crop head region -> HelmetClassifier.classify()
           |
           v
     For each "traffic light" detection:
         crop signal -> TrafficSignalClassifier.classify()
           |
           v
     Results passed to violation RuleEngine
```

## Deployment on Raspberry Pi

- TFLite Runtime is optimized for ARM: `pip install tflite-runtime`
- INT8 quantized models run 2-3x faster than float32 on Pi 4
- Set `detection.num_threads: 4` to use all Pi 4 cores
- Expected throughput: 4-6 fps at 720p with YOLOv8n INT8
