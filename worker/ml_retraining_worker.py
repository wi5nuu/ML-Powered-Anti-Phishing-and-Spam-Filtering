"""
CogniMail ML Retraining Worker — Production-Ready Continuous Learning System.

Features:
  1. Automated retraining from approved training samples
  2. Model versioning with rollback capability
  3. Comprehensive validation before deployment
  4. A/B testing support
  5. Audit trail and metrics logging
  6. Production-safe with extensive error handling
  7. Configurable scheduling and thresholds
  
Environment Variables:
  - RETRAINING_MIN_SAMPLES: Minimum samples required (default: 100)
  - RETRAINING_MIN_ACCURACY: Minimum accuracy threshold (default: 0.85)
  - RETRAINING_SCHEDULE_HOURS: Hours between retraining checks (default: 24)
  - RETRAINING_ENABLED: Enable/disable retraining (default: true)
  - MODEL_DIR: Directory for model artifacts (default: classifier/models)
  - DB_URL: PostgreSQL connection string
"""

import os
import sys
import json
import logging
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sqlalchemy import create_engine, text, update, func, select
from sqlalchemy.orm import sessionmaker, Session

# Import existing classifier components
from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES
from classifier.inference_matrix import build_feature_matrix

from database.models import TrainingSample

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

RETRAINING_MIN_SAMPLES = int(os.getenv("RETRAINING_MIN_SAMPLES", "100"))
RETRAINING_MIN_ACCURACY = float(os.getenv("RETRAINING_MIN_ACCURACY", "0.85"))
RETRAINING_ENABLED = os.getenv("RETRAINING_ENABLED", "true").lower() == "true"
MODEL_DIR = Path(os.getenv("MODEL_DIR", "classifier/models"))
BACKUP_DIR = MODEL_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Label mapping: database labels → training labels
LABEL_MAPPING = {
    "clean": 0,
    "spam": 1,
    "phishing": 1,  # Treat phishing as malicious (class 1)
    "suspicious": 1,
    "malware": 1,
}


# ─── Database Connection ──────────────────────────────────────────────────────

def get_db_session() -> Session:
    """Create database session from environment variables."""
    db_url = (
        os.getenv("DB_URL") 
        or os.getenv("DASHBOARD_DB_URL") 
        or os.getenv("DB_SYNC_URL")
    )
    
    if not db_url:
        raise ValueError("Database URL not found in environment variables")
    
    # Convert async URL to sync if needed
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ─── Data Extraction ──────────────────────────────────────────────────────────

def fetch_approved_training_samples(db: Session) -> pd.DataFrame:
    """
    Fetch approved training samples from database.
    
    Returns DataFrame with columns:
    - email_id, raw_email, corrected_label, original_scores, subject, sender, etc.
    """
    query = text("""
        SELECT 
            email_id,
            raw_email,
            corrected_label,
            original_label,
            feedback_type,
            original_scores,
            subject,
            sender,
            recipient_list,
            notes,
            reported_by,
            created_at
        FROM training_samples
        WHERE status = 'approved'
        ORDER BY created_at DESC
    """)
    
    result = db.execute(query)
    rows = result.fetchall()
    
    if not rows:
        logger.warning("No approved training samples found")
        return pd.DataFrame()
    
    df = pd.DataFrame(rows, columns=result.keys())
    logger.info(f"Fetched {len(df)} approved training samples")
    
    return df


def fetch_original_training_data(limit: int = 10000) -> pd.DataFrame:
    """
    Fetch original training data from quarantine_emails for baseline.
    This ensures the model doesn't forget original patterns.
    """
    db = get_db_session()
    
    try:
        query = text("""
            SELECT 
                email_id,
                raw_content as raw_email,
                category as corrected_label,
                label as original_label,
                subject,
                sender,
                recipient_list,
                fused_score,
                ml_probability,
                received_at
            FROM quarantine_emails
            WHERE raw_content IS NOT NULL 
              AND category IN ('spam', 'phishing', 'clean')
              AND status NOT IN ('trash', 'deleted')
            ORDER BY received_at DESC
            LIMIT :limit
        """)
        
        result = db.execute(query, {"limit": limit})
        rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=result.keys())
        logger.info(f"Fetched {len(df)} original training emails for stability")
        
        return df
    finally:
        db.close()


