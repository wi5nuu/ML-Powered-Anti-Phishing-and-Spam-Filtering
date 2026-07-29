# ML Continuous Learning & Retraining System

## Overview

CogniMail's ML Retraining System enables **continuous learning** from user feedback, making the anti-phishing/spam detection model progressively smarter over time - just like modern AI systems (ChatGPT, Claude, etc.).

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ 1. EMAIL DETECTION (Automatic)                             │
├─────────────────────────────────────────────────────────────┤
│ New email arrives → ML Model classifies → Saved to database│
│ ✅ All emails stored with scores and predictions            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. USER FEEDBACK (Manual Correction)                       │
├─────────────────────────────────────────────────────────────┤
│ User reports:                                               │
│ • False Positive: "This is safe, not spam"                 │
│ • False Negative: "This is spam/phishing, not safe"        │
│ ✅ Automatically saved to training_samples table            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ADMIN REVIEW (Quality Control)                          │
├─────────────────────────────────────────────────────────────┤
│ Admin reviews feedback → Approves valid samples            │
│ ✅ Status: pending → approved                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. AUTOMATED RETRAINING (Continuous Learning)              │
├─────────────────────────────────────────────────────────────┤
│ Worker checks every 24 hours:                               │
│ • Fetch approved samples (minimum 100)                      │
│ • Extract features + combine with original data             │
│ • Train new XGBoost model                                   │
│ • Validate against current model                            │
│ • Deploy if accuracy >= 85%                                 │
│ ✅ Model gets smarter automatically!                        │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### ✅ **Production-Ready**
- **Automated scheduling**: Runs every 24 hours (configurable)
- **Model versioning**: All models backed up with timestamps
- **Rollback capability**: Restore previous models if needed
- **Comprehensive validation**: New models must pass quality checks
- **Audit logging**: Full trail of all retraining attempts

### ✅ **Intelligent Learning**
- **Prevents catastrophic forgetting**: Combines new samples with original training data
- **Quality thresholds**: Only deploys if accuracy ≥ 85% (configurable)
- **A/B comparison**: New model compared against production model
- **Class balancing**: Handles imbalanced datasets automatically

### ✅ **Safety & Reliability**
- **Minimum sample requirement**: Won't train on too-few samples (default: 100)
- **Feature consistency**: Ensures new model uses same features as production
- **Error handling**: Graceful failures with detailed logging
- **Health checks**: Docker container monitoring
- **Database transactions**: All-or-nothing updates

## Architecture

### Components

1. **ML Retraining Worker** (`worker/ml_retraining_worker.py`)
   - Fetches approved training samples from database
   - Extracts features using existing pipeline
   - Trains XGBoost model with validation
   - Deploys new model if quality checks pass
   - Marks samples as used

2. **Dashboard API Integration** (`dashboard/app.py:6930`)
   - Endpoint: `POST /api/admin/training/retrain`
   - Triggers retraining manually via UI
   - Runs in background task
   - Audit logging

3. **Docker Service** (`docker-compose.yml`)
   - Continuous worker service
   - Automated scheduling
   - Model persistence via volumes
   - Health monitoring

4. **Manual Trigger Script** (`scripts/trigger_retraining.py`)
   - Check status and sample counts
   - Test retraining locally
   - Force retraining for testing
   - View detailed metrics

## Configuration

### Environment Variables (`.env`)

```bash
# Enable/disable automated retraining
RETRAINING_ENABLED=true

# Minimum approved training samples required
RETRAINING_MIN_SAMPLES=100

# Minimum model accuracy to deploy (0.85 = 85%)
RETRAINING_MIN_ACCURACY=0.85

# Hours between automated retraining checks
RETRAINING_SCHEDULE_HOURS=24

# Model artifacts directory
MODEL_DIR=classifier/models
```

## Deployment

### Production Deployment (Docker)

