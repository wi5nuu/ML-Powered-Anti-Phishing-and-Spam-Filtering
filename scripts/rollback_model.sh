#!/bin/bash
"""
Model Rollback Script

Restores a previous model version from backup.

Usage:
    ./scripts/rollback_model.sh <backup_name>
    
Example:
    ./scripts/rollback_model.sh backup_20260729_143022
"""

set -e  # Exit on error

BACKUP_NAME=$1
MODEL_DIR="classifier/models"
BACKUP_DIR="$MODEL_DIR/backups"

if [ -z "$BACKUP_NAME" ]; then
    echo "Error: Backup name required"
    echo ""
    echo "Usage: $0 <backup_name>"
    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR" | grep "^d" | awk '{print "  - " $9}'
    exit 1
fi

BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

if [ ! -d "$BACKUP_PATH" ]; then
    echo "Error: Backup not found: $BACKUP_PATH"
    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR" | grep "^d" | awk '{print "  - " $9}'
    exit 1
fi

echo "======================================"
echo "MODEL ROLLBACK"
echo "======================================"
echo ""
echo "Backup: $BACKUP_NAME"
echo "Location: $BACKUP_PATH"
echo ""

# Create a backup of current models before rollback
CURRENT_BACKUP="$BACKUP_DIR/pre_rollback_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$CURRENT_BACKUP"

echo "Creating backup of current models..."
cp "$MODEL_DIR/xgb_model_latest.joblib" "$CURRENT_BACKUP/" 2>/dev/null || true
cp "$MODEL_DIR/tfidf_latest.joblib" "$CURRENT_BACKUP/" 2>/dev/null || true
cp "$MODEL_DIR/scaler_latest.joblib" "$CURRENT_BACKUP/" 2>/dev/null || true
cp "$MODEL_DIR/metadata_latest.json" "$CURRENT_BACKUP/" 2>/dev/null || true

echo "Restoring models from backup..."
cp "$BACKUP_PATH"/* "$MODEL_DIR/"

echo ""
echo "======================================"
echo "ROLLBACK COMPLETE"
echo "======================================"
echo ""
echo "Restored models:"
ls -lh "$MODEL_DIR"/*_latest.* | awk '{print "  - " $9}'
echo ""
echo "Current models backed up to: $CURRENT_BACKUP"
echo ""
echo "Next steps:"
echo "  1. Restart classifier service: docker-compose restart classifier"
echo "  2. Verify health: curl http://localhost:8001/health"
echo "  3. Check model info: curl http://localhost:8001/model-info"
echo ""
