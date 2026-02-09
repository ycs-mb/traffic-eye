# 🤖 Agent Team Prompts for Traffic-Eye Project

**Project Status**: 75-80% Complete
**Total Modules**: 9 (capture, cloud, detection, ocr, reporting, utils, violation)
**Source Files**: 36 Python files
**Test Files**: 27 test files
**Platform**: Raspberry Pi 4 (edge AI deployment)

---

## 📊 **Current Status Analysis**

### ✅ **Completed (Production Ready)**
- Core detection pipeline (YOLOv8n)
- Object tracking (IoU tracker)
- Frame buffering (circular buffer)
- Cloud OCR (Gemini API - 100% tested ✅)
- Cloud verification (Gemini, OpenAI, Vertex AI)
- Reporting system (evidence packaging, email sender)
- Configuration system (YAML-based)
- Deployment scripts (systemd, setup.sh)
- Testing infrastructure (pytest, 138 tests)

### ⚠️ **Partially Complete (Needs Work)**
- Helmet detection (classifier stub exists, model missing)
- Traffic signal detection (HSV-based, needs testing)
- Violation rules (framework ready, logic incomplete)
- OCR pipeline (PaddleOCR installed but not integrated)

### ❌ **Not Started**
- Red light jump detection (rule logic)
- Wrong-side driving detection (GPS-based)
- Field testing on Raspberry Pi hardware
- Performance benchmarking
- Integration testing (end-to-end)
- Monitoring & alerting

---

## 🎯 **Recommended Agent Team Strategies**

---

## **STRATEGY 1: Complete MVP for Field Testing** (Highest Priority)

**Goal**: Get a working system ready for real-world testing on Raspberry Pi

**Timeline**: 2-3 days with 4 agents in parallel

### **Prompt:**

```
I need to complete the traffic-eye MVP for field testing on Raspberry Pi 4.
Launch 4 agents working in parallel:

1. Agent "Helmet-ML-Engineer" (@software-engineer + @raspberry-pi-expert):
   Task: Complete helmet detection end-to-end
   - Download Indian helmet detection dataset (Kaggle recommended in models/README.md)
   - Train MobileNetV3-Small helmet classifier using scripts/train_helmet.py
   - Convert trained model to TFLite INT8 using scripts/convert_model.py
   - Test helmet classifier on sample images
   - Integrate into src/detection/helmet.py (replace mock implementation)
   - Benchmark inference time on Pi 4 (target: <50ms)
   - Document model accuracy and limitations
   Target: Deployable helmet_cls_int8.tflite with >85% accuracy

2. Agent "Violation-Logic-Engineer" (@software-engineer):
   Task: Complete violation detection rules
   - Implement red_light_jump rule in src/violation/rules.py:
     * Detect traffic light state (use src/detection/signal.py)
     * Track vehicle position crossing stop line
     * Require 5 consecutive frames for confirmation
   - Implement wrong_side_driving rule (GPS-based):
     * Calculate GPS heading vs expected road direction
     * Use 120° deviation threshold for 3+ seconds
     * Handle edge cases (U-turns, unmapped roads)
   - Update config/violation_rules.yaml with rule parameters
   - Write comprehensive tests in tests/test_violation/
   - Document accuracy expectations per violation type
   Target: All 3 violation types (helmet, red-light, wrong-side) working

3. Agent "Integration-Tester" (@software-engineer + @raspberry-pi-expert):
   Task: End-to-end integration testing
   - Create test dataset with sample traffic footage
   - Test full pipeline: detection → violation → OCR → reporting
   - Verify Gemini Cloud OCR integration works in main app
   - Test email sending with real SMTP credentials
   - Test evidence packaging (frames + video clips)
   - Create integration tests in tests/test_integration/
   - Document test scenarios and expected results
   - Fix any integration bugs found
   Target: Working end-to-end pipeline with sample footage

4. Agent "Pi-Deployment-Expert" (@raspberry-pi-expert):
   Task: Prepare for Pi hardware deployment
   - Complete scripts/setup.sh for Pi OS Lite installation
   - Test deployment on fresh Pi OS (document all steps)
   - Configure camera interface (picamera2) and test
   - Set up GPS module (NEO-6M via UART) and test
   - Benchmark performance on Pi 4:
     * Measure actual FPS with YOLOv8n
     * Measure memory usage
     * Measure CPU temperature under load
     * Test thermal throttling at 75°C and 80°C
   - Create deployment checklist and troubleshooting guide
   - Set up monitoring (health_check.sh running via cron)
   Target: One-command Pi deployment that works reliably

After all agents complete:
- Run full integration test on Pi hardware
- Validate all 3 violation types work
- Verify email reporting works
- Document known issues and limitations

Status: Ready for real-world field testing
```