```bash
# 1. Update .env with retraining configuration
vim .env

# 2. Start all services including retraining worker
docker-compose --profile production up -d

# 3. Verify retraining service is running
docker-compose ps ml_retraining

# 4. Check logs
docker-compose logs -f ml_retraining
```

### Development / Testing

```bash
# Check current status
python scripts/trigger_retraining.py --dry-run

# Run retraining once (manual trigger)
python scripts/trigger_retraining.py

# Force retraining with lower thresholds for testing
python scripts/trigger_retraining.py --force --min-samples 10
```

## Usage Workflow

### 1. Users Report Misclassified Emails

**Dashboard UI:**
- User opens quarantined email
- Clicks "Report False Positive" → Email marked as safe
- Clicks "Report False Negative" → Email marked as threat

**API:**
```bash
# Report false positive (incorrectly marked as spam)
curl -X POST https://cognimail.example.com/api/emails/{email_id}/report-false-positive \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"notes": "This is a legitimate invoice from our vendor"}'

# Report false negative (missed phishing)
curl -X POST https://cognimail.example.com/api/emails/{email_id}/report-false-negative \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"corrected_label": "phishing", "notes": "Credential harvesting attempt"}'
```

### 2. Admin Reviews Training Samples

**Dashboard:** `/admin/training-samples`

**API:**
```bash
# List pending samples
curl https://cognimail.example.com/api/admin/training-samples?status=pending

# Approve a sample
curl -X PUT https://cognimail.example.com/api/admin/training-samples/{sample_id} \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "approved"}'
```

### 3. Trigger Retraining

**Automatic (Every 24 hours):**
- Worker automatically checks for approved samples
- Retrains if ≥ 100 samples available
- Deploys if new model passes validation

**Manual via Dashboard:**
- Navigate to Admin → Training
- Click "Retrain Model" button
- View progress in audit logs

**Manual via API:**
```bash
curl -X POST https://cognimail.example.com/api/admin/training/retrain \
  -H "Authorization: Bearer $TOKEN"
```

**Manual via CLI:**
```bash
python scripts/trigger_retraining.py
```

### 4. Monitor Retraining Results

**Check Status:**
```bash
python scripts/trigger_retraining.py --dry-run
```

**View Audit Logs:**
```sql
SELECT timestamp, status, description, changes
FROM audit_trail
WHERE action = 'model_retrain'
ORDER BY timestamp DESC
LIMIT 10;
```

**Check Model Versions:**
```bash
ls -lah classifier/models/xgb_model__latest_*.joblib
ls -lah classifier/models/backups/
```

## Model Lifecycle

### Training Process

1. **Data Collection**
   - Fetch approved samples from `training_samples` table
   - Fetch original training data from `quarantine_emails` (for stability)
   - Combine: typically 100 new + 5000 original samples

2. **Feature Extraction**
   - Parse raw email content
   - Extract TF-IDF text features (5000 max features)
   - Extract 20 structured features (URLs, attachments, urgency score, etc.)
   - Build sparse feature matrix

3. **Model Training**
   - Split: 70% train, 15% validation, 15% test
   - Train XGBoost classifier (200 estimators, max_depth=6)
   - Early stopping on validation set
   - Handle class imbalance with scale_pos_weight

4. **Validation**
   - Test set accuracy must be ≥ 85% (configurable)
   - Compare with production model
   - Must not degrade by > 2% accuracy
   - Calculate precision, recall, F1, confusion matrix

5. **Deployment**
   - Backup current production models
   - Save new models with timestamp
   - Update `*_latest.joblib` symlinks
   - Save metadata JSON with metrics
   - Mark training samples as `used_in_training`

### Version Management

**Model Files:**
```
classifier/models/
├── xgb_model_latest.joblib          ← Current production model
├── tfidf_latest.joblib               ← Current TF-IDF vectorizer
├── scaler_latest.joblib              ← Current feature scaler
├── metadata_latest.json              ← Current metadata
│
├── xgb_model__latest_20260729_143022.joblib   ← Timestamped versions
├── tfidf__latest_20260729_143022.joblib
├── scaler__latest_20260729_143022.joblib
├── metadata__latest_20260729_143022.json
│
└── backups/
    └── backup_20260729_143022/       ← Full backup before deployment
        ├── xgb_model_latest.joblib
        ├── tfidf_latest.joblib
        ├── scaler_latest.joblib
        └── metadata_latest.json
```