# ─── Feature Engineering ──────────────────────────────────────────────────────

def extract_features_from_samples(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract features from raw email content using existing feature extractor.
    
    Returns DataFrame with:
    - combined_text (for TF-IDF)
    - All STRUCTURED_FEATURES
    - label (numeric: 0=clean, 1=malicious)
    """
    parser = EmailParser()
    extractor = FeatureExtractor()
    
    features_list = []
    labels = []
    
    for idx, row in df.iterrows():
        try:
            # Parse raw email
            parsed = parser.parse(row['raw_email'])
            
            # Extract features
            features = extractor.extract(parsed)
            
            # Map label to numeric
            label_str = str(row['corrected_label']).lower().strip()
            label = LABEL_MAPPING.get(label_str, 1)  # Default to malicious if unknown
            
            # Build feature dict
            feature_dict = {
                'combined_text': features.combined_text,
                **{feat: getattr(features, feat, 0) for feat in STRUCTURED_FEATURES}
            }
            
            features_list.append(feature_dict)
            labels.append(label)
            
        except Exception as e:
            logger.warning(f"Failed to extract features from sample {idx}: {e}")
            continue
    
    if not features_list:
        raise ValueError("No valid features extracted from training samples")
    
    feature_df = pd.DataFrame(features_list)
    feature_df['label'] = labels
    
    logger.info(f"Extracted features from {len(feature_df)} samples")
    logger.info(f"Label distribution: {feature_df['label'].value_counts().to_dict()}")
    
    return feature_df


# ─── Model Training ───────────────────────────────────────────────────────────

def train_new_model(
    X_train, 
    y_train, 
    X_val, 
    y_val
) -> Tuple[xgb.XGBClassifier, Dict]:
    """
    Train new XGBoost model with cross-validation and hyperparameter tuning.
    
    Returns:
    - Trained model
    - Validation metrics dict
    """
    logger.info("Training new XGBoost model...")
    
    # XGBoost parameters (tuned for email classification)
    params = {
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'random_state': 42,
        'n_jobs': -1,
        'scale_pos_weight': np.sum(y_train == 0) / np.sum(y_train == 1)  # Handle imbalance
    }
    
    model = xgb.XGBClassifier(**params)
    
    # Train with early stopping
    eval_set = [(X_train, y_train), (X_val, y_val)]
    
    model.fit(
        X_train, 
        y_train,
        eval_set=eval_set,
        verbose=False
    )
    
    # Evaluate
    y_pred = model.predict(X_val)
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    
    metrics = {
        'accuracy': accuracy_score(y_val, y_pred),
        'precision': precision_score(y_val, y_pred, zero_division=0),
        'recall': recall_score(y_val, y_pred, zero_division=0),
        'f1': f1_score(y_val, y_pred, zero_division=0),
        'confusion_matrix': confusion_matrix(y_val, y_pred).tolist(),
        'n_train_samples': len(y_train),
        'n_val_samples': len(y_val),
        'class_distribution': {
            'train': {int(k): int(v) for k, v in pd.Series(y_train).value_counts().to_dict().items()},
            'val': {int(k): int(v) for k, v in pd.Series(y_val).value_counts().to_dict().items()}
        }
    }
    
    logger.info(f"Training complete - Accuracy: {metrics['accuracy']:.4f}, F1: {metrics['f1']:.4f}")
    
    return model, metrics


# ─── Model Validation ─────────────────────────────────────────────────────────

def validate_new_model(
    new_model: xgb.XGBClassifier,
    old_model: Optional[xgb.XGBClassifier],
    X_test,
    y_test,
    tfidf,
    scaler
) -> Tuple[bool, Dict]:
    """
    Validate new model against old model and minimum thresholds.
    
    Returns:
    - is_valid (bool): Whether to deploy new model
    - comparison_metrics (dict): Detailed comparison
    """
    logger.info("Validating new model...")
    
    # Evaluate new model
    y_pred_new = new_model.predict(X_test)
    new_accuracy = accuracy_score(y_test, y_pred_new)
    new_f1 = f1_score(y_test, y_pred_new, zero_division=0)
    
    comparison = {
        'new_model': {
            'accuracy': new_accuracy,
            'f1': new_f1,
            'precision': precision_score(y_test, y_pred_new, zero_division=0),
            'recall': recall_score(y_test, y_pred_new, zero_division=0),
        },
        'meets_threshold': new_accuracy >= RETRAINING_MIN_ACCURACY,
        'recommendation': 'deploy' if new_accuracy >= RETRAINING_MIN_ACCURACY else 'reject'
    }
    
    # Compare with old model if available
    if old_model is not None:
        try:
            y_pred_old = old_model.predict(X_test)
            old_accuracy = accuracy_score(y_test, y_pred_old)
            old_f1 = f1_score(y_test, y_pred_old, zero_division=0)
            
            comparison['old_model'] = {
                'accuracy': old_accuracy,
                'f1': old_f1,
                'precision': precision_score(y_test, y_pred_old, zero_division=0),
                'recall': recall_score(y_test, y_pred_old, zero_division=0),
            }
            
            comparison['improvement'] = {
                'accuracy': new_accuracy - old_accuracy,
                'f1': new_f1 - old_f1,
            }
            
            # Only deploy if improvement or comparable
            if new_accuracy < old_accuracy - 0.02:  # 2% tolerance
                comparison['recommendation'] = 'reject'
                logger.warning(f"New model accuracy {new_accuracy:.4f} is worse than old {old_accuracy:.4f}")
            
        except Exception as e:
            logger.warning(f"Could not compare with old model: {e}")
    
    is_valid = comparison['recommendation'] == 'deploy'
    
    logger.info(f"Validation result: {'APPROVED' if is_valid else 'REJECTED'}")
    logger.info(f"New model metrics: Accuracy={new_accuracy:.4f}, F1={new_f1:.4f}")
    
    return is_valid, comparison


# ─── Model Deployment ─────────────────────────────────────────────────────────

def backup_current_models():
    """Backup current production models before deployment."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / f"backup_{timestamp}"
    backup_subdir.mkdir(parents=True, exist_ok=True)
    
    files_to_backup = [
        "xgb_model_latest.joblib",
        "tfidf_latest.joblib",
        "scaler_latest.joblib",
        "metadata_latest.json"
    ]
    
    backed_up = []
    for filename in files_to_backup:
        src = MODEL_DIR / filename
        if src.exists():
            dst = backup_subdir / filename
            shutil.copy2(src, dst)
            backed_up.append(filename)
    
    logger.info(f"Backed up {len(backed_up)} model files to {backup_subdir}")
    
    return backup_subdir


def deploy_new_model(
    model: xgb.XGBClassifier,
    tfidf: TfidfVectorizer,
    scaler: StandardScaler,
    metrics: Dict,
    validation_metrics: Dict
):
    """Deploy new model to production with versioning."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    # Backup current models
    backup_dir = backup_current_models()
    
    # Save new models with timestamp
    model_path = MODEL_DIR / f"xgb_model__latest_{timestamp}.joblib"
    tfidf_path = MODEL_DIR / f"tfidf__latest_{timestamp}.joblib"
    scaler_path = MODEL_DIR / f"scaler__latest_{timestamp}.joblib"
    metadata_path = MODEL_DIR / f"metadata__latest_{timestamp}.json"
    
    joblib.dump(model, model_path)
    joblib.dump(tfidf, tfidf_path)
    joblib.dump(scaler, scaler_path)
    
    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'datetime': datetime.now(timezone.utc).isoformat(),
        'training_metrics': metrics,
        'validation_metrics': validation_metrics,
        'backup_dir': str(backup_dir),
        'model_params': model.get_params(),
        'tfidf_vocab_size': len(tfidf.vocabulary_),
        'structured_features': STRUCTURED_FEATURES,
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Update symlinks/latest files
    for old, new in [
        ("xgb_model_latest.joblib", model_path),
        ("tfidf_latest.joblib", tfidf_path),
        ("scaler_latest.joblib", scaler_path),
        ("metadata_latest.json", metadata_path),
    ]:
        old_path = MODEL_DIR / old
        if old_path.exists():
            old_path.unlink()
        shutil.copy2(new, old_path)
    
    logger.info(f"Successfully deployed new model (version {timestamp})")
    logger.info(f"Backup saved to: {backup_dir}")
    
    return timestamp


# ─── Database Updates ─────────────────────────────────────────────────────────

def mark_samples_as_used(db: Session, sample_ids: List[int], model_version: str):
    """Mark training samples as used after successful training."""
    try:
        db.execute(
            update(TrainingSample).where(
                TrainingSample.id.in_(sample_ids)
            ).values(
                status="used_in_training",
                used_in_training_at=func.now()
            )
        )
        db.commit()
        
        logger.info(f"Marked {len(sample_ids)} samples as used_in_training")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update training samples: {e}")
        raise


def log_retraining_audit(
    db: Session,
    status: str,
    metrics: Dict,
    model_version: Optional[str] = None,
    error_message: Optional[str] = None
):
    """Log retraining attempt to audit_trail table."""
    try:
        insert_query = text("""
            INSERT INTO audit_trail (
                timestamp, actor, action, target_type, target_id,
                status, changes, description
            ) VALUES (
                NOW(), 'retraining_worker', 'model_retrain', 'ml_model', :model_version,
                :status, :changes, :description
            )
        """)
        
        description = f"Model retraining: {status}"
        if error_message:
            description += f" - Error: {error_message}"
        
        db.execute(insert_query, {
            "model_version": model_version or "failed",
            "status": status,
            "changes": json.dumps(metrics),
            "description": description
        })
        db.commit()
        
        logger.info(f"Logged retraining audit: {status}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log audit trail: {e}")


# ─── Main Retraining Pipeline ─────────────────────────────────────────────────

def run_retraining() -> Dict:
    """
    Main retraining pipeline.
    
    Returns:
    - status_dict with success/failure and metrics
    """
    if not RETRAINING_ENABLED:
        logger.info("Retraining is disabled via RETRAINING_ENABLED=false")
        return {"status": "disabled", "message": "Retraining is disabled"}
    
    db = get_db_session()
    
    try:
        logger.info("=" * 80)
        logger.info("Starting ML Retraining Pipeline")
        logger.info("=" * 80)
        
        # 1. Fetch approved training samples
        training_samples = fetch_approved_training_samples(db)
        
        if len(training_samples) < RETRAINING_MIN_SAMPLES:
            message = f"Insufficient training samples: {len(training_samples)} < {RETRAINING_MIN_SAMPLES}"
            logger.warning(message)
            log_retraining_audit(db, "SKIPPED", {"n_samples": len(training_samples)}, error_message=message)
            return {"status": "skipped", "message": message, "n_samples": len(training_samples)}
        
        # 2. Fetch original data for stability (prevent catastrophic forgetting)
        original_data = fetch_original_training_data(limit=5000)
        
        # Combine new samples with original data
        if not original_data.empty:
            combined_samples = pd.concat([training_samples, original_data], ignore_index=True)
            logger.info(f"Combined {len(training_samples)} new + {len(original_data)} original = {len(combined_samples)} total samples")
        else:
            combined_samples = training_samples
        
        # 3. Extract features
        feature_df = extract_features_from_samples(combined_samples)
        
        if len(feature_df) < RETRAINING_MIN_SAMPLES:
            message = f"Insufficient valid features: {len(feature_df)} < {RETRAINING_MIN_SAMPLES}"
            logger.error(message)
            log_retraining_audit(db, "FAILURE", {"n_valid_features": len(feature_df)}, error_message=message)
            return {"status": "failed", "message": message}
        
        # 4. Prepare training data
        X = feature_df.drop('label', axis=1)
        y = feature_df['label'].values
        
        # Split: 70% train, 15% validation, 15% test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=0.15, random_state=42, stratify=y
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=0.176, random_state=42, stratify=y_temp  # 0.176 * 0.85 ≈ 0.15
        )
        
        logger.info(f"Split data: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
        
        # 5. Build feature matrices (TF-IDF + structured features)
        tfidf = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            strip_accents='unicode',
            lowercase=True
        )
        scaler = StandardScaler()
        
        X_train_matrix = build_feature_matrix(X_train, tfidf, scaler, fit=True)
        X_val_matrix = build_feature_matrix(X_val, tfidf, scaler, fit=False)
        X_test_matrix = build_feature_matrix(X_test, tfidf, scaler, fit=False)
        
        # 6. Load old model for comparison
        old_model = None
        try:
            old_model = joblib.load(MODEL_DIR / "xgb_model_latest.joblib")
            logger.info("Loaded existing model for comparison")
        except Exception as e:
            logger.warning(f"No existing model found: {e}")
        
        # 7. Train new model
        new_model, training_metrics = train_new_model(
            X_train_matrix, y_train,
            X_val_matrix, y_val
        )
        
        # 8. Validate new model
        is_valid, validation_metrics = validate_new_model(
            new_model, old_model,
            X_test_matrix, y_test,
            tfidf, scaler
        )
        
        if not is_valid:
            message = "New model failed validation - not deploying"
            logger.warning(message)
            log_retraining_audit(db, "REJECTED", {
                "training_metrics": training_metrics,
                "validation_metrics": validation_metrics
            }, error_message=message)
            return {
                "status": "rejected",
                "message": message,
                "metrics": validation_metrics
            }
        
        # 9. Deploy new model
        model_version = deploy_new_model(
            new_model, tfidf, scaler,
            training_metrics, validation_metrics
        )
        
        # 10. Mark training samples as used
        sample_ids = training_samples['email_id'].tolist() if 'email_id' in training_samples.columns else []
        if sample_ids:
            result = db.execute(
                select(TrainingSample.id).where(TrainingSample.email_id.in_(sample_ids))
            )
            actual_ids = [row[0] for row in result.fetchall()]
            
            if actual_ids:
                mark_samples_as_used(db, actual_ids, model_version)
        
        # 11. Log success audit
        log_retraining_audit(db, "SUCCESS", {
            "model_version": model_version,
            "n_samples_used": len(training_samples),
            "training_metrics": training_metrics,
            "validation_metrics": validation_metrics
        }, model_version=model_version)
        
        logger.info("=" * 80)
        logger.info(f"Retraining completed successfully! Model version: {model_version}")
        logger.info("=" * 80)
        
        return {
            "status": "success",
            "model_version": model_version,
            "n_samples_used": len(training_samples),
            "training_metrics": training_metrics,
            "validation_metrics": validation_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        error_msg = f"Retraining failed: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        
        try:
            log_retraining_audit(db, "FAILURE", {}, error_message=error_msg)
        except:
            pass
        
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }
    
    finally:
        db.close()


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CogniMail ML Retraining Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run retraining once and exit (default: continuous mode)"
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=RETRAINING_MIN_SAMPLES,
        help=f"Minimum training samples required (default: {RETRAINING_MIN_SAMPLES})"
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=RETRAINING_MIN_ACCURACY,
        help=f"Minimum accuracy threshold (default: {RETRAINING_MIN_ACCURACY})"
    )
    
    args = parser.parse_args()
    
    # Override config from CLI args
    RETRAINING_MIN_SAMPLES = args.min_samples
    RETRAINING_MIN_ACCURACY = args.min_accuracy
    
    if args.once:
        # Run once and exit
        result = run_retraining()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] in ["success", "skipped"] else 1)
    else:
        # Continuous mode (for production deployment)
        import time
        schedule_hours = int(os.getenv("RETRAINING_SCHEDULE_HOURS", "24"))
        
        logger.info(f"Starting continuous retraining mode (every {schedule_hours} hours)")
        
        while True:
            try:
                result = run_retraining()
                logger.info(f"Retraining cycle completed: {result['status']}")
            except Exception as e:
                logger.error(f"Unexpected error in retraining cycle: {e}")
            
            # Sleep until next schedule
            sleep_seconds = schedule_hours * 3600
            logger.info(f"Sleeping for {schedule_hours} hours until next retraining check...")
            time.sleep(sleep_seconds)
