# Traffic-Eye Documentation

Complete documentation for the Traffic-Eye violation detection system.

---

## 📚 Current Documentation

### **Field Testing** (`field-testing/`)

Everything you need for field deployment and testing:

| Document | Purpose |
|----------|---------|
| **[FIELD_DEPLOYMENT_COMPLETE.md](field-testing/FIELD_DEPLOYMENT_COMPLETE.md)** | Complete deployment guide (14KB) |
| **[FIELD_QUICK_REFERENCE.md](field-testing/FIELD_QUICK_REFERENCE.md)** | Printable quick reference card |
| **[FIELD_TESTING_CHECKLIST.md](field-testing/FIELD_TESTING_CHECKLIST.md)** | Pre-flight and testing checklist |
| **[DEPLOYMENT_ARCHITECTURE.md](field-testing/DEPLOYMENT_ARCHITECTURE.md)** | System architecture diagrams |
| **[INSTALL_FIELD_TESTING.txt](field-testing/INSTALL_FIELD_TESTING.txt)** | Quick installation summary |

**Quick Start**: Read `INSTALL_FIELD_TESTING.txt` first, then follow `FIELD_DEPLOYMENT_COMPLETE.md`

---

## 📦 Archive (`archive/`)

Historical documentation from development and setup phases:

### **Setup Documentation** (`archive/setup/`)
- `CLOUD_OCR_SETUP_COMPLETE.md` - Initial cloud OCR setup
- `GEMINI_OCR_COMPLETE.md` - Gemini API configuration and testing
- `VERTEX_AI_CONFIGURED.md` - Vertex AI setup (not used)
- `CAMERA_DEPLOYMENT.md` - USB webcam deployment summary
- `POWER_SUPPLY_GUIDE.md` - Hardware power supply guide
- `USB_WEBCAM_SETUP_COMPLETE.md` - USB webcam setup confirmation
- `WEBCAM_MIGRATION.md` - Migration from Pi Camera to USB webcam

### **Testing Documentation** (`archive/testing/`)
- `E2E_TEST_RESULTS_FINAL.md` - End-to-end test results
- `INTEGRATION_TEST_RESULTS.md` - Integration test results
- `QUICK_TEST_GUIDE.md` - Quick testing guide

### **Reports** (`archive/reports/`)
- `HELMET_PIPELINE_REPORT.md` - Helmet detection pipeline development
- `REPORTING_CHECKLIST.md` - Reporting system checklist
- `REPORTING_IMPLEMENTATION.md` - Reporting implementation details
- `REPORTING_SUMMARY.md` - Reporting system summary
- `DEPLOYMENT_STATUS.md` - Current deployment status report
- `DEPLOYMENT_SUMMARY.md` - Overall deployment summary
- `DASHBOARD_FIXES.md` - Dashboard bug fixes log
- `DASHBOARD_UPGRADE.md` - Mission control dashboard upgrade report

### **Planning** (`archive/planning/`)
- `AGENT_TEAM_PROMPTS.md` - Agent team development strategies
- `project.md` - Original project description

---

## 🚀 Quick Navigation

### **New to the Project?**
1. Start with [../README.md](../README.md) (project overview)
2. Read [field-testing/INSTALL_FIELD_TESTING.txt](field-testing/INSTALL_FIELD_TESTING.txt) (quick start)
3. Follow [field-testing/FIELD_DEPLOYMENT_COMPLETE.md](field-testing/FIELD_DEPLOYMENT_COMPLETE.md) (complete guide)

### **Ready for Field Testing?**
1. Print [field-testing/FIELD_QUICK_REFERENCE.md](field-testing/FIELD_QUICK_REFERENCE.md) (keep in car)
2. Use [field-testing/FIELD_TESTING_CHECKLIST.md](field-testing/FIELD_TESTING_CHECKLIST.md) (pre-flight)
3. Deploy with `bash scripts/deploy_field_testing.sh`

### **Need Technical Details?**
1. Architecture: [field-testing/DEPLOYMENT_ARCHITECTURE.md](field-testing/DEPLOYMENT_ARCHITECTURE.md)
2. Setup history: [archive/setup/](archive/setup/)
3. Test results: [archive/testing/](archive/testing/)

---

## 📂 Project Structure

```
/home/yashcs/traffic-eye/
├── README.md                    # Main project README
├── docs/                        # Documentation (you are here)
│   ├── README.md                # This file
│   ├── field-testing/           # Current field testing docs
│   │   ├── FIELD_DEPLOYMENT_COMPLETE.md
│   │   ├── FIELD_QUICK_REFERENCE.md
│   │   ├── FIELD_TESTING_CHECKLIST.md
│   │   ├── DEPLOYMENT_ARCHITECTURE.md
│   │   └── INSTALL_FIELD_TESTING.txt
│   └── archive/                 # Historical documentation
│       ├── setup/               # Setup and configuration
│       ├── testing/             # Test results and guides
│       ├── reports/             # Feature reports
│       └── planning/            # Planning documents
├── src/                         # Source code
├── scripts/                     # Deployment and utility scripts
├── config/                      # Configuration files
├── models/                      # ML models
└── systemd/                     # Service files
```

---

## 🔄 Documentation Updates

**Last Updated**: 2026-02-10

### Recent Changes
- ✅ Created organized docs/ structure
- ✅ Moved field testing documentation to docs/field-testing/
- ✅ Archived historical documentation to docs/archive/
- ✅ Updated archive with dashboard and webcam deployment docs (2026-02-10)
- ✅ Created this README as documentation index

### Maintenance
- Archive old documentation when superseded
- Keep field-testing/ folder current
- Update this README when structure changes

---

## 📝 Contributing to Documentation

When adding new documentation:
1. Place active docs in appropriate `docs/` subdirectory
2. Move superseded docs to `archive/` with appropriate category
3. Update this README with new document references
4. Use clear, descriptive filenames (UPPERCASE_WITH_UNDERSCORES.md)

---

**Documentation Status**: ✅ Organized and Current
**Version**: 1.0
**Last Organized**: 2026-02-09