**Rollback:**
```bash
# List backups
ls -lh classifier/models/backups/

# Restore from backup
cp classifier/models/backups/backup_20260729_143022/* classifier/models/

# Restart classifier service
docker-compose restart classifier
```

## Monitoring

### Health Checks

**Retraining Worker Health:**
```bash
docker-compose ps ml_retraining
curl http://localhost:8000/api/health  # Dashboard health includes retraining status
```

**Check Training Samples:**
```sql
-- Count by status
SELECT status, COUNT(*) 
FROM training_samples 
GROUP BY status;

-- Recent feedback
SELECT email_id, feedback_type, corrected_label, reported_by, created_at
FROM training_samples
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

### Metrics & Logs

**Retraining Logs:**
```bash
# Docker logs
docker-compose logs -f ml_retraining

# Specific timeframe
docker-compose logs --since 30m ml_retraining
```

**Audit Trail:**
```sql
SELECT 
    timestamp,
    status,
    description,
    changes->>'model_version' as model_version,
    changes->'training_metrics'->>'accuracy' as accuracy
FROM audit_trail
WHERE action = 'model_retrain'
ORDER BY timestamp DESC;
```

**Training Statistics:**
```bash
curl https://cognimail.example.com/api/admin/training/stats \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

### Retraining Fails to Start

**Check Docker service:**
```bash
docker-compose ps ml_retraining
docker-compose logs ml_retraining
```

**Common causes:**
- Database connection issues
- Missing environment variables
- Insufficient disk space for model files

### Not Enough Training Samples

**Check sample counts:**
```bash
python scripts/trigger_retraining.py --dry-run
```

**Solutions:**
- Lower threshold temporarily: `RETRAINING_MIN_SAMPLES=50`
- Approve more pending samples
- Wait for more user feedback

### New Model Rejected

**Check validation metrics:**
```sql
SELECT changes 
FROM audit_trail 
WHERE action = 'model_retrain' 
  AND status = 'REJECTED'
ORDER BY timestamp DESC 
LIMIT 1;
```

**Common causes:**
- Accuracy below threshold (< 85%)
- Worse than current production model
- Insufficient test data
- Class imbalance too extreme

**Solutions:**
- Review rejected samples quality
- Increase sample diversity
- Adjust `RETRAINING_MIN_ACCURACY` threshold
- Add more original training data

### Model Performance Degradation

**Compare model versions:**
```bash
# Check metadata
cat classifier/models/metadata_latest.json
cat classifier/models/metadata__latest_20260729_*.json
```

**Rollback to previous version:**
```bash
# Find best backup
ls -lh classifier/models/backups/

# Restore
./scripts/rollback_model.sh backup_20260729_143022

# Or manual:
cp classifier/models/backups/backup_20260729_143022/* classifier/models/
docker-compose restart classifier
```

### Out of Memory During Training

**Symptoms:**
- Retraining crashes
- OOM errors in logs

**Solutions:**
1. Reduce `RETRAINING_MIN_SAMPLES` to process fewer samples
2. Reduce TF-IDF `max_features` from 5000 to 3000
3. Limit original data fetch from 5000 to 2000
4. Increase Docker memory limits
5. Use server with more RAM

## Performance Impact

### Resource Usage

**Training:**
- CPU: ~4-8 cores for 10-30 minutes
- Memory: ~4-8 GB RAM
- Disk: ~500 MB for model artifacts
- Network: Minimal (only database queries)

**Production Inference:**
- No impact - retraining happens offline
- Classifier service briefly reloads model (~2 seconds)
- Requests continue to work during reload

### Training Time

