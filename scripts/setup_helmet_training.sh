#!/bin/bash
# Complete setup script for helmet detection training
# Uses Indian Helmet Detection Dataset from Kaggle

set -e

echo "============================================================"
echo "  Helmet Detection Model Training Setup"
echo "============================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Check Kaggle credentials
echo "1. Checking Kaggle API credentials..."
if [ ! -f ~/.kaggle/kaggle.json ]; then
    echo -e "${YELLOW}⚠️  Kaggle API credentials not found${NC}"
    echo ""
    echo "To download the dataset, you need to set up Kaggle API:"
    echo ""
    echo "  1. Go to https://www.kaggle.com/settings/account"
    echo "  2. Scroll to 'API' section"
    echo "  3. Click 'Create New API Token'"
    echo "  4. This downloads kaggle.json"
    echo "  5. Move it to ~/.kaggle/kaggle.json"
    echo "  6. Run: chmod 600 ~/.kaggle/kaggle.json"
    echo ""
    echo "Commands:"
    echo "  mkdir -p ~/.kaggle"
    echo "  mv ~/Downloads/kaggle.json ~/.kaggle/"
    echo "  chmod 600 ~/.kaggle/kaggle.json"
    echo ""
    echo -e "${YELLOW}After setting up credentials, run this script again.${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Kaggle credentials found${NC}"
fi

# 2. Install dependencies
echo ""
echo "2. Installing training dependencies..."
cd /home/yashcs/traffic-eye
source venv/bin/activate

if pip install -r scripts/requirements-training.txt -q; then
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi

# 3. Download dataset
echo ""
echo "3. Downloading Indian Helmet Detection Dataset from Kaggle..."
DATASET_DIR="data/helmet_dataset"
mkdir -p "$DATASET_DIR"

if kaggle datasets download -d aryanvaid13/indian-helmet-detection-dataset -p "$DATASET_DIR" --unzip; then
    echo -e "${GREEN}✅ Dataset downloaded${NC}"
else
    echo -e "${RED}❌ Failed to download dataset${NC}"
    echo "Manual download: https://www.kaggle.com/datasets/aryanvaid13/indian-helmet-detection-dataset"
    exit 1
fi

# 4. Check dataset structure
echo ""
echo "4. Checking dataset structure..."
if [ -d "$DATASET_DIR/train" ] && [ -d "$DATASET_DIR/val" ]; then
    echo -e "${GREEN}✅ Dataset structure valid${NC}"
    echo "   Train: $(find $DATASET_DIR/train -type f | wc -l) images"
    echo "   Val: $(find $DATASET_DIR/val -type f | wc -l) images"
else
    echo -e "${YELLOW}⚠️  Unexpected dataset structure${NC}"
    echo "Dataset contents:"
    ls -la "$DATASET_DIR"
    echo ""
    echo "Expected structure:"
    echo "  data/helmet_dataset/"
    echo "  ├── train/"
    echo "  │   ├── helmet/"
    echo "  │   └── no_helmet/"
    echo "  └── val/"
    echo "      ├── helmet/"
    echo "      └── no_helmet/"
fi

# 5. Summary
echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "Dataset location: $DATASET_DIR"
echo ""
echo "Next steps:"
echo "  1. Train model:"
echo "     python scripts/train_helmet.py --data-dir $DATASET_DIR --epochs 50"
echo ""
echo "  2. Convert to TFLite:"
echo "     python scripts/convert_model.py --model models/helmet_mobilenetv3.h5"
echo ""
echo "  3. Test on Pi:"
echo "     python -c \"from src.detection.helmet import TFLiteHelmetClassifier; ...\""
echo ""
