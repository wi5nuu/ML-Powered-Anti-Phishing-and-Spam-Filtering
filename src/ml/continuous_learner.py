"""
Continuous Learning Module — CogniMail Enterprise Edition.

Feedback ingestion, semi-supervised learning, model versioning & rollback,
and performance tracking over time.

Architecture:
  1. Feedback Ingestion  — collect labeled data from user actions (report spam/phishing/clean)
  2. Semi-Supervised     — use pseudo-labeling to expand training set from unlabeled data
  3. Model Versioning    — track every retrain cycle with versioned artifacts and rollback
  4. Performance Tracking — monitor accuracy drift, precision, recall, F1 over time
"""

import datetime
import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from classifier.features import (
    EmailParser, FeatureExtractor, STRUCTURED_FEATURES,
)
from classifier.inference_matrix import build_feature_matrix
from classifier.unsupervised import UNSUPERVISED_FEATURES

logger = structlog.get_logger()

# ─── Paths & Constants ───────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = ROOT_DIR / "classifier" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'cognimail.db'}")

# Confidence threshold for pseudo-labeling (semi-supervised)
PSEUDO_LABEL_CONFIDENCE = float(os.getenv("PSEUDO_LABEL_CONFIDENCE", "0.85"))

# Minimum samples to trigger retrain
MIN_RETRAIN_SAMPLES = int(os.getenv("MIN_RETRAIN_SAMPLES", "100"))

# ─── Data Classes ────────────────────────────────────────────────────────────


