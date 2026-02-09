# Edge-AI Traffic Violation Detection System — Technical Architecture & Implementation Plan

---

## 1. System Architecture

### Hardware Layout

```
┌─────────────────────────────────────────────────────┐
│                   HELMET MOUNT                       │
│                                                      │
│  ┌──────────┐   CSI/USB   ┌──────────────────────┐  │
│  │ Pi Camera ├────────────►│   Raspberry Pi 4     │  │
│  │ Module v2 │             │   (4GB / 8GB)        │  │
│  └──────────┘             │                      │  │
│                            │  ┌────────────────┐  │  │
│  ┌──────────┐   UART/USB  │  │ MicroSD 64GB   │  │  │
│  │ GPS Module├────────────►│  │ (A2 class)     │  │  │
│  │ NEO-6M   │             │  └────────────────┘  │  │
│  └──────────┘             │                      │  │
│                            │  ┌────────────────┐  │  │
│  ┌──────────┐   GPIO      │  │ Status LED +   │  │  │
│  │ Power Bank├────────────►│  │ Buzzer         │  │  │
│  │ 10000mAh │             │  └────────────────┘  │  │
│  │ PD/QC    │             └──────────────────────┘  │
│  └──────────┘                                        │
└─────────────────────────────────────────────────────┘
```

### BOM (Prototype ~₹4,000)

| Component | Approx Cost (₹) | Notes |
|---|---|---|
| Raspberry Pi 4 (4GB) | ~₹3,200 (used/refurb) | 8GB preferred if available |
| Pi Camera Module v2 | ~₹300 | Or USB webcam ~₹200 |
| NEO-6M GPS Module | ~₹200 | UART interface |
| MicroSD 64GB A2 | ~₹400 | Fast random write matters |
| Power bank 10000mAh | Already owned | PD output preferred |
| Misc (wires, mount, case) | ~₹200 | 3D-printed helmet bracket |
| **Total** | **~₹4,300** | |

### Data Flow

```
Camera (30fps)
    │
    ▼
Frame Sampler (5-8 fps effective)
    │
    ▼
┌───────────────────────────────┐
│  On-Device Detection Pipeline │
│                               │
│  1. Object Detection (YOLOv8n)│
│     - vehicles, persons,      │
│       helmets, traffic lights  │
│  2. Plate Region Extraction   │
│  3. Rule Engine (violations)  │
└───────┬───────────┬───────────┘
        │           │
   No Violation   Violation Candidate
        │           │
      Drop      ┌───▼────────────────┐
                │ Evidence Buffer    │
                │ (5-sec clip +      │
                │  best frames)      │
                └───┬────────────────┘
                    │
                    ▼
             ┌──────────────┐
             │ OCR Pipeline  │
             │ (plate text)  │
             └──────┬───────┘
                    │
                    ▼
             Confidence ≥ 96%?
              /            \
           YES              NO
            │                │
     ┌──────▼──────┐  ┌─────▼──────────┐
     │ Local Report │  │ Queue for Cloud │
     │ Generation   │  │ Verification    │
     └──────┬──────┘  │ (when online)   │
            │         └─────┬──────────┘
            ▼               ▼
      Store locally    Send to GPT-4V/
      + queue email    Gemini Vision API
                            │
                            ▼
                     Confidence ≥ 96%?
                      /          \
                    YES          NO → Discard
                     │
                  Merge into report
```

---

## 2. Model Selection and Edge Optimization

### Object Detection

| Model | Size | Pi 4 FPS (est.) | mAP | Recommendation |
|---|---|---|---|---|
| YOLOv8n (TFLite INT8) | ~6MB | 4-6 fps | ~37 (COCO) | **Primary choice** |
| YOLOv5n (TFLite INT8) | ~4MB | 5-7 fps | ~28 (COCO) | Fallback / lighter |
| MobileNet-SSD v2 | ~6MB | 8-10 fps | ~22 (COCO) | If YOLO too slow |
| EfficientDet-Lite0 | ~5MB | 3-5 fps | ~26 (COCO) | Alternative |

**Primary recommendation: YOLOv8n quantized to INT8 via TFLite.** Best accuracy-speed tradeoff on Pi 4 without accelerator.

### Helmet Detection Strategy

Two-stage approach (more reliable than single-stage):

1. **Stage 1:** YOLOv8n detects `person`, `motorcycle`, `head` bounding boxes.
2. **Stage 2:** Lightweight binary classifier (MobileNetV3-Small, ~2MB INT8) on cropped head regions → `helmet` / `no_helmet`.