---

## **STRATEGY 2: Production Hardening** (After MVP works)

**Goal**: Make the system production-ready, reliable, and maintainable

**Timeline**: 3-4 days with 5 agents in parallel

### **Prompt:**

```
Harden the traffic-eye system for production deployment.
Launch 5 agents in parallel:

1. Agent "Performance-Optimizer" (@software-engineer + @raspberry-pi-expert):
   Task: Optimize for Raspberry Pi 4 performance
   - Profile CPU/memory usage with cProfile and memory_profiler
   - Identify bottlenecks in detection pipeline
   - Optimize frame processing (reduce memory copies)
   - Tune YOLOv8n inference (num_threads, batch_size)
   - Implement frame skipping based on CPU load
   - Test duty cycling (only process when GPS speed > 5 km/h)
   - Benchmark before/after improvements
   - Document performance tuning guide
   Target: Achieve 5-6 fps stable on Pi 4, <500MB RAM

2. Agent "Reliability-Engineer" (@raspberry-pi-expert):
   Task: Build reliability and error recovery
   - Implement watchdog for camera disconnects
   - Implement watchdog for GPS fix loss
   - Add SQLite database health checks and auto-repair
   - Implement graceful degradation (continue without GPS if lost)
   - Add circuit breakers for cloud API failures
   - Test power-loss scenarios (validate WAL mode recovery)
   - Add systemd watchdog heartbeat (sd_notify)
   - Create recovery procedures for common failures
   Target: System survives hardware failures gracefully

3. Agent "Monitoring-Dashboard-Builder" (@software-engineer + @raspberry-pi-expert):
   Task: Create monitoring and alerting system
   - Enhance scripts/health_check.sh with comprehensive checks:
     * CPU temperature, throttling status
     * Disk usage, evidence storage
     * Service status, crash detection
     * API quota usage (Gemini free tier)
     * Detection FPS, violation rate
   - Create Prometheus metrics exporter (optional)
   - Set up email alerts for critical issues
   - Create simple web dashboard (Flask) showing:
     * System status, recent violations
     * Performance metrics, error logs
   - Add log rotation with log2ram
   Target: Real-time monitoring with automatic alerts

4. Agent "Security-Hardener" (@software-engineer):
   Task: Security hardening and compliance
   - Audit code for vulnerabilities (SQL injection, path traversal, XSS)
   - Implement face blurring for privacy (all faces except violator)
   - Add data encryption for /data/evidence (fscrypt or LUKS)
   - Implement data retention policies (auto-delete after 30 days)
   - Set up UFW firewall rules
   - Configure fail2ban for SSH protection
   - Add API key rotation mechanism
   - Document privacy safeguards and GDPR compliance
   Target: Production-grade security and privacy

5. Agent "Documentation-Writer" (@software-engineer):
   Task: Complete documentation
   - Write deployment guide (docs/DEPLOYMENT.md):
     * Hardware setup, BOM with purchase links
     * Pi OS installation, initial configuration
     * Camera/GPS wiring diagrams
     * Step-by-step deployment instructions
   - Write operations guide (docs/OPERATIONS.md):
     * How to monitor the system
     * How to review violations
     * How to troubleshoot common issues
   - Write API documentation (docstrings → Sphinx)
   - Create FAQ for common questions
   - Record video tutorial for deployment
   Target: Complete documentation for operators

Coordination: After all complete, test hardened system end-to-end
```