Typical retraining with 5,100 samples (100 new + 5,000 original):
- Feature extraction: ~5-10 minutes
- Model training: ~10-20 minutes
- Validation: ~2-5 minutes
- **Total: ~20-35 minutes**

Scales roughly linearly with sample count.

## Best Practices

### 1. Sample Quality Over Quantity
- Review all pending samples before approval
- Reject obvious spam in training data
- Ensure corrected labels are accurate
- Add detailed notes for edge cases

### 2. Gradual Learning
- Start with `RETRAINING_MIN_SAMPLES=100`
- Increase threshold as you gain confidence
- Monitor first few retrainings closely
- Don't rush to lower quality thresholds

### 3. Backup Before Major Changes
- Always keep last 5-10 model backups
- Test rollback procedure periodically
- Document model versions in use
- Archive old backups to external storage

### 4. Monitor Continuously
- Check retraining logs daily
- Review audit trail weekly
- Track accuracy trends over time
- Alert on validation failures

### 5. User Feedback Hygiene
- Educate users on proper reporting
- Provide clear feedback categories
- Make feedback easy to submit
- Thank users for contributions

## FAQ

**Q: How often should retraining run?**
A: Default 24 hours is good. Increase to 7 days for low-traffic systems, decrease to 12 hours for high-traffic.

**Q: What if I don't have 100 samples yet?**
A: Lower `RETRAINING_MIN_SAMPLES` to 50 temporarily, but maintain quality over quantity.

**Q: Can retraining make the model worse?**
A: No - validation checks prevent deployment if new model is worse than current.

**Q: How do I know if retraining is working?**
A: Check audit logs, run `trigger_retraining.py --dry-run`, monitor false positive/negative rates.

**Q: Can I train on production data automatically?**
A: Yes, but only approved samples are used. This ensures quality control.

**Q: What happens if retraining fails?**
A: Current production model stays active. Failure is logged. Manual intervention needed.

**Q: How long are old models kept?**
A: Forever unless manually deleted. Manage `classifier/models/backups/` disk usage.

**Q: Can I run retraining manually without Docker?**
A: Yes: `python scripts/trigger_retraining.py`

## Advanced Topics

### Custom Feature Engineering

Edit `classifier/features.py` to add new features. Ensure backwards compatibility:

```python
# Add new feature
STRUCTURED_FEATURES = [
    # ... existing features ...
    "new_custom_feature",  # Add at end to preserve indices
]
```

### Multi-Model Ensemble

Train multiple models and use voting:

```python
# Modify ml_retraining_worker.py
models = []
for seed in [42, 43, 44]:
    model = train_new_model(..., random_state=seed)
    models.append(model)

# Deploy ensemble
joblib.dump(models, "xgb_ensemble_latest.joblib")
```

### A/B Testing New Models

Deploy to subset of traffic:

```python
# In classifier/predict.py
if random.random() < 0.1:  # 10% traffic
    model = state.model_experimental
else:
    model = state.model
```

### Transfer Learning from External Datasets

```python
# Fetch external phishing dataset
external_data = fetch_phishtank_dataset()

# Combine with internal samples
combined_samples = pd.concat([training_samples, external_data])

# Train
feature_df = extract_features_from_samples(combined_samples)
```

---

## Summary

CogniMail's ML Retraining System implements **true continuous learning**:

✅ **Automatic**: Runs every 24 hours, no manual intervention needed
✅ **Safe**: Quality checks prevent model degradation
✅ **Smart**: Combines new feedback with original data
✅ **Traceable**: Full audit trail and versioning
✅ **Rollback**: Easy recovery from any issues

Your anti-phishing/spam system will **get progressively smarter** as users provide feedback - just like modern AI systems!

**Next Steps:**
1. Enable retraining: `docker-compose --profile production up -d`
2. Start collecting feedback from users
3. Review and approve training samples
4. Monitor first retraining cycle
5. Adjust thresholds based on results

**Questions?** Check audit logs, review training stats, or run `trigger_retraining.py --dry-run`
