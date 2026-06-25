"""
Model Drift Detection — Monitor model performance over time.
Detects data drift (feature distribution change) and concept drift (accuracy degradation).

Usage: python scripts/drift_monitor.py [--check]
"""

import argparse
import json
import os
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from scipy.stats import ks_2samp

from database.models import QuarantineEmail, Feedback, PipelineMetrics

DB_URL = os.getenv("DB_URL", "sqlite:///./lti_antiphishing.db")
DRIFT_REPORT_DIR = Path("reports/drift")
DRIFT_REPORT_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def check_data_drift(reference_data: list, current_data: list, feature_names: list, threshold: float = 0.05):
    """Check for data drift using Kolmogorov-Smirnov test."""
    drifted_features = []
    for i, name in enumerate(feature_names):
        if i < len(reference_data[0]) and i < len(current_data[0]):
            ref_vals = [row[i] for row in reference_data if row[i] is not None]
            cur_vals = [row[i] for row in current_data if row[i] is not None]
            if len(ref_vals) > 5 and len(cur_vals) > 5:
                stat, p_value = ks_2samp(ref_vals, cur_vals)
                if p_value < threshold:
                    drifted_features.append({
                        "feature": name,
                        "ks_stat": round(stat, 4),
                        "p_value": round(p_value, 4),
                        "drift_detected": True,
                    })
    return drifted_features


def check_concept_drift(recent_days: int = 7, baseline_days: int = 30,
                        precision_threshold: float = 0.80):
    """Check concept drift by comparing recent vs baseline precision."""
    db = SessionLocal()

    baseline_since = datetime.utcnow() - timedelta(days=baseline_days)
    recent_since = datetime.utcnow() - timedelta(days=recent_days)

    total_recent = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.created_at >= recent_since
    ).scalar() or 0

    fp_recent = db.query(func.count(Feedback.id)).filter(
        Feedback.created_at >= recent_since,
        Feedback.feedback_type == "false_positive"
    ).scalar() or 0

    total_baseline = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.created_at >= baseline_since,
        QuarantineEmail.created_at < recent_since
    ).scalar() or 0

    fp_baseline = db.query(func.count(Feedback.id)).filter(
        Feedback.created_at >= baseline_since,
        Feedback.created_at < recent_since,
        Feedback.feedback_type == "false_positive"
    ).scalar() or 0

    db.close()

    recent_precision = 1.0 - (fp_recent / max(total_recent, 1))
    baseline_precision = 1.0 - (fp_baseline / max(total_baseline, 1))

    drift_detected = recent_precision < precision_threshold
    degradation = baseline_precision - recent_precision

    return {
        "drift_detected": drift_detected,
        "baseline_precision": round(baseline_precision, 4),
        "recent_precision": round(recent_precision, 4),
        "degradation": round(degradation, 4),
        "baseline_period_days": baseline_days,
        "recent_period_days": recent_days,
        "recommendation": "Retraining recommended" if drift_detected else "Model is stable",
    }


def run_full_check():
    """Run full drift detection and save report."""
    # Concept drift check
    concept = check_concept_drift()

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "concept_drift": concept,
        "recommendation": concept["recommendation"],
    }

    report_path = DRIFT_REPORT_DIR / f"drift_report_{datetime.utcnow().date()}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Drift report saved: {report_path}")
    print(f"  Baseline precision: {concept['baseline_precision']:.4f}")
    print(f"  Recent precision:   {concept['recent_precision']:.4f}")
    print(f"  Degradation:        {concept['degradation']:.4f}")
    print(f"  Status:             {concept['recommendation']}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model drift detection")
    parser.add_argument("--check", action="store_true", help="Run full drift check")
    args = parser.parse_args()
    run_full_check()