---

## **STRATEGY 3: Advanced Features** (Future Enhancements)

**Goal**: Add advanced capabilities beyond MVP

**Timeline**: 4-5 days with 6 agents

### **Prompt:**

```
Implement advanced features for traffic-eye v2.
Launch 6 agents in parallel:

1. Agent "Plate-Detection-Engineer" (@software-engineer):
   Task: Implement dedicated plate detection model
   - Research lightweight plate detection models (YOLO-tiny, MobileNet-SSD)
   - Train on Indian license plate dataset
   - Convert to TFLite INT8 (<5MB)
   - Integrate into src/ocr/plate_detect.py
   - Replace current bounding box heuristic
   - Benchmark accuracy and speed
   Target: Dedicated plate detector >90% recall

2. Agent "Multi-Frame-OCR-Engineer" (@software-engineer):
   Task: Implement multi-frame OCR fusion
   - Extract plate text from 3 best frames (not just 1)
   - Implement voting/consensus algorithm:
     * If 2+ frames agree → high confidence
     * If all 3 different → send to cloud
   - Reduce cloud API calls by 60-70%
   - Add plate text validation (regex + checksum)
   - Test with motion blur and night footage
   Target: Reduce cloud API costs by 70%

3. Agent "Night-Vision-Engineer" (@raspberry-pi-expert):
   Task: Optimize for night/low-light conditions
   - Configure Pi Camera night mode (long exposure via libcamera)
   - Implement CLAHE histogram equalization for plates
   - Add IR LED control via GPIO (optional hardware)
   - Test with night footage dataset
   - Tune detection thresholds for low-light
   - Document accuracy degradation at night
   Target: 60%+ plate OCR accuracy at night

4. Agent "Mobile-App-Developer" (@software-engineer):
   Task: Create mobile companion app
   - Build Flutter/React Native app for:
     * Live system status monitoring
     * View recent violations
     * Review and approve violations before sending
     * Manual violation reporting
     * GPS streaming to Pi (network GPS)
   - BLE/WiFi connection to Pi
   - Implement secure authentication
   Target: Working mobile app for iOS/Android

5. Agent "Cloud-Dashboard-Builder" (@software-engineer):
   Task: Build web dashboard for violation management
   - Create FastAPI backend:
     * Violation database access
     * Evidence file serving
     * Status tracking API
   - Create React frontend:
     * Violation gallery with filtering
     * Map view of violations
     * Statistics and analytics
     * Export reports (PDF/CSV)
   - Deploy with nginx reverse proxy
   Target: Professional web dashboard

6. Agent "ML-Training-Pipeline" (@software-engineer):
   Task: Create automated model retraining pipeline
   - Collect edge cases (low confidence detections)
   - Implement active learning:
     * Flag uncertain detections for manual review
     * Retrain models monthly with new data
   - Create dataset versioning (DVC)
   - Automate model conversion (PyTorch → TFLite)
   - Implement A/B testing for new models
   Target: Self-improving detection system
```

---

## **STRATEGY 4: Scale to Fleet Deployment** (Multi-Device)

**Goal**: Support multiple devices, shared database, deduplication

**Timeline**: 3-4 days with 4 agents

### **Prompt:**

