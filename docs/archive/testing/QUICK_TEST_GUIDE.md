# Quick Test Guide - Traffic-Eye

**Quick reference for running validation tests**

---

## Quick Start (No Configuration Needed)

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Run integration tests
pytest tests/test_integration/ -v

# 3. Run E2E test (smoke test)
python scripts/test_end_to_end.py --skip-ocr

# Result: Should see "PASS" with 0 violations (expected with synthetic data)
```

**Expected Results:**
- Integration tests: 7 passed, 1 skipped
- E2E test: PASS, 6.7 FPS, 0 errors

---

## Full E2E Test (With Real Video)

```bash
# 1. Get or create test video
# Option A: Use your own video
cp /path/to/your/video.mp4 data/test_videos/

# Option B: Generate synthetic video
python scripts/test_end_to_end.py --create-video data/test_video.mp4

# 2. Run E2E test
python scripts/test_end_to_end.py --video data/test_videos/your_video.mp4 --skip-ocr

# 3. Check results
ls -lh data/evidence/test_reports/
```

---

## Test with Cloud OCR

```bash
# 1. Set API key (get from https://aistudio.google.com/app/apikey)
export TRAFFIC_EYE_CLOUD_API_KEY="your-gemini-api-key-here"

# 2. Run E2E test with OCR
python scripts/test_end_to_end.py --video data/test_videos/plate_video.mp4

# 3. Check OCR results in output
# Should see: "OCR success: MH12AB1234 (conf=0.92)"
```

---

## Test Individual Components

```bash
# Configuration
python -c "from src.config import load_config; print(load_config('config'))"

# YOLOv8 Detection
pytest tests/test_detection/test_detector.py -v

# Helmet Classifier
pytest tests/test_detection/test_helmet.py -v

# Rule Engine
pytest tests/test_violation/test_rules.py -v

# OCR (requires API key)
python scripts/test_vertex_ai.py

# Evidence Packaging
pytest tests/test_reporting/test_evidence.py -v

# Report Generation
pytest tests/test_reporting/test_report_template.py -v

# Database
pytest tests/test_database.py -v
```

---

## Test with Different Scenarios

```bash
# Scenario 1: Quick smoke test (synthetic frames)
python scripts/test_end_to_end.py --skip-ocr
# Time: ~9 seconds, Frames: 60

# Scenario 2: Full test with video (no OCR)
python scripts/test_end_to_end.py --video data/test_video.mp4 --skip-ocr
# Time: ~45 seconds, Frames: 300

# Scenario 3: Full test with OCR
export TRAFFIC_EYE_CLOUD_API_KEY="your-key"
python scripts/test_end_to_end.py --video data/test_videos/real_video.mp4
# Time: varies with video length + OCR calls

# Scenario 4: Performance benchmark
time python scripts/test_end_to_end.py --video data/test_video.mp4 --skip-ocr
# Measure FPS and memory usage
```

---

## Test Output Locations

```bash
# Test results
cat E2E_TEST_RESULTS_FINAL.md

# Generated reports
ls data/evidence/test_reports/
cat data/evidence/test_reports/{violation_id}.txt

