# Helmet Detection Model - Quick Start Guide

This guide provides the fastest path to training and deploying the helmet detection model.

## Prerequisites

- Python 3.11+
- 500+ labeled images per class (helmet, no_helmet)
- ~2GB disk space for training
- TensorFlow 2.13+ installed

## 5-Minute Setup

### 1. Install Dependencies

```bash
pip install -r scripts/requirements-training.txt
```

### 2. Prepare Dataset

Download from **Kaggle** (recommended for Indian traffic):
```bash
pip install kaggle
kaggle datasets download -d aryanvaid13/indian-helmet-detection-dataset
unzip indian-helmet-detection-dataset.zip -d data/helmet_dataset
```

Or organize your own data:
```
data/helmet_dataset/
├── train/
│   ├── helmet/       # 500+ images
│   └── no_helmet/    # 500+ images
└── val/
    ├── helmet/       # 100+ images
    └── no_helmet/    # 100+ images
```

### 3. Train Model (30-60 minutes)

```bash
python scripts/train_helmet.py --data-dir data/helmet_dataset
```

**Output**: `models/helmet_model_YYYYMMDD_HHMMSS/`

### 4. Convert to TFLite (2-5 minutes)

```bash
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000 \
    --validate
```

**Output**: `models/helmet_cls_int8.tflite` (~1.2 MB)

### 5. Configure and Test

Update `config/settings.yaml`:
```yaml
helmet:
  enabled: true
  model_path: models/helmet_cls_int8.tflite
  threshold: 0.5
```

Test:
```bash
python -m src.main --video data/test_traffic.mp4
```

## Expected Results

- **Model Size**: ~1.2 MB (INT8 quantized)
- **Inference Time**: 5-10ms on Raspberry Pi 4
- **Accuracy**: >90% on validation set
- **Training Time**: 30-60 minutes (CPU), 10-15 minutes (GPU)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Low accuracy (<80%) | Increase epochs to 75, check dataset balance |
| Slow training | Use GPU if available, reduce batch size |
| Model not found | Check path in config, verify conversion completed |
| Import error | `pip install tensorflow tflite-runtime` |

## Advanced Options

### Custom Training

```bash
python scripts/train_helmet.py \
    --data-dir data/helmet_dataset \
    --epochs 75 \
    --batch-size 64 \
    --lr 0.0005 \
    --augment
```

### Resume Training

```bash
python scripts/train_helmet.py \
    --data-dir data/helmet_dataset \
    --resume models/helmet_model_20260209_120000 \
    --epochs 20
```

### Custom Calibration

```bash
python scripts/convert_model.py \
    --model models/helmet_model_20260209_120000 \
    --calib-dir data/helmet_dataset/val \
    --num-calib 200
```

## Deployment to Raspberry Pi

```bash
# Package model
tar -czf helmet_model.tar.gz models/helmet_cls_int8.tflite

# Copy to Pi
scp helmet_model.tar.gz pi@raspberrypi.local:/opt/traffic-eye/

# Extract and restart
ssh pi@raspberrypi.local "cd /opt/traffic-eye && tar -xzf helmet_model.tar.gz && sudo systemctl restart traffic-eye"
```

## Next Steps

- Fine-tune threshold based on precision/recall requirements
- Collect misclassified examples for retraining
- Monitor performance logs for edge cases
- Set up periodic retraining (quarterly recommended)

## Resources

- Full documentation: `models/README.md`
- Model metadata: `models/helmet_model_metadata.json`
- Training script: `scripts/train_helmet.py`
- Conversion script: `scripts/convert_model.py`

## Dataset Sources

1. **Kaggle - Indian Helmet Detection**: https://www.kaggle.com/datasets/aryanvaid13/indian-helmet-detection-dataset
2. **RoboFlow - Helmet Detection**: https://universe.roboflow.com/gw-khadatkar-and-sv-wasule/helmet-and-no-helmet-rider-detection
3. **Custom Data**: Record traffic footage and extract head crops using YOLO

## Support

For issues or questions:
- Check `models/README.md` for detailed troubleshooting
- Review training logs: `models/helmet_model_*/training_log.csv`
- Test with mock mode: `python -m src.main --mock`
