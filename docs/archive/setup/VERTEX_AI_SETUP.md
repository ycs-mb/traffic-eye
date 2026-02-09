# GCP Vertex AI Cloud-Only OCR Setup Guide

This guide explains how to set up **cloud-only OCR** using **GCP Vertex AI (Gemini Pro Vision)** for license plate reading in the Traffic-Eye system.

## 📋 Overview

**Cloud-only OCR** skips all local OCR processing and sends plate images directly to GCP Vertex AI for text extraction. This provides:

- ✅ **90-95% accuracy** on Indian license plates
- ✅ **No local resource usage** (saves RAM/CPU on Raspberry Pi)
- ✅ **No model installation** (no PaddleOCR/Tesseract needed)
- ⚠️ **Requires internet** connection for all plate reads
- ⚠️ **API costs** per request (~$0.0025 per image with Gemini)

---

## 🚀 Prerequisites

1. **GCP Account** with billing enabled
2. **GCP Project** created
3. **Vertex AI API** enabled
4. **Service Account** with appropriate permissions

---

## 📝 Step-by-Step Setup

### **Step 1: Create GCP Project**

```bash
# Using gcloud CLI (or use GCP Console)
gcloud projects create traffic-eye-ocr --name="Traffic Eye OCR"

# Set as default project
gcloud config set project traffic-eye-ocr
```

**Via Console**: https://console.cloud.google.com/projectcreate

---

### **Step 2: Enable Vertex AI API**

```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Enable required APIs
gcloud services enable storage-component.googleapis.com
gcloud services enable compute.googleapis.com
```

**Via Console**: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com

---

### **Step 3: Create Service Account**

```bash
# Create service account
gcloud iam service-accounts create traffic-eye-sa \
    --description="Traffic Eye Vertex AI OCR" \
    --display-name="Traffic Eye Service Account"

# Grant Vertex AI User role
gcloud projects add-iam-policy-binding traffic-eye-ocr \
    --member="serviceAccount:traffic-eye-sa@traffic-eye-ocr.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Grant Storage Object Viewer role (for model access)
gcloud projects add-iam-policy-binding traffic-eye-ocr \
    --member="serviceAccount:traffic-eye-sa@traffic-eye-ocr.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

---

### **Step 4: Create and Download Service Account Key**

```bash
# Create JSON key
gcloud iam service-accounts keys create ~/traffic-eye-key.json \
    --iam-account=traffic-eye-sa@traffic-eye-ocr.iam.gserviceaccount.com

# Secure the key file
chmod 600 ~/traffic-eye-key.json
```

**⚠️ IMPORTANT**: Never commit this key to version control!

---

### **Step 5: Configure Environment on Raspberry Pi**

```bash
# Copy service account key to Pi
scp ~/traffic-eye-key.json pi@raspberrypi.local:/home/pi/

# SSH into Pi
ssh pi@raspberrypi.local

# Move key to secure location
sudo mkdir -p /etc/traffic-eye
sudo mv ~/traffic-eye-key.json /etc/traffic-eye/
sudo chmod 600 /etc/traffic-eye/traffic-eye-key.json
sudo chown root:root /etc/traffic-eye/traffic-eye-key.json

# Set environment variable
echo 'export GOOGLE_APPLICATION_CREDENTIALS="/etc/traffic-eye/traffic-eye-key.json"' | sudo tee -a /etc/traffic-eye.env
echo 'export GCP_PROJECT_ID="traffic-eye-ocr"' | sudo tee -a /etc/traffic-eye.env
echo 'export GCP_LOCATION="us-central1"' | sudo tee -a /etc/traffic-eye.env

# Source the environment
source /etc/traffic-eye.env
```

---

### **Step 6: Update Traffic-Eye Configuration**

Edit `/opt/traffic-eye/config/settings.yaml`:

```yaml
ocr:
  engine: "cloud_only"  # Use Vertex AI for all plate reading
  confidence_threshold: 0.7
  cloud_only: true  # Skip local OCR entirely

cloud:
  provider: "vertex_ai"  # Use GCP Vertex AI
  confidence_threshold: 0.90  # Confidence threshold for verification
  max_retries: 3
  timeout_seconds: 30
  gcp_project_id: "traffic-eye-ocr"  # Your GCP project ID
  gcp_location: "us-central1"  # GCP region (us-central1, asia-south1, etc.)
```

**Available GCP Locations:**
- `us-central1` (Iowa, USA) - Default, lowest latency for most regions
- `us-east1` (South Carolina, USA)
- `europe-west1` (Belgium)
- `asia-south1` (Mumbai, India) - **Recommended for Indian deployment**
- `asia-southeast1` (Singapore)

---

### **Step 7: Update systemd Service**

Edit `/etc/systemd/system/traffic-eye.service`:

```ini
[Service]
# Add environment file that includes GCP credentials
EnvironmentFile=-/etc/traffic-eye.env
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart traffic-eye
```

---

### **Step 8: Verify Setup**

Test Vertex AI connectivity:

```bash
source venv/bin/activate
python -c "
from google.cloud import aiplatform
aiplatform.init(project='traffic-eye-ocr', location='us-central1')
print('✅ Vertex AI initialized successfully')
"
```

Expected output:
```
✅ Vertex AI initialized successfully
```

---

## 🧪 Testing Cloud OCR

Create a test script `test_cloud_ocr.py`:

```python
#!/usr/bin/env python3
"""Test Vertex AI Cloud OCR."""

