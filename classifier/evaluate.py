"""
Evaluation module — menghasilkan laporan metrik dari model yang sudah di-train.

Output: confusion matrix, ROC curve, precision-recall curve, SHAP summary plot.
"""

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve, precision_recall_curve,
    average_precision_score, ConfusionMatrixDisplay
)

from classifier.features import STRUCTURED_FEATURES
from classifier.train import build_feature_matrix

logger = logging.getLogger(__name__)

MODEL_DIR = Path("classifier/models")
EVAL_DIR  = Path("docs/evidence")
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def evaluate(test_path: str, model_name: str = "latest"):
    logger.info("Loading model artifacts...")
    model  = joblib.load(MODEL_DIR / f"xgb_model_{model_name}.joblib")
    tfidf  = joblib.load(MODEL_DIR / f"tfidf_{model_name}.joblib")
    scaler = joblib.load(MODEL_DIR / f"scaler_{model_name}.joblib")

    logger.info("Loading test set dari %s", test_path)
    df = pd.read_csv(test_path)

    required_cols = ["combined_text", "label"] + STRUCTURED_FEATURES
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom tidak ditemukan: {missing}")

    X = build_feature_matrix(df, tfidf, scaler, fit=False)
    y_true = df["label"]

    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]

    roc_auc  = roc_auc_score(y_true, y_prob)
    avg_prec = average_precision_score(y_true, y_prob)
    cm = confusion_matrix(y_true, y_pred)
    report_str = classification_report(y_true, y_pred, target_names=["ham", "spam"])

    logger.info("\n%s", report_str)
    logger.info("ROC-AUC: %.4f | Avg Precision: %.4f", roc_auc, avg_prec)

    tn, fp, fn, tp = cm.ravel()
    fpr = fp / max(fp + tn, 1) * 100
    fnr = fn / max(fn + tp, 1) * 100
    logger.info("TP=%d  FP=%d  FN=%d  TN=%d", tp, fp, fn, tn)
    logger.info("False Positive Rate: %.2f%%", fpr)
    logger.info("False Negative Rate: %.2f%%", fnr)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    ConfusionMatrixDisplay(cm, display_labels=["ham", "spam"]).plot(ax=axes[0])
    axes[0].set_title("Confusion Matrix")

    fpr_roc, tpr_roc, _ = roc_curve(y_true, y_prob)
    axes[1].plot(fpr_roc, tpr_roc, label=f"ROC-AUC = {roc_auc:.4f}")
    axes[1].plot([0, 1], [0, 1], "k--", alpha=0.3)
    axes[1].set_xlabel("False Positive Rate")
    axes[1].set_ylabel("True Positive Rate")
    axes[1].set_title("ROC Curve")
    axes[1].legend()

    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    axes[2].plot(recall, precision, label=f"Avg Precision = {avg_prec:.4f}")
    axes[2].set_xlabel("Recall")
    axes[2].set_ylabel("Precision")
    axes[2].set_title("Precision-Recall Curve")
    axes[2].legend()

    plt.tight_layout()
    plot_path = EVAL_DIR / "evaluation_plots.png"
    plt.savefig(plot_path, dpi=150)
    logger.info("Plots saved to %s", plot_path)

    cm_path = EVAL_DIR / "confusion_matrix.png"
    fig_cm, ax_cm = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay(cm, display_labels=["ham", "spam"]).plot(ax=ax_cm)
    ax_cm.set_title("Confusion Matrix - LTI Anti-Phishing")
    fig_cm.tight_layout()
    fig_cm.savefig(cm_path, dpi=150)

    metrics = {
        "test_set": test_path,
        "samples": len(df),
        "roc_auc": round(roc_auc, 4),
        "avg_precision": round(avg_prec, 4),
        "confusion_matrix": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
        "false_positive_rate_pct": round(fpr, 2),
        "false_negative_rate_pct": round(fnr, 2),
        "classification_report": report_str,
    }

    metrics_path = EVAL_DIR / "evaluation_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Metrics saved to %s", metrics_path)

    return metrics


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    test_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/test.csv"
    evaluate(test_path)