# Evidence packages
ls data/evidence/*/
# Contains: frame_00.jpg, frame_01.jpg, frame_02.jpg, clip.mp4

# Database
sqlite3 data/test_traffic_eye.db "SELECT * FROM violations;"

# Logs
tail -f data/logs/traffic_eye.log
```

---

## Troubleshooting Tests

### No detections found
**Cause:** Using synthetic video (expected)
**Solution:** Use real video with motorcycles/people

### OCR test skipped
**Cause:** No API key set
**Solution:** `export TRAFFIC_EYE_CLOUD_API_KEY="your-key"`

### Model not found error
**Cause:** YOLOv8 model missing
**Solution:**
```bash
ls models/yolov8n_int8.tflite  # Check if exists
# If not, download or generate model
```

### Tests run slow (<3 FPS)
**Cause:** High CPU load or thermal throttling
**Solution:**
```bash
# Check CPU temp
vcgencmd measure_temp  # Raspberry Pi
# If >75°C, wait for cooling
# Or increase process_every_nth_frame in config
```

### Out of memory
**Cause:** Large video or long buffer
**Solution:**
```bash
# Use shorter video
# Or reduce buffer_seconds in config/settings.yaml
```

---

## Performance Expectations

### Development Machine (x86_64)
- **FPS:** 8-12 frames/second
- **Memory:** 300-400 MB
- **CPU:** 30-50%

### Raspberry Pi 4 (ARM)
- **FPS:** 6-7 frames/second
- **Memory:** 350-400 MB
- **CPU:** 60-80%

### Raspberry Pi 5 (ARM)
- **FPS:** 10-15 frames/second
- **Memory:** 300-350 MB
- **CPU:** 40-60%

---

## Test Status Indicators

### Integration Tests
```
✅ PASS - Test passed successfully
⏭️ SKIP - Test skipped (missing dependency)
❌ FAIL - Test failed (investigate)
```

### E2E Test Output
```
✓ Component initialized - Working correctly
⊗ Component skipped - Not tested (by design)
ERROR in component - Issue found (check logs)
```

### Final Status
```
PASS: Pipeline executed successfully - All good
FAIL: Critical component errors - Fix required
```

---

## Common Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
firefox htmlcov/index.html

# Run specific test file
pytest tests/test_integration/test_component_integration.py -v

# Run specific test class
pytest tests/test_integration/test_component_integration.py::TestDetectionIntegration -v

# Run specific test function
pytest tests/test_integration/test_component_integration.py::TestDetectionIntegration::test_detector_tracker_flow -v

# Run tests matching pattern
pytest -k "detection" -v

# Run with verbose output
pytest tests/ -vv

# Run and show print statements
pytest tests/ -s

# Run and stop on first failure
pytest tests/ -x

# Run in parallel (faster)
pytest tests/ -n auto
```

---

## Test Data Setup

### Required Test Videos
Place in `data/test_videos/`:

1. `helmet_violation.mp4` - Motorcycle rider without helmet
2. `helmet_violation_plate.mp4` - Same but with visible license plate
3. `no_violation.mp4` - Rider with helmet (negative test)
4. `multiple_vehicles.mp4` - Multiple objects for tracking test

### Test Video Requirements
- Duration: 10-30 seconds
- Resolution: 720p or higher
- Format: MP4, AVI, or MOV
- Content: Clear motorcycle/person visibility
- Lighting: Good quality, minimal blur

---

## Environment Setup

```bash
# Essential
export TRAFFIC_EYE_CLOUD_API_KEY="your-gemini-key"

# Optional (for email tests)
export TRAFFIC_EYE_EMAIL_PASSWORD="your-smtp-password"

# Check environment
env | grep TRAFFIC_EYE
```

---

## CI/CD Integration

```bash
# Add to .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
      - run: python scripts/test_end_to_end.py --skip-ocr
```

---

## Quick Validation Checklist

Before deployment, verify:

- [ ] `pytest tests/test_integration/ -v` → 7 passed
- [ ] `python scripts/test_end_to_end.py --skip-ocr` → PASS
- [ ] Models exist: `ls models/*.tflite` → 2 files
- [ ] Config valid: `python -m src.config` → No errors
- [ ] Database works: `sqlite3 data/test_traffic_eye.db .tables` → Shows tables
- [ ] OCR configured: `echo $TRAFFIC_EYE_CLOUD_API_KEY` → Shows key
- [ ] Test video available: `ls data/test_videos/*.mp4` → At least 1 file

---

## Getting Help

1. **Check test results:**
   ```bash
   cat E2E_TEST_RESULTS_FINAL.md
   cat docs/INTEGRATION_ISSUES.md
   ```

2. **Review logs:**
   ```bash
   tail -f data/logs/traffic_eye.log
   ```

3. **Check documentation:**
   ```bash
   cat scripts/README_E2E_TESTING.md
   cat docs/E2E_VALIDATION_REPORT.md
   ```

4. **Verify environment:**
   ```bash
   python --version  # Should be 3.9+
   pip list | grep -E "opencv|numpy|tensorflow|tflite"
   ```

---

**Last Updated:** 2026-02-09
**Version:** 1.0