@dataclass
class FeedbackSample:
    """A single feedback sample collected from user action."""
    email_id: str
    raw_email: str
    subject: str
    sender: str
    label: str                    # "spam", "phishing", "clean", "malware"
    source: str                   # "user", "admin", "auto"
    ml_probability: float = 0.0
    anomaly_score: float = 0.0
    fused_score: float = 0.0
    user_feedback: str = ""       # "confirmed_spam", "false_positive", "confirmed_clean"
    features: dict = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class ModelMetrics:
    """Performance metrics for a trained model."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    n_samples: int = 0
    n_features: int = 0
    training_time_s: float = 0.0
    confusion_matrix: list = field(default_factory=list)
    timestamp: str = ""


@dataclass
class RetrainReport:
    """Report generated after a full retrain cycle."""
    run_id: str = ""
    xgb_before: ModelMetrics = field(default_factory=ModelMetrics)
    xgb_after: ModelMetrics = field(default_factory=ModelMetrics)
    anomaly_before: dict = field(default_factory=dict)
    anomaly_after: dict = field(default_factory=dict)
    n_samples_supervised: int = 0
    n_samples_unsupervised: int = 0
    status: str = "completed"
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

# ─── Continuous Learner ──────────────────────────────────────────────────────


class ContinuousLearner:
    """Main continuous learning orchestrator.

    Handles feedback ingestion, semi-supervised expansion, model retraining,
    versioning, rollback, and performance tracking.
    """

    def __init__(self, db_url: str = DEFAULT_DB_URL, model_dir: Path = MODEL_DIR):
        self.db_url = db_url
        self.model_dir = model_dir
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        )
        self._xgb_model = None
        self._tfidf = None
        self._scaler = None
        self._anomaly = None

    # ── Feedback Ingestion ──────────────────────────────────────────────────

    def ingest_feedback(self, sample: FeedbackSample) -> bool:
        """Ingest a single feedback sample into the training_data table.

        Args:
            sample: FeedbackSample with email data and user label.

        Returns:
            True if successfully ingested, False otherwise.
        """
        try:
            features = sample.features or self._extract_features(sample.raw_email)
            feature_vector = json.dumps([features.get(f, 0) for f in UNSUPERVISED_FEATURES])

            with Session(self.engine) as session:
                existing = session.execute(
                    text("SELECT id FROM training_data WHERE email_id = :eid"),
                    {"eid": sample.email_id},
                ).fetchone()

                if existing:
                    session.execute(
                        text("""
                            UPDATE training_data
                            SET label = :label, user_feedback = :feedback,
                                source = :source, used_in_retrain = :used
                            WHERE email_id = :eid
                        """),
                        {
                            "label": sample.label,
                            "feedback": sample.user_feedback,
                            "source": sample.source,
                            "used": False,
                            "eid": sample.email_id,
                        },
                    )
                    logger.info("feedback_updated", email_id=sample.email_id, label=sample.label)
                else:
                    session.execute(
                        text("""
                            INSERT INTO training_data
                                (email_id, raw_email, subject, sender, label, source,
                                 features_json, feature_vector, ml_probability,
                                 anomaly_score, fused_score, user_feedback,
                                 created_at, used_in_retrain)
                            VALUES
                                (:eid, :raw, :subj, :sender, :label, :source,
                                 :fjson, :fvec, :mlprob,
                                 :anom, :fused, :fb,
                                 :now, :used)
                        """),
                        {
                            "eid": sample.email_id,
                            "raw": sample.raw_email,
                            "subj": sample.subject,
                            "sender": sample.sender,
                            "label": sample.label,
                            "source": sample.source,
                            "fjson": json.dumps(features),
                            "fvec": feature_vector,
                            "mlprob": sample.ml_probability,
                            "anom": sample.anomaly_score,
                            "fused": sample.fused_score,
                            "fb": sample.user_feedback,
                            "now": datetime.datetime.utcnow(),
                            "used": False,
                        },
                    )
                    logger.info("feedback_ingested", email_id=sample.email_id, label=sample.label)

                session.commit()
            return True

        except Exception as e:
            logger.error("feedback_ingestion_error", email_id=sample.email_id, error=str(e))
            return False

    def ingest_batch(self, samples: list[FeedbackSample]) -> dict:
        """Ingest multiple feedback samples.

        Args:
            samples: List of FeedbackSample objects.

        Returns:
            Dict with counts of successful and failed ingestions.
        """
        success = 0
        failed = 0
        for sample in samples:
            if self.ingest_feedback(sample):
                success += 1
            else:
                failed += 1
        logger.info("batch_feedback_ingested", success=success, failed=failed)
        return {"success": success, "failed": failed}


    # ── Semi-Supervised Learning ────────────────────────────────────────────

    def expand_with_pseudo_labels(self, confidence_threshold: float = PSEUDO_LABEL_CONFIDENCE) -> int:
        """Use the current supervised model to pseudo-label high-confidence
        unlabeled emails from the quarantine table, then add them to training_data.

        This semi-supervised approach grows the training set automatically.

        Args:
            confidence_threshold: Minimum ML probability to accept pseudo-label.

        Returns:
            Number of pseudo-labeled samples added.
        """
        try:
            self._load_supervised_models()
            if self._xgb_model is None:
                logger.warning("pseudo_label_skipped", reason="No supervised model loaded")
                return 0

            with Session(self.engine) as session:
                rows = session.execute(
                    text("""
                        SELECT q.email_id, q.raw_content, q.subject, q.sender,
                               q.ml_probability, q.anomaly_score, q.fused_score,
                               q.label, q.category
                        FROM quarantine_emails q
                        WHERE q.email_id NOT IN (
                            SELECT email_id FROM training_data
                        )
                        AND q.raw_content IS NOT NULL AND q.raw_content != ''
                        LIMIT 1000
                    """)
                ).fetchall()

            pseudo_count = 0
            parser = EmailParser()
            extractor = FeatureExtractor()

            for row in rows:
                try:
                    raw_email = row.raw_content or ""
                    email_id = row.email_id
                    parsed = parser.parse(raw_email)
                    features = extractor.extract(parsed)
                    feat_dict = {f: getattr(features, f, 0) for f in STRUCTURED_FEATURES}

                    df = pd.DataFrame([{
                        **feat_dict,
                        "combined_text": features.combined_text,
                    }])
                    X = build_feature_matrix(df, self._tfidf, self._scaler, fit=False)
                    proba = self._xgb_model.predict_proba(X)[0][1]

                    if proba >= confidence_threshold:
                        label = "spam"
                    elif proba <= (1.0 - confidence_threshold):
                        label = "clean"
                    else:
                        continue

                    fb = FeedbackSample(
                        email_id=email_id,
                        raw_email=raw_email,
                        subject=row.subject or "",
                        sender=row.sender or "",
                        label=label,
                        source="auto",
                        ml_probability=float(proba),
                        anomaly_score=float(row.anomaly_score or 0.0),
                        fused_score=float(row.fused_score or 0.0),
                        user_feedback="pseudo_labeled",
                        features=feat_dict,
                        timestamp=datetime.datetime.utcnow().isoformat(),
                    )
                    if self.ingest_feedback(fb):
                        pseudo_count += 1

                except Exception as e:
                    logger.debug("pseudo_label_skip", email_id=row.email_id, error=str(e))
                    continue

            logger.info("pseudo_labeling_complete", added=pseudo_count, threshold=confidence_threshold)
            return pseudo_count

        except Exception as e:
            logger.error("pseudo_labeling_error", error=str(e))
            return 0