import cv2
from src.ocr.cloud_ocr import CloudOCR

# Initialize Cloud OCR
ocr = CloudOCR(
    project_id="traffic-eye-ocr",
    location="us-central1",
    confidence_threshold=0.7
)

# Load test plate image
plate_img = cv2.imread("test_plate.jpg")

# Extract plate text
text, confidence = ocr.extract_plate_text(plate_img)

if text:
    print(f"✅ Plate detected: {text} (confidence: {confidence:.2f})")
else:
    print("❌ Plate not readable")
```

Run:
```bash
python test_cloud_ocr.py
```

---

## 💰 Cost Estimation

**Gemini Pro Vision Pricing** (as of 2024):
- **Images**: $0.0025 per image
- **Text**: $0.000125 per 1K characters (negligible)

**Usage Estimation:**
- 100 violations/day × 3 images/violation = 300 images/day
- 300 images × $0.0025 = **$0.75/day**
- **~$23/month** for 100 violations/day

**With cloud verification** (not all plates need OCR):
- Only low-confidence detections sent to cloud
- Estimated 30-50% of detections
- **~$7-12/month**

**Free Tier**: GCP provides $300 credit for 90 days

---

## 🔒 Security Best Practices

### **1. Service Account Permissions**

Use **least privilege** principle:
```bash
# Only grant necessary roles
roles/aiplatform.user       # Vertex AI predictions
roles/storage.objectViewer  # Read model files (if needed)
```

### **2. Rotate Service Account Keys**

```bash
# Create new key
gcloud iam service-accounts keys create ~/new-key.json \
    --iam-account=traffic-eye-sa@traffic-eye-ocr.iam.gserviceaccount.com

# Update Pi configuration
# Delete old key
gcloud iam service-accounts keys delete OLD_KEY_ID \
    --iam-account=traffic-eye-sa@traffic-eye-ocr.iam.gserviceaccount.com
```

### **3. Monitor API Usage**

Set up budget alerts:
```bash
# Via Console: Billing → Budgets & alerts
# Alert when spend exceeds $10/month
```

### **4. Restrict API Access**

Use **VPC Service Controls** to limit API access to specific IPs (optional, advanced).

---

## 📊 Monitoring & Logging

### **View API Usage**

```bash
# View Vertex AI usage
gcloud logging read "resource.type=aiplatform.googleapis.com/Endpoint" --limit 10

# View costs
gcloud billing accounts list
gcloud billing accounts get-iam-policy BILLING_ACCOUNT_ID
```

### **Cloud Console Monitoring**

- **Vertex AI Dashboard**: https://console.cloud.google.com/vertex-ai
- **Logs Explorer**: https://console.cloud.google.com/logs
- **Billing**: https://console.cloud.google.com/billing

---

## 🐛 Troubleshooting

### **Error: "Application Default Credentials not found"**

```bash
# Verify credentials file exists
ls -la /etc/traffic-eye/traffic-eye-key.json

# Check environment variable
echo $GOOGLE_APPLICATION_CREDENTIALS

# Set it if missing
export GOOGLE_APPLICATION_CREDENTIALS="/etc/traffic-eye/traffic-eye-key.json"
```

### **Error: "Permission denied on Vertex AI API"**

```bash
# Verify service account has correct role
gcloud projects get-iam-policy traffic-eye-ocr \
    --flatten="bindings[].members" \
    --format='table(bindings.role)' \
    --filter="bindings.members:traffic-eye-sa@*"
```

Should show: `roles/aiplatform.user`

### **Error: "Vertex AI API not enabled"**

```bash
# Enable the API
gcloud services enable aiplatform.googleapis.com

# Verify it's enabled
gcloud services list --enabled | grep aiplatform
```

### **High Latency (>5 seconds per request)**

- **Switch to closer region**: Use `asia-south1` for India
- **Check network**: Ensure stable internet connection
- **Increase timeout**: Update `timeout_seconds: 60` in config

---

## 🔄 Fallback to Local OCR

If cloud connectivity is unreliable, switch to **hybrid mode**:

```yaml
ocr:
  engine: "tesseract"  # Local OCR
  confidence_threshold: 0.6
  cloud_only: false  # Use cloud only for low-confidence results

cloud:
  provider: "vertex_ai"
  confidence_threshold: 0.90  # Cloud verification for conf < 0.7
```

---

## 📚 Additional Resources

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini Pro Vision Pricing](https://cloud.google.com/vertex-ai/pricing)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
- [GCP Free Tier](https://cloud.google.com/free)

---

## ✅ Configuration Checklist

- [ ] GCP project created
- [ ] Vertex AI API enabled
- [ ] Service account created with `aiplatform.user` role
- [ ] Service account key downloaded and secured
- [ ] Environment variables set (`GOOGLE_APPLICATION_CREDENTIALS`, `GCP_PROJECT_ID`)
- [ ] `settings.yaml` updated with `provider: vertex_ai`
- [ ] systemd service configured with environment file
- [ ] Connectivity tested with verification script
- [ ] Budget alerts configured ($10/month threshold)
- [ ] Monitoring dashboard bookmarked

---

**Status**: ✅ **Cloud-Only OCR Ready**

With this configuration, Traffic-Eye will use GCP Vertex AI for all license plate reading, providing 90-95% accuracy without any local resource usage.
