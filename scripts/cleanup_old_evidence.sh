#!/bin/bash
# Automatic cleanup of old evidence files to prevent SD card from filling up

EVIDENCE_DIR="/home/yashcs/traffic-eye/data/evidence"
KEEP_DAYS=7  # Keep evidence for 7 days
MIN_FREE_SPACE_GB=5  # Minimum free space in GB

echo "=== Evidence Cleanup Script ==="
echo "Evidence directory: $EVIDENCE_DIR"
echo "Keep files for: $KEEP_DAYS days"
echo "Minimum free space: ${MIN_FREE_SPACE_GB}GB"
echo ""

# Create evidence directory if it doesn't exist
mkdir -p "$EVIDENCE_DIR"

# Check current disk usage
CURRENT_FREE=$(df -BG "$EVIDENCE_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
echo "Current free space: ${CURRENT_FREE}GB"

# Delete files older than KEEP_DAYS
echo "Deleting evidence older than $KEEP_DAYS days..."
DELETED_COUNT=$(find "$EVIDENCE_DIR" -type f -mtime +$KEEP_DAYS -delete -print | wc -l)
echo "Deleted $DELETED_COUNT old files"

# If still low on space, delete oldest files until we have MIN_FREE_SPACE_GB
CURRENT_FREE=$(df -BG "$EVIDENCE_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$CURRENT_FREE" -lt "$MIN_FREE_SPACE_GB" ]; then
    echo "⚠️  Still low on space (${CURRENT_FREE}GB), deleting oldest files..."

    # Delete oldest files until we have enough space
    while [ "$CURRENT_FREE" -lt "$MIN_FREE_SPACE_GB" ]; do
        OLDEST_FILE=$(find "$EVIDENCE_DIR" -type f -printf '%T+ %p\n' | sort | head -1 | cut -d' ' -f2-)
        if [ -z "$OLDEST_FILE" ]; then
            echo "No more files to delete!"
            break
        fi

        echo "Deleting: $OLDEST_FILE"
        rm -f "$OLDEST_FILE"

        CURRENT_FREE=$(df -BG "$EVIDENCE_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    done
fi

# Empty trash directories
find "$EVIDENCE_DIR" -type d -empty -delete 2>/dev/null

echo ""
echo "✅ Cleanup complete"
echo "Final free space: ${CURRENT_FREE}GB"
echo ""

# Log disk usage
df -h "$EVIDENCE_DIR"