**Training data:** Use custom dataset combining:
- Safety Helmet Wearing Detection Dataset (Kaggle, ~5000 images)
- Self-collected Indian traffic images (500-1000 augmented)
- Augmentations: motion blur, brightness jitter, rain overlay, night simulation

### Traffic Signal and Lane Inference

**Traffic signal detection:**
- Detect traffic light bounding boxes via YOLO.
- Crop and classify color state with a tiny CNN (3-class: red/yellow/green) or HSV color analysis.
- HSV-based detection is actually more robust on Pi given the fixed color semantics. Use ML only as fallback.

**Wrong-side / divider jumping:**
- This is the hardest problem. Fully ML-based lane detection is expensive on Pi.
- **Practical approach:** Use GPS heading + road direction heuristic.
  - Maintain a local road direction cache (from OpenStreetMap offline tiles).
  - If GPS heading deviates >120° from expected road direction for >3 seconds → flag wrong-side.
  - Visual lane detection (ultra-lightweight UNet or rule-based edge detection) as supplementary signal only.

**Assumption stated:** Wrong-side detection will have lower accuracy (~70-80%) than helmet detection (~90%+). This is acceptable if flagged for cloud verification.

### Optimization Pipeline

```
PyTorch model (FP32)
    │
    ▼
Export to ONNX
    │
    ▼
Convert to TFLite (FP16 → INT8 quantization)
    │  Use representative dataset for calibration
    ▼
Deploy with TFLite Runtime on Pi
    (ARM NEON acceleration, 4 threads)
```

- **No TensorRT on Pi** (requires NVIDIA GPU). TFLite is the correct runtime here.
- INT8 quantization typically gives 2-3x speedup over FP32 with <2% mAP loss.
- Pruning: optional, marginal gains on already-nano models. Skip for v1.

---

## 3. Violation Detection Logic

### Rule Engine

```python
# Pseudocode for violation logic

VIOLATION_RULES = {
    "no_helmet": {
        "condition": lambda detections: (
            any(d.class == "motorcycle" for d in detections) and
            any(d.class == "person" and not has_helmet(d) for d in detections)
        ),
        "min_consecutive_frames": 3,
        "confidence_threshold": 0.85,
    },
    "red_light_jump": {
        "condition": lambda detections, signals: (
            any(s.state == "red" for s in signals) and
            vehicle_crossing_stop_line(detections)
        ),
        "min_consecutive_frames": 5,
        "confidence_threshold": 0.80,
    },
    "wrong_side": {
        "condition": lambda gps_heading, road_bearing: (
            abs(angle_diff(gps_heading, road_bearing)) > 120
        ),
        "min_duration_seconds": 3,
        "confidence_threshold": 0.70,
    },
}
```

### False Positive Mitigation

| Technique | Purpose |
|---|---|
| Temporal consistency (N consecutive frames) | Eliminates single-frame misdetections |
| Minimum object size filter | Ignores far-away / tiny detections |
| ROI masking | Process only center-lower portion of frame (road area) |
| Motion compensation via gyro/accel (optional IMU) | Reduces blur-induced errors |
| GPS speed gate | Suppress processing when stationary (no violations at 0 km/h) |
| Cooldown timer per violation type | Prevents duplicate reports for same event |

### Frame Sampling and Buffering

- Capture at 30fps, **process every 4th-6th frame** (effective 5-8 fps for inference).
- Maintain a **rolling 10-second circular buffer** of raw frames in memory (~150MB at 720p).
- On violation trigger: extract 5-second clip (2s before + 3s after) from buffer.
- Save best 3 frames (highest detection confidence) as JPEG evidence.

---

## 4. OCR and Plate Recognition

### Pipeline

```
Detected Vehicle Box
    │
    ▼
Plate Region Detector (YOLOv8n, separate tiny model or shared head)
    │
    ▼
Crop + Preprocessing
    │
    ├─ Grayscale conversion
    ├─ Adaptive thresholding (Gaussian)
    ├─ Deskew (Hough transform for rotation correction)
    ├─ Deblur (Wiener filter for motion blur, optional)
    └─ Resize to 320x64 normalized
    │
    ▼
OCR Engine
    │
    ▼
Post-processing (regex validation for Indian plate format)
```

### OCR Engine Selection

