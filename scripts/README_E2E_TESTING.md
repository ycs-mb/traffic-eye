# End-to-End Testing Guide

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Basic E2E test (no OCR, synthetic frames)
python scripts/test_end_to_end.py --skip-ocr

# With real video
python scripts/test_end_to_end.py --video path/to/video.mp4

# With OCR validation (requires API key)
export TRAFFIC_EYE_CLOUD_API_KEY="your-gemini-api-key"
python scripts/test_end_to_end.py --video path/to/video.mp4

# Create synthetic test video
python scripts/test_end_to_end.py --create-video data/test_video.mp4
```

## Test Script: `test_end_to_end.py`

### What It Tests

1. **Frame Processing**
   - Video loading or synthetic frame generation
   - Circular buffer management (10 second window)
   - Frame rate processing (configurable)

2. **Detection Pipeline**
   - YOLOv8n TFLite inference
   - Object tracking (IOU tracker)
   - Person and vehicle detection
   - Target class filtering

3. **Violation Detection**
   - Helmet classification (mock or real)
   - Rule engine execution
   - Temporal consistency (3+ consecutive frames)
   - Speed gate enforcement (GPS-based)

4. **Evidence Processing**
   - Best frame selection
   - Frame annotation (bboxes, metadata)
   - Video clip generation (H.264 MP4)
   - File hashing (SHA256)

5. **Cloud Services**
   - Gemini OCR (license plate reading)
   - Plate validation (Indian format)
   - Error correction

6. **Reporting**
   - Report generation (HTML + text)
   - Email template rendering
   - Attachment handling

### Command Line Options

```
--video PATH        Path to test video file
--api-key KEY       Gemini API key (or use env var)
--skip-ocr          Skip OCR testing
--create-video PATH Create test video and exit
--config DIR        Config directory (default: config)
```

### Output

The script generates:
- Console output with progress and metrics
- Test summary with performance stats
- Error log (if any issues)
- Evidence packages in `data/evidence/`
- Reports in `data/evidence/test_reports/`

### Success Criteria

Test passes if:
1. All frames processed without errors
2. Components initialize successfully
3. No critical component failures
4. Pipeline executes end-to-end

Test may pass even with:
- No violations detected (depends on input)
- OCR skipped (if no API key)
- Mock helmet classifier used

## Integration Tests: `tests/test_integration/`

### Running Tests

```bash
# All integration tests
pytest tests/test_integration/ -v

# Specific test
pytest tests/test_integration/test_component_integration.py::TestDetectionIntegration -v

# With coverage report
pytest tests/test_integration/ --cov=src --cov-report=html

# Run only tests that don't require API key
pytest tests/test_integration/ -v -m "not requires_api_key"
```

### Test Classes

1. **TestDetectionIntegration**
   - Detector + tracker interaction
   - Detection output format validation

2. **TestBufferIntegration**
   - Frame storage and retrieval
   - Circular buffer behavior
   - Clip extraction

3. **TestRuleEngineIntegration**
   - Rule evaluation with detections
   - Temporal consistency
   - Violation candidate generation

4. **TestEvidencePackaging**
   - Evidence packet creation
   - Frame selection and encoding
   - Video clip generation
   - Database persistence

5. **TestReportGeneration**
   - Report rendering from evidence
   - Template processing
   - Attachment handling

6. **TestOCRIntegration** (requires API key)
   - Gemini OCR with plate images
   - Plate validation
   - Error handling

7. **TestConfigLoading**
   - Configuration parsing
   - Validation

8. **TestDatabaseIntegration**
   - Violation record storage
   - Evidence file tracking

## Test Data Requirements

### For Real Testing

Need a test video with:
- **Duration:** 10-30 seconds
- **Content:** Motorcycle with rider
- **Violation:** Rider without helmet (clear)
- **License Plate:** Visible and readable
- **Quality:** Good lighting, minimal blur
- **Format:** MP4, AVI, or MOV

### Creating Test Videos

**Option 1: Use test video creation tool**
```bash
python scripts/test_end_to_end.py --create-video data/test_videos/synthetic.mp4
```
Creates a simple animated test video (but won't trigger real detections)

**Option 2: Record real video**
- Use phone or camera
- Follow requirements above
- Place in `data/test_videos/`

**Option 3: Use public datasets**
- Traffic surveillance datasets
- Dashcam footage
- YouTube videos (with appropriate license)

## Environment Setup

### Required Environment Variables

```bash
# For OCR testing
export TRAFFIC_EYE_CLOUD_API_KEY="your-gemini-api-key"

