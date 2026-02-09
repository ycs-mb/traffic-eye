# models/

TFLite model files for on-device ML inference. These files are not included in the repository and must be prepared separately.

## Required Models

| File | Model | Purpose | Input Size | Format |
|------|-------|---------|------------|--------|
| `yolov8n_int8.tflite` | YOLOv8n | Object detection (person, vehicle, traffic light) | 640x640 | INT8 quantized |
| `helmet_cls_int8.tflite` | MobileNetV3 | Binary helmet classification | 96x96 | INT8 quantized |

## Preparing the Object Detection Model

### Option 1: Export from Ultralytics (Recommended)

```bash
pip install ultralytics

python -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='tflite', int8=True, imgsz=640)
"

# Copy the exported model
cp yolov8n_saved_model/yolov8n_int8.tflite models/
```

### Option 2: Convert from ONNX

```bash
pip install onnx onnxruntime tf2onnx tensorflow

# Export to ONNX
yolo export model=yolov8n.pt format=onnx

# Convert ONNX to TFLite with INT8 quantization
python scripts/convert_model.py --input yolov8n.onnx --output models/yolov8n_int8.tflite --quantize int8
```

### Model Output Format

The `TFLiteDetector` expects YOLO output in `(1, N, 6)` format:
- N = number of detections
- 6 columns: `[x1, y1, x2, y2, confidence, class_id]`
- Coordinates normalized to [0, 1]

### COCO Classes Used

The detector filters for these COCO class IDs:

| Class ID | Name |
|----------|------|
| 0 | person |
| 1 | bicycle |
| 2 | car |
| 3 | motorcycle |
| 5 | bus |
| 7 | truck |
| 9 | traffic light |

## Preparing the Helmet Classifier

### Dataset Collection

The helmet classifier requires a dataset of head crops labeled as `helmet` or `no_helmet`. Use these recommended data sources:

#### Recommended Datasets

