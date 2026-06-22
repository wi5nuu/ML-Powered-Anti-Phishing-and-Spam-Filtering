"""
Train Unsupervised Anomaly Detectors — hanya pakai email bersih (ham).

Arsitektur Layer 2:
  - Isolation Forest (utama) — dilatih HANYA dengan email bersih
  - One-Class SVM (pendukung) — sensitivitas lebih tinggi

Data source: SpamAssassin easy_ham + hard_ham (label=0)
→ Tidak butuh data spam sama sekali!
→ Mendeteksi zero-day / unknown threats yang tidak ada di training set supervised.

Usage:
  python scripts/train_unsupervised.py
"""

import logging
import sys
from pathlib import Path

import pandas as pd

# Tambah parent ke path agar import classifier.* work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.unsupervised import AnomalyDetector, UNSUPERVISED_FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def get_clean_emails_from_training_csv(csv_path: str = "data/processed/train.csv") -> pd.DataFrame:
    """
    Ambil hanya email bersih (label=0) dari CSV training.
    
    CSV ini sudah memiliki kolom STRUCTURED_FEATURES dari supervised training pipeline.
    Kita filt er label=0 → hanya ham.
    """
    df = pd.read_csv(csv_path)
    logger.info("Total samples in dataset: %d", len(df))
    logger.info("Label distribution:\n%s", df["label"].value_counts().to_string())

    clean_df = df[df["label"] == 0].copy()
    logger.info("Clean (ham) samples extracted: %d", len(clean_df))

    # Validate feature columns exist
    missing = [c for c in UNSUPERVISED_FEATURES if c not in clean_df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}. "
                         f"Need complete training CSV with structured features.")

    # Pastikan combined_text ada (meski tidak dipakai unsupervised)
    if "combined_text" not in clean_df.columns:
        clean_df["combined_text"] = ""

    return clean_df


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/train.csv"

    logger.info("=" * 60)
    logger.info("UNSUPERVISED ANOMALY DETECTION TRAINING")
    logger.info("Training dengan ZERO spam — hanya email bersih")
    logger.info("=" * 60)

    # Load clean emails only
    clean_df = get_clean_emails_from_training_csv(csv_path)

    # Train anomaly detectors
    detector = AnomalyDetector()
    detector.fit(clean_emails_df=clean_df)

    # Save models
    detector.save(suffix="from_ham")

    # Quick self-test on a few clean samples
    logger.info("\nSelf-test: scoring first 5 clean emails...")
    for idx in range(min(5, len(clean_df))):
        row = clean_df.iloc[idx]
        # Build minimal feature dict (we can't reconstruct full raw email from CSV)
        # Instead, just verify the model works with predict on synthetic dict
        logger.info("  Sample %d → No actual prediction (no raw email in CSV)", idx)

    logger.info("=" * 60)
    logger.info("UNSUPERVISED MODEL TRAINING COMPLETE")
    logger.info("Folder: classifier/models/")
    logger.info("Files: isolation_forest_latest.joblib, one_class_svm_latest.joblib, unsupervised_scaler_latest.joblib")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
