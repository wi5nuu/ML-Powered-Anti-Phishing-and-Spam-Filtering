"""
Build metadata.csv + training CSV for dataset_merged (100,000 emails).

Maps each subfolder to a label and generates:
  data/dataset_merged/metadata.csv
  data/dataset_merged/training_data.csv (for train.py compatibility)

The merged dataset has the structure:
  _enron/enron1_ham/     -> ham
  _enron/enron1_spam/    -> spam
  _enron/enron2_ham/     -> ham
  _enron/enron2_spam/    -> spam
  _dataset1/chris/       -> transaction (ham)
  _dataset1/ilham/       -> internal_b2b (ham)
  _dataset1/brian/       -> spam
  _dataset1/wisnu/       -> phishing
  _dataset1/risly/       -> malware
  _extended/transaksi/   -> ham
  _extended/cs/          -> ham
  _extended/internal/    -> ham
  _extended/spam/        -> spam
  _extended/phishing/    -> phishing
  _extended/malware/     -> malware
  _extended/bec/         -> phishing (BEC is a phishing subtype)
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path

# Mapping: subfolder -> (label, origin, category)
FOLDER_MAP = {
    "enron1_ham":    ("ham",      "enron", "enron_ham"),
    "enron1_spam":   ("spam",     "enron", "enron_spam"),
    "enron2_ham":    ("ham",      "enron", "enron_ham"),
    "enron2_spam":   ("spam",     "enron", "enron_spam"),
    "chris":         ("ham",      "dataset1", "transaction"),
    "ilham":         ("ham",      "dataset1", "internal_b2b"),
    "brian":         ("spam",     "dataset1", "spam"),
    "wisnu":         ("phishing", "dataset1", "phishing"),
    "risly":         ("malware",  "dataset1", "malware"),
    "transaksi":     ("ham",      "extended", "transaction"),
    "cs":            ("ham",      "extended", "customer_service"),
    "internal":      ("ham",      "extended", "internal_b2b"),
    "spam":          ("spam",     "extended", "spam"),
    "phishing":      ("phishing", "extended", "phishing"),
    "malware":       ("malware",  "extended", "malware"),
    "bec":           ("phishing", "extended", "bec"),
}


# Known leaf directories (subfolder, label, origin, category)
LEAF_DIRS = [
    ("_enron/enron1_ham",    "ham",      "enron",    "enron_ham"),
    ("_enron/enron1_spam",   "spam",     "enron",    "enron_spam"),
    ("_enron/enron2_ham",    "ham",      "enron",    "enron_ham"),
    ("_enron/enron2_spam",   "spam",     "enron",    "enron_spam"),
    ("_dataset1/chris",      "ham",      "dataset1", "transaction"),
    ("_dataset1/ilham",      "ham",      "dataset1", "internal_b2b"),
    ("_dataset1/brian",      "spam",     "dataset1", "spam"),
    ("_dataset1/wisnu",      "phishing", "dataset1", "phishing"),
    ("_dataset1/risly",      "malware",  "dataset1", "malware"),
    ("_extended/transaksi",  "ham",      "extended", "transaction"),
    ("_extended/cs",         "ham",      "extended", "customer_service"),
    ("_extended/internal",   "ham",      "extended", "internal_b2b"),
    ("_extended/spam",       "spam",     "extended", "spam"),
    ("_extended/phishing",   "phishing", "extended", "phishing"),
    ("_extended/malware",    "malware",  "extended", "malware"),
    ("_extended/bec",        "phishing", "extended", "bec"),
    ("_extended/casual_ham", "ham",      "extended", "casual_ham"),
]


def build_metadata(merged_dir: str):
    merged = Path(merged_dir)
    metadata_path = merged / "metadata.csv"
    training_path = merged / "training_data.csv"
    rows = []
    file_id = 0

    for subfolder, label, origin, category in LEAF_DIRS:
        subdir = merged / subfolder
        if not subdir.exists():
            print(f"  WARNING: '{subfolder}' not found, skipping")
            continue
        for fpath in sorted(subdir.iterdir()):
            if not fpath.is_file() or not fpath.suffix.lower() in (".eml", ".txt"):
                continue
            content = fpath.read_text(encoding="utf-8", errors="replace")
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            rel_path = f"{subfolder}/{fpath.name}"
            file_id += 1
            rows.append({
                "id": file_id,
                "filename": rel_path,
                "full_path": str(fpath.absolute()),
                "label": label,
                "origin": origin,
                "category": category,
                "sha256": content_hash,
            })

    # Write metadata.csv
    fieldnames = ["id", "filename", "full_path", "label", "origin", "category", "sha256"]
    with open(metadata_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Write training_data.csv (compatible with train.py's expected format)
    # train.py reads: filename (relative), label (0/1), category
    with open(training_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "label", "category"])
        for r in rows:
            label_int = 0 if r["label"] == "ham" else 1
            writer.writerow([r["filename"], label_int, r["category"]])

    print(f"Metadata written: {metadata_path}")
    print(f"  Rows: {len(rows)}")
    print(f"Training CSV: {training_path}")
    print(f"  Rows: {len(rows)}")

    # Print summary
    labels = {}
    for r in rows:
        labels[r["label"]] = labels.get(r["label"], 0) + 1
    print(f"\nLabel distribution:")
    for k, v in sorted(labels.items()):
        print(f"  {k}: {v}")
    print(f"\nOrigin distribution:")
    origins = {}
    for r in rows:
        origins[r["origin"]] = origins.get(r["origin"], 0) + 1
    for k, v in sorted(origins.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build merged dataset metadata")
    parser.add_argument("--merged", default="data/dataset_merged",
                        help="Merged dataset directory")
    args = parser.parse_args()
    build_metadata(args.merged)