```
Prepare traffic-eye for fleet deployment (multiple riders/devices).
Launch 4 agents in parallel:

1. Agent "Fleet-Architecture-Designer" (@software-engineer):
   Task: Design fleet architecture
   - Design centralized violation database (PostgreSQL)
   - Implement deduplication:
     * Same violation from multiple riders (time + location)
     * Same plate detected multiple times
   - Design device registration and management
   - Create multi-tenant configuration
   - Document fleet deployment architecture
   Target: Architecture for 10-100 devices

2. Agent "Edge-Sync-Engineer" (@software-engineer):
   Task: Implement edge-to-cloud synchronization
   - Create background sync service:
     * Queue violations locally
     * Sync to central server when online
     * Handle conflict resolution
   - Implement delta sync (only send changes)
   - Add bandwidth optimization (compress evidence)
   - Handle offline operation (7-day buffer)
   Target: Reliable offline-first sync

3. Agent "Central-API-Builder" (@software-engineer):
   Task: Build central management API
   - Create FastAPI server:
     * Device registration
     * Violation ingestion
     * Evidence storage (S3/MinIO)
     * Deduplication logic
     * Status dashboard API
   - Implement authentication (JWT)
   - Add rate limiting and quotas
   - Document API endpoints
   Target: Production-ready central API

4. Agent "Fleet-Monitoring" (@software-engineer):
   Task: Build fleet monitoring dashboard
   - Create admin dashboard:
     * Map view of all devices
     * Device health status
     * Violation heatmap
     * Performance metrics per device
     * Alert management
   - Implement real-time updates (WebSocket)
   - Add device remote control (restart, config update)
   Target: Central monitoring for fleet
```

---

## **STRATEGY 5: Testing & Quality Assurance**

**Goal**: Comprehensive testing and quality validation

**Timeline**: 2-3 days with 3 agents

### **Prompt:**

```
Build comprehensive testing and QA for traffic-eye.
Launch 3 agents in parallel:

1. Agent "Test-Suite-Builder" (@software-engineer):
   Task: Expand test coverage to 90%+
   - Write unit tests for all modules (currently 138 tests)
   - Add integration tests (end-to-end scenarios)
   - Add performance tests (benchmark critical paths)
   - Add regression tests (prevent bugs from returning)
   - Test edge cases:
     * Camera disconnect during recording
     * GPS signal loss
     * Disk full scenarios
     * Network unavailable
     * API rate limiting
   - Use pytest fixtures for test data
   - Achieve 90%+ code coverage
   Target: 300+ tests with 90% coverage

2. Agent "Field-Test-Coordinator" (@raspberry-pi-expert):
   Task: Organize and execute field testing
   - Create field testing protocol:
     * Test scenarios (day/night, moving/stationary)
     * Evaluation criteria
     * Data collection procedure
   - Test with real traffic footage (10+ hours)
   - Measure accuracy per violation type:
     * True positives, false positives, false negatives
     * Precision, recall, F1 score
   - Test with different lighting conditions
   - Test battery life (10000mAh power bank)
   - Document all findings and issues
   Target: Complete field test report

3. Agent "Performance-Validator" (@raspberry-pi-expert):
   Task: Validate performance requirements
   - Benchmark on Pi 4:
     * Measure FPS (target: 4-6 fps)
     * Measure memory usage (target: <500MB)
     * Measure CPU usage (target: <90%)
     * Measure inference time per frame
   - Stress test under load:
     * 8-hour continuous operation
     * High traffic density (20+ vehicles/frame)
     * Thermal throttling behavior
   - Validate battery life:
     * Full load: 3-4 hours
     * Duty cycle: 5-6 hours
   - Create performance report
   Target: Validated performance metrics
```

---

## 🎯 **RECOMMENDED FIRST ACTION**

### **Quick Win: Complete Helmet Detection + Integration Test**

**Most Important Right Now**: Get helmet detection working end-to-end

```
Launch 2 agents in parallel for quick validation:

1. Agent "Helmet-Quick-Deploy" (@raspberry-pi-expert):
   - Find and download pre-trained helmet detection model (RoboFlow, Kaggle)
   - Convert to TFLite INT8 format
   - Test on 10 sample images
   - Deploy to models/helmet_cls_int8.tflite
   - Verify >80% accuracy
   Target: Working helmet model in 2 hours

2. Agent "End-to-End-Validator" (@software-engineer):
   - Create test script that runs full pipeline:
     * Load video with helmet violations
     * Run detection → helmet classifier → violation detection
     * Generate evidence package
     * Send to Gemini Cloud OCR
     * Create email report
   - Verify all components work together
   - Document any integration issues
   Target: Validated end-to-end flow in 2 hours

After both complete: You'll know if the system actually works!
```

