"""
Dataset Category Validation
===========================
Memeriksa apakah setiap folder berisi email yang sesuai dengan kategorinya.
Menggunakan keyword analysis + signature detection.

Output: Laporan per folder + confussion matrix
"""

import os
import re
import sys
from pathlib import Path
from collections import Counter

from scripts.dataset_config import get_dataset_dir, FOLDER_NAMES

# Pilih dataset: set env ACTIVE_DATASET atau ubah di sini
DATASET_NAME = os.environ.get("ACTIVE_DATASET", "dataset_1")
DATASET_DIR = get_dataset_dir(DATASET_NAME)
FOLDERS = FOLDER_NAMES

print(f"Memvalidasi dataset: {DATASET_NAME}")
print(f"  Path: {DATASET_DIR}")

# ─── Signatures per category ──────────────────────────────────────────────

SIGNATURES = {
    "chris": {
        "label": "ham — transaksi & customer service",
        "keywords": {
            "must": [
                r"pembayaran|transfer|transaksi|invoice|receipt|payment",
                r"tiket|ticket|support|cs|customer service|keluhan",
                r"Rp\s*[\d.,]+",         # Rupiah amounts
            ],
            "should_not": [
                r"menang|undian|prize|winner",
                r"verifikasi.*akun|account.*verify",
                r".exe\b|\.vbs\b|\.docm\b",
                r"bit\.ly|tinyurl\.com",
            ],
            "expected": {
                "transaction_indicators": 0.5,   # at least 50% should have payment keywords
                "cs_ticket_indicators": 0.3,     # at least 30% should have ticket keywords
            }
        }
    },
    "ilham": {
        "label": "ham — internal doc & B2B",
        "keywords": {
            "must": [
                r"rapat|meeting|proyek|project|proposal|dokumen|document",
                r"laporan|report|memo|notulensi|minutes",
                r"team|divisi|department|division",
            ],
            "should_not": [
                r"klik.*link|click.*here",
                r"verifikasi|verify.*account",
                r"\bpola\b|\bpenipuan\b",
            ],
            "expected": {
                "meeting_keywords": 0.4,
                "document_keywords": 0.4,
            }
        }
    },
    "brian": {
        "label": "spam",
        "keywords": {
            "must": [
                r"selamat|congratulations|menang|winner|hadiah|prize",
                r"gratis|free|diskon|discount|promo",
                r"klik|click.*here|bit\.ly|tinyurl",
                r"\bRp[\d.,]+\b.*GRATIS|GRATIS.*Rp",
            ],
            "should_not": [
                r"terima kasih|thank you|best regards",
                r"notulensi|meeting|rapat",
            ],
            "expected": {
                "urgency_keywords": 0.6,
                "link_shorteners": 0.5,
            }
        }
    },
    "wisnu": {
        "label": "phishing",
        "keywords": {
            "must": [
                r"verifikasi|verify|konfirmasi",
                r"akun.*diblokir|account.*suspend|account.*limit",
                r"segera|urgent|immediately",
                r"bit\.ly|tinyurl|\.tk\b|\.ml\b|\.ga\b|\.cf\b|\.xyz\b",
            ],
            "should_not": [
                r"terima kasih.*menghubungi|thank you for contacting",
                r"notulensi|meeting",
                r"laporan.{0,20}keuangan",  # financial reports
            ],
            "expected": {
                "urgency": 0.7,
                "lookalike_domain": 0.5,
                "spoofed_brand": 0.6,
            }
        }
    },
    "risly": {
        "label": "malware",
        "keywords": {
            "must": [
                r"\.exe\b|\.vbs\b|\.js\b|\.docm\b|\.ps1\b|\.jar\b|\.bat\b|\.scr\b",
                r"lampiran|attachment|terlampir|attached",
                r"invoice|kontrak|contract|update.*sistem|security.*patch",
            ],
            "should_not": [
                r"selamat.*menang|congratulations.*won",
                r"verifikasi.*akun|verify.*account",
            ],
            "expected": {
                "executable_attachment": 0.8,
                "social_engineering_subject": 0.6,
            }
        }
    }
}