# For email testing (optional)
export TRAFFIC_EYE_EMAIL_PASSWORD="your-smtp-password"
```

### Configuration

Edit `config/settings.yaml`:

```yaml
# For testing, you may want to adjust:
camera:
  process_every_nth_frame: 5  # Process every 5th frame (faster testing)

detection:
  confidence_threshold: 0.3  # Lower for more detections in test

violations:
  max_reports_per_hour: 100  # High limit for testing

gps:
  speed_gate_kmh: 0  # Disable speed gate for testing
```

## Troubleshooting

### No Detections Found

**Problem:** Test runs but finds 0 detections

**Causes:**
- Using synthetic frames (expected)
- Video doesn't contain target objects
- Confidence threshold too high
- Model not detecting objects in video

**Solutions:**
1. Use real video with motorcycles/people
2. Lower confidence threshold in config
3. Check video quality and content
4. Verify model is loaded correctly

### OCR Failures

**Problem:** OCR returns None or low confidence

**Causes:**
- API key not set
- Network issues
- Plate not visible in frame
- Poor image quality

**Solutions:**
1. Verify API key: `echo $TRAFFIC_EYE_CLOUD_API_KEY`
2. Check network connectivity
3. Use video with clear license plates
4. Test OCR separately: `python scripts/test_vertex_ai.py`

### Performance Issues

**Problem:** Very slow processing (<1 FPS)

**Causes:**
- High resolution video
- CPU-bound detection
- Swap usage
- Too many threads

**Solutions:**
1. Reduce video resolution
2. Increase `process_every_nth_frame`
3. Reduce `num_threads` (try 2)
4. Check CPU temperature (thermal throttling)

### Memory Errors

**Problem:** Out of memory / killed

**Causes:**
- Large video file
- Long buffer window
- Memory leak

**Solutions:**
1. Use shorter video clip
2. Reduce `buffer_seconds` in config
3. Reduce frame resolution
4. Monitor with: `watch -n 1 free -h`

## Performance Expectations

### Development Machine
- **FPS:** 3-5 frames/second
- **Latency:** ~300ms per frame
- **Memory:** ~200-300 MB

### Raspberry Pi 4 (4GB)
- **FPS:** 2-4 frames/second
- **Latency:** ~400-600ms per frame
- **Memory:** ~250-400 MB

### Raspberry Pi 5
- **FPS:** 4-6 frames/second
- **Latency:** ~200-400ms per frame
- **Memory:** ~200-350 MB

### Optimization Tips

1. **Increase frame skip:**
   ```yaml
   camera:
     process_every_nth_frame: 10  # Process every 10th frame
   ```

2. **Use smaller model input:**
   - Current: 320x320
   - Could export 256x256 or 192x192 version

3. **Reduce threads on overheating:**
   ```yaml
   detection:
     num_threads: 2  # Less parallel work
   ```

4. **Enable thermal throttling:**
   ```yaml
   thermal:
     throttle_temp_c: 70  # Start skipping more frames
     pause_temp_c: 75     # Pause processing
   ```

## Next Steps After Testing

1. **Successful Test Results**
   - Document test video details
   - Save test artifacts
   - Review performance metrics
   - Plan deployment

2. **Failed Tests**
   - Review error logs
   - Check component status
   - Verify dependencies
   - Update test report

3. **Field Deployment**
   - Run extended tests (hours)
   - Test thermal behavior
   - Validate GPS integration
   - Test email delivery

4. **Production Readiness**
   - Replace mock helmet classifier
   - Configure real SMTP
   - Set up monitoring
   - Create runbook

## Contact & Support

For issues or questions:
1. Check logs in `data/logs/`
2. Review this guide and main README
3. Check component documentation in `src/*/README.md`
4. Review integration test report: `docs/INTEGRATION_TEST_REPORT.md`

---

**Last Updated:** 2026-02-09
**Version:** 1.0
