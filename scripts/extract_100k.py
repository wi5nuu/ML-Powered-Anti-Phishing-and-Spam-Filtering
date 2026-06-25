"""
Extract features from 100k merged emails → training CSV.

Reads metadata.csv from dataset_merged, parses each .eml via
classifier.features, and writes data/processed/train_100k.csv
compatible with classifier/train.py.

Usage:
  python scripts/extract_100k.py
  python scripts/extract_100k.py --sample 5000   # quick test
"""

import sys
import csv
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def extract(sample: int = 0):
    merged_dir = Path("data/dataset_merged")
    meta_path = merged_dir / "metadata.csv"
    if not meta_path.exists():
        logger.error("metadata.csv not found at %s", meta_path)
        sys.exit(1)

    df = pd.read_csv(meta_path)
    if sample:
        df = df.sample(n=min(sample, len(df)), random_state=42)
        logger.info("SAMPLED %d rows from %d total", sample, len(df))

    logger.info("Loading metadata: %d rows", len(df))

    parser = EmailParser()
    extractor = FeatureExtractor()

    rows = []
    errors = 0
    t0 = time.time()

    for i, row in df.iterrows():
        fpath = merged_dir / row["filename"]
        if not fpath.exists():
            # Try flat filename
            fpath2 = merged_dir / row["filename"].split("/", 1)[-1]
            if not fpath2.exists():
                errors += 1
                if errors <= 5:
                    logger.warning("File not found: %s", row["filename"])
                continue
            fpath = fpath2
        try:
            raw = fpath.read_text(encoding="utf-8", errors="replace")
            parsed = parser.parse(raw)
            feats = extractor.extract(parsed)
            feat_dict = {f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES}
            feat_dict["combined_text"] = feats.combined_text
            feat_dict["label"] = 0 if row["label"] == "ham" else 1
            feat_dict["category"] = row.get("category", "")
            feat_dict["origin"] = row.get("origin", "")
            rows.append(feat_dict)
        except Exception as e:
            errors += 1
            if errors <= 10:
                logger.warning("Error processing %s: %s", row["filename"], e)

        if (i + 1) % 5000 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            logger.info("  %d/%d (%.1f%%) | %.0f files/sec",
                        i + 1, len(df), (i + 1) / len(df) * 100, rate)

    out_df = pd.DataFrame(rows)
    csv_path = PROCESSED_DIR / "train_100k.csv"
    out_df.to_csv(csv_path, index=False)
    elapsed = time.time() - t0

    logger.info("=" * 50)
    logger.info("EXTRACTION COMPLETE")
    logger.info("Files processed: %d | Errors: %d | %.1f sec | %.0f files/sec",
                len(out_df), errors, elapsed, len(out_df) / elapsed if elapsed > 0 else 0)
    logger.info("Output: %s (%.1f MB)", csv_path, csv_path.stat().st_size / (1024 * 1024))
    logger.info("Label distribution:\n%s", out_df["label"].value_counts().to_string())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0,
                        help="Extract only N samples for testing")
    args = parser.parse_args()
    extract(args.sample)
