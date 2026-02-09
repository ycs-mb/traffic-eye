#!/bin/bash
# GCP Credentials Setup Script for Traffic-Eye

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║       GCP Vertex AI Credentials Setup for Traffic-Eye        ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check if credentials file path is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <path-to-credentials.json>"
    echo ""
    echo "Examples:"
    echo "  $0 ~/Downloads/gcloud-photo-project-xxxxx.json"
    echo "  $0 /path/to/key.json"
    echo ""
    exit 1
fi

CREDS_FILE="$1"

# Check if file exists
if [ ! -f "$CREDS_FILE" ]; then
    echo "❌ Error: Credentials file not found: $CREDS_FILE"
    exit 1
fi

echo "✅ Found credentials file: $CREDS_FILE"
echo ""

# Extract project ID from JSON
PROJECT_ID=$(grep -o '"project_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$CREDS_FILE" | head -1 | sed 's/.*: "\(.*\)"/\1/')

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Could not extract project_id from credentials file"
    exit 1
fi

echo "📋 Project ID: $PROJECT_ID"
echo ""

# Create secure directory for credentials
echo "📁 Creating secure directory..."
sudo mkdir -p /etc/traffic-eye
sudo chmod 755 /etc/traffic-eye

# Copy credentials file
echo "🔐 Installing credentials..."
DEST_FILE="/etc/traffic-eye/gcp-credentials.json"
sudo cp "$CREDS_FILE" "$DEST_FILE"
sudo chmod 600 "$DEST_FILE"
sudo chown root:root "$DEST_FILE"

echo "✅ Credentials installed to: $DEST_FILE"
echo ""

# Create environment file
echo "⚙️  Creating environment configuration..."
ENV_FILE="/etc/traffic-eye.env"

sudo tee "$ENV_FILE" > /dev/null <<EOF
# GCP Vertex AI Configuration for Traffic-Eye
GOOGLE_APPLICATION_CREDENTIALS="/etc/traffic-eye/gcp-credentials.json"
GCP_PROJECT_ID="$PROJECT_ID"
GCP_LOCATION="us-central1"

# Email Configuration (set your password)
# TRAFFIC_EYE_EMAIL_PASSWORD="your-gmail-app-password"

# Cloud API Configuration
# TRAFFIC_EYE_CLOUD_API_KEY="optional-for-other-providers"
EOF

sudo chmod 600 "$ENV_FILE"

echo "✅ Environment file created: $ENV_FILE"
echo ""

# Update traffic-eye configuration
CONFIG_FILE="/home/yashcs/traffic-eye/config/settings.yaml"
if [ -f "$CONFIG_FILE" ]; then
    echo "📝 Updating Traffic-Eye configuration..."
    # Already configured in settings.yaml
    echo "✅ Configuration already set"
else
    echo "⚠️  Warning: Config file not found at $CONFIG_FILE"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║                    ✅ SETUP COMPLETE!                         ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "🧪 Next step: Test the configuration"
echo ""
echo "Run this command:"
echo "  source /etc/traffic-eye.env"
echo "  cd /home/yashcs/traffic-eye"
echo "  source venv/bin/activate"
echo "  python scripts/test_vertex_ai.py"
echo ""