| Engine | Accuracy | Speed (Pi 4) | Notes |
|---|---|---|---|
| PaddleOCR-Lite | Good | ~200ms/plate | **Best for Indian plates**, supports Devanagari |
| EasyOCR | Good | ~500ms/plate | Heavier but good multilingual |
| Tesseract 5 | Moderate | ~300ms/plate | Needs heavy preprocessing |
| Custom CRNN (TFLite) | Best | ~100ms/plate | Requires training on Indian plates |

**Recommendation:** PaddleOCR-Lite for v1. Train custom CRNN for v2.

### Indian Plate Format Validation

```python
import re

INDIAN_PLATE_PATTERNS = [
    r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$',      # Standard: MH12AB1234
    r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$',     # Variations
    r'^\d{2}BH\d{4}[A-Z]{1,2}$',              # BH series
]

def validate_plate(text: str) -> bool:
    cleaned = text.replace(' ', '').replace('-', '').upper()
    return any(re.match(p, cleaned) for p in INDIAN_PLATE_PATTERNS)
```

### Night / Motion Blur Handling

- **Night:** Enable Pi Camera night mode (longer exposure via `libcamera` params), apply CLAHE histogram equalization on crops.
- **Motion blur:** At speeds >30 km/h, plate OCR accuracy drops significantly. Mitigation: trigger OCR only on frames where vehicle is relatively stationary in frame (optical flow check), or use burst capture (3 frames, pick sharpest via Laplacian variance).

**Tradeoff stated:** Plate OCR at night on a moving motorcycle will realistically achieve 50-60% accuracy. This is where cloud verification adds value. The system should still capture evidence even if OCR fails locally.

---

## 5. Agentic Workflow

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────┐
│                    STAGE 0: CAPTURE                      │
│  Camera → Frame buffer → GPS logger → Timestamp sync    │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                 STAGE 1: DETECTION                       │
│  YOLOv8n inference → helmet classifier → signal detect  │
│  Output: detection_result + confidence_score             │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              STAGE 2: RULE ENGINE                        │
│  Apply violation rules → temporal consistency check      │
│  Output: violation_candidate + edge_confidence           │
└─────────────────────┬───────────────────────────────────┘
                      │
              edge_confidence ≥ 0.96?
               /              \
             YES               NO (≥ 0.70)
              │                 │         \
              │                 │        < 0.70 → DISCARD
┌─────────────▼──┐  ┌──────────▼───────────────────────┐
│ STAGE 3a:      │  │ STAGE 3b: CLOUD VERIFICATION     │
│ LOCAL OCR +    │  │ Queue evidence packet             │
│ REPORT GEN     │  │ On connectivity:                  │
│                │  │   Send to GPT-4V / Gemini Vision  │
│                │  │   Prompt: "Is this a traffic       │
│                │  │   violation? Type? Plate number?"  │
│                │  │   Retry up to 3x with backoff      │
│                │  │   If API confirms ≥ 0.96 → Report │
│                │  │   Else → Discard                   │
└───────┬────────┘  └──────────┬───────────────────────┘
        │                      │
