"""
Dataset Configuration
=====================
Gunakan environment variable ACTIVE_DATASET atau ubah DEFAULT_DATASET di sini.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent / ".."

# Default: dataset_merged (100.000 email dari Enron + Dataset1 + Extended)
# Opsi lain: "dataset_1" (15.029), "dataset_2" (model artifacts)
DEFAULT_DATASET = "dataset_merged"

def get_active_dataset() -> str:
    """Kembalikan nama folder dataset yang aktif."""
    return os.environ.get("ACTIVE_DATASET", DEFAULT_DATASET)

def get_dataset_dir(dataset_name: str = None) -> Path:
    """Kembalikan Path ke folder dataset."""
    name = dataset_name or get_active_dataset()
    return ROOT / "data" / name

def get_dataset_path(*subdirs: str, dataset_name: str = None) -> Path:
    return get_dataset_dir(dataset_name).joinpath(*subdirs)

def get_metadata_path(dataset_name: str = None) -> Path:
    """Path ke metadata CSV dataset."""
    return get_dataset_dir(dataset_name) / "metadata.csv"

def get_training_csv_path(dataset_name: str = None) -> Path:
    """Path ke training CSV hasil ekstraksi fitur."""
    name = dataset_name or get_active_dataset()
    return ROOT / "data" / "processed" / f"train_{name}.csv"


# ─── Label mapping ─────────────────────────────────────────────────
FOLDER_LABELS = {
    # Dataset 1
    "chris": ("ham", "transaksi_cs"),
    "ilham": ("ham", "internal_b2b"),
    "brian": ("spam", "spam"),
    "wisnu": ("phishing", "phishing"),
    "risly": ("malware", "malware"),
    # Extended
    "transaksi": ("ham", "transaction"),
    "cs": ("ham", "customer_service"),
    "internal": ("ham", "internal_b2b"),
    "spam": ("spam", "spam"),
    "phishing": ("phishing", "phishing"),
    "malware": ("malware", "malware"),
    "bec": ("phishing", "bec"),
    # Enron
    "enron1_ham": ("ham", "enron_ham"),
    "enron1_spam": ("spam", "enron_spam"),
    "enron2_ham": ("ham", "enron_ham"),
    "enron2_spam": ("spam", "enron_spam"),
}

FOLDER_NAMES = list(FOLDER_LABELS.keys())

# ─── Sample emails untuk testing ────────────────────────────────────
SAMPLE_EMAILS = {
    "ham_transaksi":  "_dataset1/chris/chris_0001_8ca553d955a0bf88.eml",
    "ham_internal":   "_dataset1/ilham/ilham_0001_9fefa4942adca243.eml",
    "spam_promo":     "_dataset1/brian/brian_0001_316e50a87d13354c.eml",
    "phishing_akun":  "_dataset1/wisnu/wisnu_0001_b0d875c197e282ac.eml",
    "malware_invoice":"_dataset1/risly/risly_0001_004807eea4750c9d.eml",
    "bec_fraud":      "_extended/bec/bec_0001_*.eml",
    "enron_ham":      "_enron/enron1_ham/0001*.eml",
    "enron_spam":     "_enron/enron1_spam/0001*.eml",
}