---

## 📊 **Agent Team Decision Matrix**

| Goal | Strategy | Agents | Timeline | Priority |
|------|----------|--------|----------|----------|
| **Get to MVP** | Strategy 1 | 4 agents | 2-3 days | 🔴 Critical |
| **Quick validation** | Quick Win | 2 agents | 2 hours | 🔴 Critical |
| **Production ready** | Strategy 2 | 5 agents | 3-4 days | 🟡 High |
| **Advanced features** | Strategy 3 | 6 agents | 4-5 days | 🟢 Medium |
| **Fleet deployment** | Strategy 4 | 4 agents | 3-4 days | 🟢 Medium |
| **Testing & QA** | Strategy 5 | 3 agents | 2-3 days | 🟡 High |

---

## 🚀 **Suggested Execution Order**

### **Phase 1: Validation** (Today - 2 hours)
Run **Quick Win** prompt to validate helmet detection works

### **Phase 2: MVP** (This week - 2-3 days)
Run **Strategy 1** to complete MVP for field testing

### **Phase 3: Hardening** (Next week - 3-4 days)
Run **Strategy 2** for production hardening

### **Phase 4: Enhancement** (Future - as needed)
Run **Strategy 3**, **4**, or **5** based on requirements

---

## 💡 **Tips for Using These Prompts**

1. **Start with Quick Win**: Validates the system works before investing more time

2. **Parallel Execution**: All strategies are designed for parallel agent work
   - Agents work independently
   - Minimal coordination needed
   - Can resume if one fails

3. **Skills Integration**: Each prompt specifies which skills to use:
   - `@software-engineer` - Code quality, testing, architecture
   - `@raspberry-pi-expert` - Pi hardware, deployment, optimization

4. **Incremental Progress**: Each agent has a clear deliverable
   - Can measure progress independently
   - Can validate each agent's work separately

5. **Dependency Aware**: Prompts indicate when sequential work is needed
   - Most work is parallel
   - Coordination steps clearly marked

---

## 📁 **Expected Deliverables Per Strategy**

### **Strategy 1 (MVP):**
- `models/helmet_cls_int8.tflite` (trained model)
- Updated `src/violation/rules.py` (complete rule logic)
- `tests/test_integration/` (integration test suite)
- Deployment checklist and troubleshooting guide
- Performance benchmark report

### **Strategy 2 (Production):**
- Performance optimization report (before/after metrics)
- Enhanced `scripts/health_check.sh` with alerts
- Web dashboard (Flask app)
- Security audit report
- Complete operator documentation

### **Strategy 3 (Advanced):**
- Plate detection model (<5MB TFLite)
- Multi-frame OCR fusion algorithm
- Night vision optimizations
- Mobile app (iOS/Android)
- Cloud dashboard (React + FastAPI)
- ML retraining pipeline

---

## ✅ **Ready to Execute?**

All prompts are ready to use. Just:
1. Copy the prompt you want
2. Paste into Claude Code
3. Let the agents work in parallel
4. Review results when complete

**Recommended starting point**: Quick Win (2 hours) → Strategy 1 (MVP)

---

**Total Project Completion Estimate**:
- Quick Win: 2 hours
- MVP (Strategy 1): 2-3 days
- Production Ready (Strategy 2): +3-4 days
- **Total to Production: ~1 week** with agent teams

Without agent teams: ~3-4 weeks (75% time savings!)

---

*Generated: 2026-02-09*
*For: Traffic-Eye Edge AI Project*
*Status: 75-80% Complete*