┌───────▼──────────────────────▼───────────────────────┐
│              STAGE 4: REPORT GENERATION               │
│  Compose evidence packet:                             │
│  - Best frame (JPEG, annotated)                       │
│  - 5-sec video clip (H.264)                           │
│  - Plate text + confidence                            │
│  - GPS coordinates + Google Maps link                 │
│  - Timestamp (IST)                                    │
│  - Violation type + confidence breakdown              │
│  Queue email to configured police address             │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│              STAGE 5: TRANSMISSION                    │
│  When WiFi/4G available:                              │
│  - Send queued emails via SMTP                        │
│  - Upload evidence to cloud storage (optional)        │
│  - Sync logs                                          │
│  Retry with exponential backoff (max 5 attempts)      │
└──────────────────────────────────────────────────────┘
```

### Fail-safes

- **Storage overflow:** If SD card >80% full, delete oldest non-violation footage. Never delete pending reports.
- **Thermal throttle:** Monitor CPU temp via `vcgencmd`. If >75°C, reduce inference to every 8th frame. If >80°C, pause inference for 30s.
- **GPS fix lost:** Continue detection, tag reports as "GPS unavailable." Use last known location + timestamp interpolation.
- **Camera disconnect:** Watchdog process restarts camera service within 5s.
- **Power loss:** Evidence buffer writes critical metadata to SQLite with WAL mode (crash-safe). Pending reports survive reboot.

---

## 6. Software Stack

### OS and Runtime

| Layer | Choice |
|---|---|
| OS | Raspberry Pi OS Lite (64-bit, Bookworm) |
| Python | 3.11 |
| Inference runtime | TFLite Runtime (ARM64 optimized) |
| Camera | Picamera2 (libcamera backend) |
| Video encoding | FFmpeg (hardware H.264 via V4L2 M2M) |
| GPS | gpsd + gps3 Python library |
| Database | SQLite3 (WAL mode) |
| Email | smtplib (stdlib) |
| Process management | systemd services |

### Key Python Packages

```
# requirements.txt
tflite-runtime        # Inference engine
picamera2             # Camera control
opencv-python-headless # Image processing (headless, no GUI deps)
numpy                 # Array ops
paddleocr             # Plate OCR (or easyocr)
gps3                  # GPS daemon interface
Pillow                # Image handling
jinja2                # Email template rendering
schedule              # Periodic tasks
psutil                # System monitoring
```

### Folder Structure

```
traffic-eye/
├── config/
│   ├── settings.yaml          # All configurable parameters
│   ├── violation_rules.yaml   # Rule definitions
│   └── email_template.html    # Report email template
├── models/
│   ├── yolov8n_int8.tflite    # Object detection
│   ├── helmet_cls_int8.tflite # Helmet classifier
│   ├── plate_det_int8.tflite  # Plate region detector
│   └── ocr/                   # OCR model files
├── src/
│   ├── main.py                # Entry point, orchestrator
│   ├── capture/
│   │   ├── camera.py          # Frame capture + buffer
│   │   └── gps.py             # GPS reader
│   ├── detection/
│   │   ├── detector.py        # YOLO inference wrapper
│   │   ├── helmet.py          # Helmet classifier
│   │   ├── signal.py          # Traffic light detection
│   │   └── tracker.py         # Simple IoU-based tracker
│   ├── violation/
│   │   ├── rules.py           # Rule engine
│   │   ├── temporal.py        # Temporal consistency
│   │   └── confidence.py      # Confidence aggregation
│   ├── ocr/
│   │   ├── plate_detect.py    # Plate region extraction
│   │   ├── plate_ocr.py       # OCR pipeline
│   │   └── validators.py      # Plate format validation
│   ├── reporting/
│   │   ├── evidence.py        # Evidence packaging
│   │   ├── report.py          # Report generation
│   │   └── sender.py          # Email/upload queue
│   ├── cloud/
│   │   ├── verifier.py        # GPT-4V / Gemini API calls
│   │   └── queue.py           # Offline queue manager
│   └── utils/
│       ├── thermal.py         # Temperature monitoring
│       ├── storage.py         # Disk management
│       └── logging_config.py  # Structured logging
├── data/
│   ├── evidence/              # Saved violation evidence
│   ├── queue/                 # Pending reports
│   └── logs/                  # Application logs
├── scripts/
│   ├── setup.sh               # Initial Pi setup
│   ├── train_helmet.py        # Helmet model training script
│   └── convert_model.py       # PyTorch → TFLite conversion
├── systemd/
│   ├── traffic-eye.service    # Main service
│   └── traffic-eye-sender.service  # Background email sender
├── tests/
└── README.md
```

---

## 7. Privacy, Legal, and Ethical Considerations

### Legal Context (India-specific)

- **Motor Vehicles Act, 2019:** Citizens can report traffic violations. Several Indian states (Karnataka, Kerala, Gujarat) have official portals/apps for citizen reporting.
- **IT Act, Section 43A:** Personal data must be handled with reasonable security.
- **No legal framework prohibits** capturing traffic violations in public spaces, but **distribution of footage** must be limited to authorities.

### Data Handling

| Concern | Mitigation |
|---|---|
| Face capture of bystanders | Blur all faces except the violator's head region (needed for helmet check). Apply face detection + Gaussian blur as post-processing before report generation. |
| Data retention | Auto-delete non-violation footage after 1 hour. Violation evidence retained for 30 days, then purged. Configurable in settings.yaml. |
| Storage encryption | Encrypt `/data/evidence/` directory with LUKS or fscrypt. |
| Transmission security | SMTP over TLS. Cloud API calls over HTTPS only. |
| Abuse prevention | Rate-limit reports: max 20 per hour. Require GPS data in every report (prevents fabricated reports from static footage). Log all system actions for audit. |
| False accusation risk | Always include confidence scores in reports. Frame as "potential violation for review," never as definitive accusation. |

### Ethical Tradeoffs

- **Surveillance concern:** This system records public roads continuously. The rolling buffer + auto-delete mitigates mass surveillance risk, but the operator should inform relevant authorities of its use.
- **Bias risk:** Detection models may perform unevenly across vehicle types, skin tones, or helmet styles. Test extensively across demographics before deployment.
- **Vigilantism risk:** System should only generate reports for official channels, not social media or public shaming.

---

## 8. Scalability and Improvements

### Mass Deployment Changes

| Aspect | Prototype | Scaled (v2) |
|---|---|---|
| Hardware | Pi 4 | Radxa Zero 3W or Pi Zero 2W (~₹1,500) + Coral USB TPU (~₹2,000) |
| Camera | Pi Camera v2 | Arducam IMX219 wide-angle (~₹400) |
| Connectivity | WiFi hotspot | 4G LTE HAT (SIM7600) for real-time upload |
| Power | USB power bank | Custom 18650 battery pack with BMS |
| Cost target | ₹4,000 | ₹2,000-2,500 per unit at 100+ volume |

### Cost-Down Strategies

- Replace Pi 4 with Pi Zero 2W (₹1,200) — sufficient if paired with Coral TPU for inference offload.
- Use compressed model formats (TFLite Micro) to reduce memory footprint.
- Bulk-purchase components from AliExpress/Taobao.
- 3D-print enclosures in batch (₹50/unit at scale).

### Battery Optimization

- Disable HDMI, Bluetooth, USB ports not in use (`dtoverlay` and `tvservice -o`).
- Reduce CPU governor to `powersave` when idle.
- Inference duty cycle: process frames only when GPS speed > 5 km/h.
- Estimated runtime: ~3-4 hours on 10000mAh at full load, ~6 hours with duty cycling.

### Future Extensions (v2+)

1. **Mobile companion app:** BLE/WiFi connection to phone for live preview, report review, GPS assist.
2. **Dashboard portal:** Web app for reviewing submitted violations, tracking status with police.
3. **V2X integration:** If India's V2X infrastructure matures, receive traffic signal phase data directly (eliminates visual signal detection).
4. **Fleet mode:** Multiple riders contributing to a shared violation database with deduplication.
5. **Model improvement loop:** Collect edge-case frames (low confidence detections) → retrain models monthly.
6. **Audio detection:** Add microphone for excessive honking detection (separate violation category in some cities).

---

## Key Tradeoffs and Honest Limitations

| Area | Reality Check |
|---|---|
| FPS on Pi 4 | Expect 4-6 fps for full pipeline. Not real-time video, but sufficient for violation detection at urban speeds. |
| Plate OCR at night | Realistically 40-60% accuracy without IR illumination. Consider adding a small IR LED array for ₹100. |
| Wrong-side detection | GPS-based heuristic will have false positives near U-turns, service roads, and unmapped areas. Expect ~75% accuracy. |
| Red-light detection | Requires the camera to capture both the signal AND the vehicle in the same frame. Mounting angle is critical — forward-facing, slightly upward tilt. |
| Thermal throttling | Pi 4 in an enclosed helmet mount WILL throttle in Indian summer (40°C+). A small heatsink + passive ventilation slots in the case are mandatory. |
| Legal acceptance | Police acceptance of citizen reports varies by state and officer. The system generates evidence; human follow-through is still required. |

---

## Implementation Sequence (Build Order for Claude Code)

| Phase | Tasks | Duration |
|---|---|---|
| **Phase 1** | Pi OS setup, camera/GPS integration, frame capture pipeline, circular buffer | 2-3 days |
| **Phase 2** | YOLOv8n conversion to TFLite INT8, inference wrapper, basic detection loop | 3-4 days |
| **Phase 3** | Helmet classifier training + deployment, violation rule engine | 3-4 days |
| **Phase 4** | OCR pipeline (PaddleOCR), plate validation, evidence packaging | 2-3 days |
| **Phase 5** | Report generation, email sender, offline queue | 2 days |
| **Phase 6** | Cloud verification integration (GPT-4V/Gemini), confidence pipeline | 2 days |
| **Phase 7** | Systemd services, thermal management, storage management, hardening | 2 days |
| **Phase 8** | Field testing, false positive tuning, threshold calibration | Ongoing |

When you're ready to start building in Claude Code, begin with Phase 1 — I'll generate the actual implementation files module by module.