def validate_file(filepath: Path, category: str) -> dict:
    """Validate a single .eml file against category signatures."""
    try:
        raw = filepath.read_bytes()
    except Exception:
        return {"valid": False, "reason": "unreadable"}

    text = raw.decode("utf-8", errors="replace").lower()
    sigs = SIGNATURES[category]
    results = {}

    # Check must-have keywords
    must_hits = 0
    must_total = len(sigs["keywords"]["must"])
    for pattern in sigs["keywords"]["must"]:
        if re.search(pattern, text, re.IGNORECASE):
            must_hits += 1
    results["must_hit_ratio"] = must_hits / max(must_total, 1)

    # Check should-not-have keywords
    should_not_hits = 0
    for pattern in sigs["keywords"]["should_not"]:
        if re.search(pattern, text, re.IGNORECASE):
            should_not_hits += 1
    results["should_not_hits"] = should_not_hits

    # Validation decision
    valid = must_hits >= 1 and should_not_hits == 0
    results["valid"] = valid

    if not valid:
        reasons = []
        if must_hits == 0:
            reasons.append("no_category_keywords_found")
        if should_not_hits > 0:
            reasons.append(f"found_{should_not_hits}_cross_category_keywords")
        results["reason"] = ";".join(reasons)
    else:
        results["reason"] = "ok"

    return results


def validate_all():
    """Validate all folders and produce report."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    total_files = 0
    total_valid = 0
    per_folder = {}

    for folder in FOLDERS:
        folder_path = DATASET_DIR / folder
        if not folder_path.exists():
            print(f"  [SKIP] Folder not found: {folder}")
            continue

        files = sorted(folder_path.rglob("*.eml"))
        total_files += len(files)

        sigs = SIGNATURES[folder]
        valid_count = 0
        invalid_reasons = Counter()
        sample_valid = []
        sample_invalid = []

        for f in files:
            result = validate_file(f, folder)
            if result["valid"]:
                valid_count += 1
                if len(sample_valid) < 3:
                    sample_valid.append(f.name)
            else:
                invalid_reasons[result.get("reason", "unknown")] += 1
                if len(sample_invalid) < 5:
                    sample_invalid.append((f.name, result.get("reason", "?")))

        pct = valid_count / len(files) * 100 if files else 0
        per_folder[folder] = {
            "total": len(files),
            "valid": valid_count,
            "pct": pct,
            "invalid_reasons": invalid_reasons,
            "sample_valid": sample_valid,
            "sample_invalid": sample_invalid,
        }
        total_valid += valid_count

    # ─── Report ───────────────────────────────────────────────────────────
    print("=" * 70)
    print("  DATASET VALIDATION REPORT")
    print("=" * 70)

    for folder in FOLDERS:
        if folder not in per_folder:
            continue
        d = per_folder[folder]
        sigs = SIGNATURES[folder]
        bar_len = int(d["pct"] / 2)
        bar = "#" * bar_len + "." * (50 - bar_len)

        print(f"\n  {folder.upper():8s} | {sigs['label']}")
        print(f"  {'':8s} | [{bar}] {d['pct']:5.1f}%")
        print(f"  {'':8s} | Valid: {d['valid']}/{d['total']}")

        if d["invalid_reasons"]:
            print(f"  {'':8s} | Invalid breakdown:")
            for reason, count in d["invalid_reasons"].most_common(3):
                print(f"  {'':8s} |   - {reason}: {count} emails")
            print(f"  {'':8s} | Sample problematic:")
            for name, reason in d["sample_invalid"][:3]:
                print(f"  {'':8s} |   - {name[:50]}: {reason}")

        print(f"  {'':8s} | Sample valid:")
        for name in d["sample_valid"][:2]:
            print(f"  {'':8s} |   - {name[:50]}")

    overall_pct = total_valid / max(total_files, 1) * 100
    print(f"\n  SUMMARY")
    print(f"  {'':8s} | Total: {total_files} emails")
    print(f"  {'':8s} | Valid: {total_valid} ({overall_pct:.1f}%)")
    print(f"  {'':8s} | Invalid: {total_files - total_valid}")
    print("=" * 70)

    if total_files - total_valid > 0:
        print(f"\n  [WARN] {total_files - total_valid} emails may be misclassified.")
        print(f"     Review sample_invalid files above and move them to correct folder.")
    else:
        print(f"\n  [OK] ALL EMAILS CORRECTLY CATEGORIZED!")


if __name__ == "__main__":
    validate_all()