1. **RoboFlow Universe** (Recommended for quick start):
   - [Helmet and No Helmet Rider Detection](https://universe.roboflow.com/gw-khadatkar-and-sv-wasule/helmet-and-no-helmet-rider-detection) - YOLO-based dataset
   - [Helmet Detection Project](https://universe.roboflow.com/nckh-2023/helmet-detection-project) - Traffic enforcement focused
   - [Helmet Detection with License Plates](https://universe.roboflow.com/onlytusik/helmet-detection-fk6is) - Includes number plate detection

2. **Kaggle Datasets**:
   - [Indian Helmet Detection Dataset](https://www.kaggle.com/datasets/aryanvaid13/indian-helmet-detection-dataset) - **Best for Indian traffic**
   - [General Helmet Detection](https://www.kaggle.com/datasets/andrewmvd/helmet-detection)

3. **Custom Dataset** (Most accurate for your deployment):
   - Record traffic footage from your target location
   - Extract head crops using YOLO person detection
   - Manually label 500+ samples per class
   - Ensures model learns local traffic patterns

#### Dataset Structure

Organize your dataset in this structure:

```
data/helmet_dataset/
├── train/
│   ├── helmet/       # 500+ images with helmet
│   └── no_helmet/    # 500+ images without helmet
└── val/
    ├── helmet/       # 100+ images with helmet
    └── no_helmet/    # 100+ images without helmet
```

#### Data Quality Guidelines

- **Image size**: Minimum 96x96, consistent aspect ratio
- **Format**: JPG or PNG
- **Diversity**: Include various lighting conditions, angles, helmet types
- **Balance**: Equal samples for helmet/no_helmet classes
- **Indian context**: Different helmet designs (full-face, half-face, open-face)

### Training the Model

Use the provided training script to train a MobileNetV3-Small classifier:

```bash
# Install training dependencies
pip install tensorflow scikit-learn

# Train with default settings (50 epochs, Adam optimizer)
python scripts/train_helmet.py --data-dir data/helmet_dataset

# Train with custom parameters
python scripts/train_helmet.py \
    --data-dir data/helmet_dataset \
    --epochs 75 \
    --batch-size 64 \
    --lr 0.0005 \
    --augment

# Resume training from checkpoint
python scripts/train_helmet.py \
    --data-dir data/helmet_dataset \
    --resume models/helmet_model_20260209_120000
```

#### Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--data-dir` | Required | Path to dataset directory |
| `--output-dir` | `models/` | Where to save trained model |
| `--epochs` | 50 | Number of training epochs |
| `--batch-size` | 32 | Batch size for training |
| `--lr` | 0.001 | Learning rate |
| `--augment` | True | Enable data augmentation |
| `--seed` | 42 | Random seed for reproducibility |

#### Training Process

The training script implements:
- **Transfer Learning**: MobileNetV3-Small backbone pretrained on ImageNet
- **Data Augmentation**: Random flips, rotation, zoom, contrast, brightness
- **Regularization**: Dropout layers to prevent overfitting
- **Early Stopping**: Stops training if validation loss plateaus
- **Learning Rate Scheduling**: Reduces LR when validation loss doesn't improve
- **Model Checkpointing**: Saves best model based on validation accuracy

#### Expected Training Time

- Raspberry Pi 4: ~4-6 hours (50 epochs, 1000 images)
- Desktop PC (CPU): ~1-2 hours
- Desktop PC (GPU): ~15-30 minutes

### Converting to TFLite INT8

After training, convert the model to TFLite INT8 for edge deployment:

```bash
# Basic conversion
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000

# Conversion with validation
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000 \
    --validate

# Conversion with custom calibration dataset
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000 \
    --calib-dir data/helmet_dataset/val \
    --num-calib 200 \
    --validate
```

#### Conversion Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--model` | Required | Path to trained SavedModel directory |
| `--output` | `models/helmet_cls_int8.tflite` | Output path for TFLite model |
| `--calib-dir` | None | Directory with calibration images |
| `--num-calib` | 100 | Number of calibration samples |
| `--validate` | False | Validate converted model |

#### What is INT8 Quantization?

INT8 quantization converts 32-bit floating point weights to 8-bit integers:

**Benefits**:
- 4x smaller model size (~5MB → ~1.2MB)
- 2-3x faster inference on Raspberry Pi
- Lower memory footprint

**Process**:
1. Loads trained TensorFlow SavedModel
2. Uses representative dataset for calibration
3. Converts weights and activations to INT8
4. Keeps input as UINT8, output as FLOAT32
5. Validates accuracy against original model

**Expected Accuracy Impact**: <2% accuracy drop with proper calibration

### Model Validation

After conversion, validate the model performs correctly:

```bash
# Automatic validation (recommended)
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000 \
    --validate

# Manual testing with Python
python -c "
import numpy as np
import tensorflow as tf

# Load TFLite model
interpreter = tf.lite.Interpreter(model_path='models/helmet_cls_int8.tflite')
interpreter.allocate_tensors()

# Get input/output details
inp = interpreter.get_input_details()[0]
out = interpreter.get_output_details()[0]

print(f'Input:  shape={inp[\"shape\"]}, dtype={inp[\"dtype\"]}')
print(f'Output: shape={out[\"shape\"]}, dtype={out[\"dtype\"]}')

# Test with random image
test_img = np.random.randint(0, 256, (1, 96, 96, 3), dtype=np.uint8)
interpreter.set_tensor(inp['index'], test_img)
interpreter.invoke()
result = interpreter.get_tensor(out['index'])

print(f'Test output: {result[0][0]:.4f}')
"
```

### Retraining the Model

Retrain when:
- Accuracy drops below 85% on validation set
- Deploying to a new region with different helmet types
- False positive/negative rate becomes unacceptable

#### Incremental Training

```bash
# Fine-tune existing model with new data
python scripts/train_helmet.py \
    --data-dir data/new_helmet_dataset \
    --resume models/helmet_model_20260209_120000 \
    --epochs 20 \
    --lr 0.0001  # Lower learning rate for fine-tuning
```

#### From Scratch

```bash
# Start fresh training
python scripts/train_helmet.py \
    --data-dir data/combined_helmet_dataset \
    --epochs 50
```

### Expected Accuracy Metrics

#### Validation Set Performance

With a well-curated dataset, expect these metrics on held-out validation data:

| Metric | Expected Range | Target |
|--------|---------------|--------|
| Accuracy | 88-95% | >90% |
| Precision (helmet) | 85-92% | >88% |
| Recall (helmet) | 90-95% | >92% |
| F1-Score | 88-93% | >90% |
| False Positive Rate | <8% | <5% |
| False Negative Rate | <6% | <4% |

**Note**: Actual performance depends on:
- Dataset quality and diversity
- Representative calibration data for quantization
- Similarity between training and deployment environments

#### Real-World Performance

In production deployment, expect:
- **Best case** (good lighting, clear view): 92-96% accuracy
- **Average case** (typical traffic): 85-90% accuracy
- **Challenging case** (occlusions, poor lighting): 70-80% accuracy

### Known Limitations

1. **Occlusion Sensitivity**:
   - Accuracy drops when >70% of head is obscured
   - Struggles with side-angle views
   - May miss helmets if only back of head is visible

2. **Lighting Conditions**:
   - Reduced performance in very low light (<10 lux)
   - Overexposed images may cause misclassification
   - Shadows can be mistaken for dark helmets

3. **Visual Similarities**:
   - May confuse colored caps/hats with half-face helmets
   - Reflective surfaces can cause false positives
   - Loose-fitting helmets may be classified as no helmet

4. **Dataset Dependency**:
   - Performance tied to training data diversity
   - Regional variations in helmet styles require retraining
   - Model learns helmet types seen during training

5. **Input Quality**:
   - Relies on accurate head detection from YOLO
   - Poor crop quality (too small, wrong aspect ratio) reduces accuracy
   - Motion blur from moving vehicles impacts performance

### Accuracy Tuning

Adjust confidence threshold based on use case:

```yaml
# config/settings.yaml
helmet:
  model_path: models/helmet_cls_int8.tflite
  enabled: true
  threshold: 0.5  # Default balanced threshold
```

**Threshold Recommendations**:
- **High Precision** (reduce false positives): `threshold: 0.6`
  - Use when legal evidence quality is critical
  - Trade-off: May miss some violations
- **High Recall** (catch more violations): `threshold: 0.4`
  - Use for awareness campaigns
  - Trade-off: More false positives
- **Balanced** (default): `threshold: 0.5`
  - Good balance for most deployments

### Continuous Improvement

To maintain accuracy over time:

1. **Monitor Performance**:
   - Track false positive/negative rates
   - Log misclassifications for analysis
   - Collect edge cases for retraining

2. **Update Training Data**:
   - Add misclassified examples to dataset
   - Include new helmet designs
   - Expand dataset with seasonal variations

3. **Retrain Periodically**:
   - Quarterly retraining recommended
   - Immediate retraining if accuracy <85%
   - Version control models for rollback

## Performance on Raspberry Pi 4

| Model | Input Size | Inference Time | Memory | Accuracy |
|-------|-----------|---------------|--------|----------|
| YOLOv8n INT8 | 640x640 | ~150-200ms | ~50MB | ~45 mAP (COCO) |
| Helmet MobileNetV3 INT8 | 96x96 | ~5-10ms | ~5MB | ~90% (custom) |

**Optimization Details**:
- INT8 quantization gives 2-3x speedup over float32
- Set `detection.num_threads: 4` to use all Pi 4 cores
- Combined throughput: 4-6 fps at 720p
- Memory efficient: ~150MB total for both models

**Raspberry Pi Configuration**:
```bash
# Enable all CPU cores
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Increase GPU memory (helps with camera capture)
# In /boot/config.txt:
gpu_mem=128
```

## Directory Structure

```
models/
├── yolov8n_int8.tflite          # Object detection
├── helmet_cls_int8.tflite       # Helmet classifier
└── README.md                    # This file
```

## Complete Deployment Workflow

### Step-by-Step Guide

#### 1. Prepare Training Environment

```bash
# Install training dependencies
pip install tensorflow scikit-learn

# Verify TensorFlow installation
python -c "import tensorflow as tf; print(tf.__version__)"
```

#### 2. Collect and Prepare Dataset

```bash
# Download dataset (example: Kaggle)
# Option 1: Use Kaggle API
kaggle datasets download -d aryanvaid13/indian-helmet-detection-dataset
unzip indian-helmet-detection-dataset.zip -d data/helmet_dataset

# Option 2: Download from RoboFlow
# Visit: https://universe.roboflow.com/gw-khadatkar-and-sv-wasule/helmet-and-no-helmet-rider-detection
# Export as "Folder Structure" and organize into train/val splits

# Verify dataset structure
tree data/helmet_dataset/
```

#### 3. Train Model

```bash
# Train with default settings
python scripts/train_helmet.py --data-dir data/helmet_dataset

# Monitor training progress (output will show):
# - Training/validation loss and accuracy per epoch
# - Best model checkpoint saves
# - CSV log for visualization

# Expected output:
# Epoch 1/50: loss: 0.6234 - accuracy: 0.6543 - val_loss: 0.5432 - val_accuracy: 0.7123
# ...
# Epoch 45/50: loss: 0.1234 - accuracy: 0.9543 - val_loss: 0.2145 - val_accuracy: 0.9234
# Model saved to models/helmet_model_20260209_120000
```

#### 4. Convert to TFLite

```bash
# Convert to TFLite INT8 with validation
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000 \
    --calib-dir data/helmet_dataset/val \
    --validate

# Expected output:
# Loading model for conversion...
# Converting to TFLite INT8 (this may take a few minutes)...
# Conversion complete! Model size: 1187.3 KB
# TFLite model saved to: models/helmet_cls_int8.tflite
# Model Info:
#   Input:  shape=[1, 96, 96, 3], dtype=<class 'numpy.uint8'>
#   Output: shape=[1, 1], dtype=<class 'numpy.float32'>
# Validation complete:
#   Average difference: 0.002341
#   Maximum difference: 0.018734
# Quantization quality: GOOD
```

#### 5. Configure Application

```bash
# Update config/settings.yaml
helmet:
  enabled: true
  model_path: models/helmet_cls_int8.tflite
  threshold: 0.5
```

#### 6. Test Integration

```bash
# Test with mock data
python -m src.main --mock

# Test with video file
python -m src.main --video data/test_traffic.mp4

# Monitor logs for helmet detections
tail -f data/logs/traffic-eye.log | grep "helmet"
```

#### 7. Deploy to Raspberry Pi

```bash
# On development machine, prepare deployment package
tar -czf helmet_model_deploy.tar.gz \
    models/helmet_cls_int8.tflite \
    models/helmet_model_metadata.json \
    config/settings.yaml

# Copy to Raspberry Pi
scp helmet_model_deploy.tar.gz pi@raspberrypi.local:/tmp/

# On Raspberry Pi, extract and install
ssh pi@raspberrypi.local
cd /opt/traffic-eye
tar -xzf /tmp/helmet_model_deploy.tar.gz

# Restart service
sudo systemctl restart traffic-eye

# Monitor performance
journalctl -u traffic-eye -f | grep "helmet"
```

### Testing and Validation

#### Unit Testing

```bash
# Run helmet classifier tests
pytest tests/test_detection/test_helmet.py -v

# Expected tests:
# - test_mock_classifier_default_behavior
# - test_tflite_classifier_loading
# - test_tflite_classifier_inference
# - test_tflite_classifier_error_handling
```

#### Integration Testing

Create a test script to validate model performance:

```python
# test_helmet_model.py
import cv2
import numpy as np
from pathlib import Path
from src.detection.helmet import TFLiteHelmetClassifier

def test_helmet_model(test_images_dir):
    classifier = TFLiteHelmetClassifier()
    classifier.load_model("models/helmet_cls_int8.tflite")

    results = {"correct": 0, "total": 0}

    for class_name in ["helmet", "no_helmet"]:
        class_dir = test_images_dir / class_name
        expected = (class_name == "helmet")

        for img_path in class_dir.glob("*.jpg"):
            img = cv2.imread(str(img_path))
            has_helmet, confidence = classifier.classify(img)

            results["total"] += 1
            if has_helmet == expected:
                results["correct"] += 1
            else:
                print(f"FAIL: {img_path.name} - predicted={has_helmet}, expected={expected}")

    accuracy = results["correct"] / results["total"]
    print(f"Test Accuracy: {accuracy:.2%} ({results['correct']}/{results['total']})")

    return accuracy > 0.85  # Pass if >85% accuracy

if __name__ == "__main__":
    test_images = Path("data/helmet_dataset/test")
    passed = test_helmet_model(test_images)
    exit(0 if passed else 1)
```

#### Performance Benchmarking

```python
# benchmark_helmet.py
import time
import numpy as np
from src.detection.helmet import TFLiteHelmetClassifier

def benchmark_inference(model_path, num_iterations=100):
    classifier = TFLiteHelmetClassifier(num_threads=4)
    classifier.load_model(model_path)

    # Generate random test image
    test_img = np.random.randint(0, 256, (96, 96, 3), dtype=np.uint8)

    # Warmup
    for _ in range(10):
        classifier.classify(test_img)

    # Benchmark
    start = time.time()
    for _ in range(num_iterations):
        classifier.classify(test_img)
    elapsed = time.time() - start

    avg_time = (elapsed / num_iterations) * 1000  # ms
    fps = num_iterations / elapsed

    print(f"Average inference time: {avg_time:.2f} ms")
    print(f"Throughput: {fps:.1f} FPS")

    return avg_time

if __name__ == "__main__":
    benchmark_inference("models/helmet_cls_int8.tflite")
```

## Model Versioning and Metadata

All trained models include metadata for tracking and reproducibility:

```json
// models/helmet_model_metadata.json
{
  "model_name": "helmet_cls_int8",
  "version": "1.0.0",
  "training_date": "2026-02-09",
  "architecture": "MobileNetV3-Small",
  "metrics": {
    "accuracy": 0.9234,
    "precision": 0.8912,
    "recall": 0.9456,
    "f1_score": 0.9176
  }
}
```

**Version Control Best Practices**:
- Tag model versions in metadata file
- Keep training logs and checkpoints
- Document dataset sources and preprocessing
- Track quantization impact on accuracy

## Troubleshooting

### Common Issues

**1. Low Training Accuracy (<80%)**
- Increase training epochs (try 75-100)
- Check dataset balance (equal samples per class)
- Verify image quality and diversity
- Try lower learning rate (0.0005)

**2. High Quantization Error (>5% accuracy drop)**
- Use more calibration samples (200-500)
- Ensure calibration data represents deployment distribution
- Check for data preprocessing mismatches

**3. Slow Inference on Raspberry Pi (>20ms)**
- Verify `num_threads=4` is set
- Check CPU governor is set to "performance"
- Monitor thermal throttling (keep Pi <75°C)
- Reduce input resolution if acceptable

**4. Model File Not Found**
```
FileNotFoundError: Helmet model not found: models/helmet_cls_int8.tflite
```
- Run conversion script: `python scripts/convert_model.py`
- Check file permissions
- Verify path in config/settings.yaml

**5. Import Error (tflite-runtime)**
```
ImportError: Neither tflite-runtime nor tensorflow is installed
```
- Install: `pip install tflite-runtime`
- Or: `pip install tensorflow` (larger)

## Fallback Behavior

If model files are missing or TFLite Runtime is not installed, the application automatically falls back to mock implementations:
- `MockDetector` generates random detections
- `MockHelmetClassifier` returns configurable results

This allows testing the full pipeline without models. Use `--mock` flag to force mock mode explicitly.

```bash
# Test without models
python -m src.main --mock

# Check if mock mode is active
tail -f data/logs/traffic-eye.log | grep "Mock"
```
