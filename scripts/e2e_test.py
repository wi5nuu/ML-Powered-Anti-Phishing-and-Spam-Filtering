"""
End-to-end Dataset Test
=======================
1. Extract features from .eml files → training CSV
2. Train XGBoost model
3. Start classifier API
4. Test with bulk_test.py

Usage: python scripts/e2e_test.py
"""

import csv
import os
import hashlib
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES
from scripts.dataset_config import get_dataset_dir, FOLDER_NAMES, get_training_csv_path

# Pilih dataset
DATASET_NAME = os.environ.get("ACTIVE_DATASET", "dataset_1")
DATASET_DIR = get_dataset_dir(DATASET_NAME)
OUTPUT_CSV = get_training_csv_path(DATASET_NAME)
MODEL_DIR = Path("classifier/models")

logger.info("Dataset: %s -> %s", DATASET_NAME, DATASET_DIR)

# ─── Step 1: Extract features from .eml files ───────────────────────────

def extract_features(eml_path: Path) -> dict:
    """Extract structured + text features from one .eml file."""
    parser = EmailParser()
    extractor = FeatureExtractor()
    raw = eml_path.read_text(encoding="utf-8", errors="replace")
    parsed = parser.parse(raw)
    features = extractor.extract(parsed)
    row = {
        "combined_text": features.combined_text,
        "filepath": str(eml_path),
    }
    for f in STRUCTURED_FEATURES:
        row[f] = getattr(features, f, 0)
    return row

def build_full_training_csv():
    """Build training CSV from ALL 15k emails in dataset."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []

    for folder, label in [("chris", "ham"), ("ilham", "ham"), ("brian", "spam"),
                          ("wisnu", "phishing"), ("risly", "malware")]:
        folder_path = DATASET_DIR / folder
        files = sorted(folder_path.rglob("*.eml"))
        bin_label = 0 if label == "ham" else 1
        logger.info("Extracting %d files from %s...", len(files), folder)

        for i, f in enumerate(files):
            try:
                row = extract_features(f)
                row["label"] = bin_label
                row["class_label"] = label
                all_rows.append(row)
                if (i + 1) % 1000 == 0:
                    logger.info("  %s: %d/%d", folder, i + 1, len(files))
            except Exception as e:
                logger.warning("  Error extracting %s: %s", f.name, e)

    # Write CSV
    fieldnames = ["combined_text", "label", "class_label", "filepath"] + STRUCTURED_FEATURES
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    ham_count = sum(1 for r in all_rows if r["label"] == 0)
    threat_count = sum(1 for r in all_rows if r["label"] == 1)
    logger.info("Written %d rows to %s", len(all_rows), OUTPUT_CSV)
    logger.info("Distribution: ham=%d, threat=%d", ham_count, threat_count)
    return OUTPUT_CSV


def build_training_csv(samples_per_class: int = 150):
    """Build balanced training CSV from dataset."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Get files per category
    categories = {
        "ham": [],
        "spam": [],
        "phishing": [],
        "malware": [],
    }

    for folder, label in [("chris", "ham"), ("ilham", "ham"), ("brian", "spam"),
                          ("wisnu", "phishing"), ("risly", "malware")]:
        folder_path = DATASET_DIR / folder
        files = sorted(folder_path.rglob("*.eml"))
        # Distribute samples: 50/50 between chris & ilham for ham
        if label == "ham":
            categories[label].extend(files[:samples_per_class // 2])  # first half from first folder
            categories[label].extend(files[samples_per_class // 2: samples_per_class])  # from next folder
        else:
            categories[label].extend(files[:samples_per_class])

    # Flatten & shuffle
    import random
    all_rows = []
    for label, files in categories.items():
        bin_label = 0 if label == "ham" else 1
        random.shuffle(files)

        for i, f in enumerate(files):
            if i >= samples_per_class:
                break
            try:
                row = extract_features(f)
                row["label"] = bin_label
                row["class_label"] = label
                all_rows.append(row)
                if (i + 1) % 50 == 0:
                    logger.info("  %s: %d/%d extracted", label, i + 1, min(len(files), samples_per_class))
            except Exception as e:
                logger.warning("  Error extracting %s: %s", f.name, e)

    # Write CSV
    fieldnames = ["combined_text", "label", "class_label", "filepath"] + STRUCTURED_FEATURES
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info("Written %d rows to %s", len(all_rows), OUTPUT_CSV)

    # Print distribution
    ham_count = sum(1 for r in all_rows if r["label"] == 0)
    spam_count = sum(1 for r in all_rows if r["label"] == 1)
    logger.info("Distribution: ham=%d, spam/threat=%d", ham_count, spam_count)

    return OUTPUT_CSV


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("STEP 1: Build FULL training CSV from ALL .eml files")
    logger.info("=" * 60)
    csv_path = build_full_training_csv()

    logger.info("\n" + "=" * 60)
    logger.info("DONE. Full training CSV: %s", csv_path)
    logger.info("=" * 60)
