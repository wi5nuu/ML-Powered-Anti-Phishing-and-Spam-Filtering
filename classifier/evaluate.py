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

    # ─── Generate HTML report ────────────────────────────────────────────────────────
    from datetime import datetime
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>LTI Anti-Phishing ML Model Evaluation Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f6f9;
            color: #333;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}
        h1 {{
            color: #1a73e8;
            border-bottom: 2px solid #eef2f6;
            padding-bottom: 12px;
            margin-top: 0;
        }}
        h2 {{
            color: #3c4043;
            margin-top: 30px;
            border-left: 4px solid #34a853;
            padding-left: 10px;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
        }}
        .meta-item b {{
            color: #5f6368;
            display: block;
            margin-bottom: 4px;
            font-size: 0.85rem;
            text-transform: uppercase;
        }}
        .meta-item span {{
            font-size: 1.1rem;
            font-weight: 600;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .card {{
            background: #fff;
            border: 1px solid #dadce0;
            padding: 20px;
            border-radius: 6px;
            text-align: center;
        }}
        .card.primary {{
            border-top: 4px solid #1a73e8;
        }}
        .card.success {{
            border-top: 4px solid #34a853;
        }}
        .card.warning {{
            border-top: 4px solid #f29900;
        }}
        .card.danger {{
            border-top: 4px solid #ea4335;
        }}
        .card-val {{
            font-size: 1.8rem;
            font-weight: bold;
            color: #202124;
            margin: 8px 0;
        }}
        .card-label {{
            font-size: 0.85rem;
            color: #70757a;
            text-transform: uppercase;
        }}
        .report-block {{
            background: #202124;
            color: #f1f3f4;
            padding: 20px;
            border-radius: 6px;
            font-family: 'Courier New', Courier, monospace;
            white-space: pre-wrap;
            overflow-x: auto;
            margin-bottom: 30px;
        }}
        .image-container {{
            text-align: center;
            margin: 30px 0;
        }}
        .image-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .footer {{
            margin-top: 50px;
            text-align: center;
            font-size: 0.85rem;
            color: #70757a;
            border-top: 1px solid #eef2f6;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Laporan Evaluasi Model ML Anti-Phishing LTI</h1>
        
        <div class="meta-grid">
            <div class="meta-item">
                <b>Dataset Pengujian</b>
                <span>{test_path}</span>
            </div>
            <div class="meta-item">
                <b>Jumlah Sampel</b>
                <span>{len(df):,}</span>
            </div>
            <div class="meta-item">
                <b>Model Version</b>
                <span>{model_name}</span>
            </div>
            <div class="meta-item">
                <b>Waktu Evaluasi</b>
                <span>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
        </div>

        <h2>Metrik Utama</h2>
        <div class="metrics-grid">
            <div class="card primary">
                <div class="card-label">ROC-AUC Score</div>
                <div class="card-val">{roc_auc:.4f}</div>
            </div>
            <div class="card success">
                <div class="card-label">Average Precision</div>
                <div class="card-val">{avg_prec:.4f}</div>
            </div>
            <div class="card danger">
                <div class="card-label">False Positive Rate</div>
                <div class="card-val">{fpr:.2f}%</div>
            </div>
            <div class="card warning">
                <div class="card-label">False Negative Rate</div>
                <div class="card-val">{fnr:.2f}%</div>
            </div>
        </div>

        <h2>Classification Report</h2>
        <div class="report-block">{report_str}</div>

        <h2>Visualisasi Kinerja</h2>
        <div class="image-container">
            <h3>Confusion Matrix, ROC, & Precision-Recall</h3>
            <img src="evaluation_plots.png" alt="Evaluation Plots">
        </div>

        <div class="footer">
            Sistem Deteksi Anti-Phishing & Spam LTI &bull; Final Project President University (Section 5.4)
        </div>
    </div>
</body>
</html>
"""
    html_path = EVAL_DIR / "evaluation_report.html"
    with open(html_path, "w") as f:
        f.write(html_content)
    logger.info("HTML evaluation report saved to %s", html_path)

    return metrics


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    test_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/test.csv"
    evaluate(test_path)
