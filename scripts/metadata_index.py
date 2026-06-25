"""
Fast Dataset Metadata Index
===========================
Scans .eml files and extracts metadata using lightweight parsing.
Produces CSV ready for ML training.

Usage:
  python scripts/metadata_index.py --dir data/dataset
  python scripts/metadata_index.py --dir data/dataset --enhance
"""

import argparse
import csv
import hashlib
import logging
import re
import json
from pathlib import Path
from collections import Counter
from email import message_from_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "chris": ("transaksi_cs", "ham"),
    "ilham": ("internal_b2b", "ham"),
    "brian": ("spam", "spam"),
    "wisnu": ("phishing", "phishing"),
    "risly": ("malware", "malware"),
}

URL_RE = re.compile(rb'https?://[^\s<>"\'()]+', re.IGNORECASE)
IMG_RE = re.compile(rb'<img[^>]+>', re.IGNORECASE)
HEADER_RE = re.compile(rb'^(From|To|Subject|Date):\s*(.+)$', re.IGNORECASE | re.MULTILINE)


def fast_parse_eml(filepath: Path) -> dict:
    """Parse .eml file without full MIME parsing — fast."""
    raw = filepath.read_bytes()
    content_hash = hashlib.sha256(raw).hexdigest()[:16]
    size = len(raw)

    folder = filepath.parent.name
    cat, label = CATEGORY_MAP.get(folder, ("unknown", "unknown"))

    # Headers
    sender = ""
    recipient = ""
    subject = ""
    date = ""

    # Simple header extraction
    header_end = raw.find(b"\r\n\r\n")
    if header_end == -1:
        header_end = raw.find(b"\n\n")

    header_section = raw[:header_end] if header_end > 0 else raw[:2000]
    for match in HEADER_RE.finditer(header_section):
        hname = match.group(1).lower()
        hval = match.group(2).decode("utf-8", errors="replace").strip()
        if hname == b"from":
            sender = hval[:200]
        elif hname == b"to":
            recipient = hval[:200]
        elif hname == b"subject":
            # Decode =?utf-8?q?...?= encoded subjects
            if "=?" in hval:
                try:
                    from email.header import decode_header
                    parts = decode_header(hval)
                    hval = "".join(
                        p.decode(charset or "utf-8", errors="replace") if isinstance(p, bytes)
                        else p for p, charset in parts
                    )
                except Exception:
                    pass
            subject = hval[:200]
        elif hname == b"date":
            date = hval[:100]

    # Body extraction (first 1000 bytes for analysis)
    body = raw[header_end + 4:] if header_end > 0 else raw
    body_text = body.decode("utf-8", errors="replace")[:2000]

    # Links
    urls = list(set(URL_RE.findall(body)))
    links_str = ";".join(u.decode("utf-8", errors="replace")[:120] for u in urls[:5])

    # Image tags in HTML
    img_tags = len(IMG_RE.findall(body))

    # Attachments (quick check)
    attachment_names = []
    for match in re.finditer(rb'filename="?([^"\r\n]+)"?', body):
        try:
            attachment_names.append(match.group(1).decode("utf-8", errors="replace")[:80])
        except Exception:
            pass

    has_image_attach = any("image" in str(a).lower() or a.endswith(b".png") or a.endswith(b".jpg") or a.endswith(b".jpeg") or a.endswith(b".gif")
                          for a in re.findall(rb'filename="?([^"\r\n]+)"?', body))

    return {
        "filename": filepath.name,
        "filepath": str(filepath.relative_to(filepath.parent.parent.parent))
                    if len(filepath.parents) > 3 else str(filepath),
        "size_bytes": size,
        "content_hash": content_hash,
        "category": cat,
        "class_label": label,
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "date": date,
        "body_length": len(body),
        "body_preview": body_text[:300].replace("\n", " ").replace("\r", ""),
        "num_links": len(urls),
        "links": links_str[:400],
        "num_attachments": len(attachment_names),
        "attachment_names": ";".join(attachment_names)[:300],
        "num_images": img_tags,
        "has_image_attachment": "yes" if has_image_attach else "no",
    }


def generate_index(dataset_dir: Path, output_path: Path):
    """Generate metadata CSV for all .eml files."""
    files = sorted(dataset_dir.rglob("*.eml"))
    logger.info("Found %d .eml files", len(files))

    fieldnames = [
        "filename", "filepath", "size_bytes", "content_hash",
        "category", "class_label",
        "sender", "recipient", "subject", "date",
        "body_length", "body_preview",
        "num_links", "links",
        "num_attachments", "attachment_names",
        "num_images", "has_image_attachment",
    ]

    rows = []
    errs = 0
    for i, f in enumerate(files):
        try:
            meta = fast_parse_eml(f)
            rows.append(meta)
        except Exception as e:
            errs += 1
            logger.debug("Error %s: %s", f.name, e)
        if (i + 1) % 2000 == 0:
            logger.info("  %d/%d (%.0f%%)", i + 1, len(files), (i + 1) / len(files) * 100)

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Stats
    cat_counts = Counter(r["category"] for r in rows)
    label_counts = Counter(r["class_label"] for r in rows)

    has_links = sum(1 for r in rows if r["num_links"] > 0)
    has_att = sum(1 for r in rows if r["num_attachments"] > 0)
    has_img = sum(1 for r in rows if r["num_images"] > 0)
    has_img_att = sum(1 for r in rows if r["has_image_attachment"] == "yes")

    print(f"""
{'='*60}
DATASET METADATA INDEX
{'='*60}
Output: {output_path}
Total: {len(rows)} emails | Errors: {errs}

Category Distribution:
""")
    for c, n in sorted(cat_counts.items()):
        p = n / len(rows) * 100
        print(f"  {c:20s}: {n:5d} ({p:5.1f}%)")

    print(f"\nClass Labels:")
    for l, n in sorted(label_counts.items()):
        p = n / len(rows) * 100
        print(f"  {l:15s}: {n:5d} ({p:5.1f}%)")

    print(f"""
Coverage Analysis:
  Links:              {has_links:5d}/{len(rows)} ({has_links/len(rows)*100:5.1f}%)
  Attachments:        {has_att:5d}/{len(rows)} ({has_att/len(rows)*100:5.1f}%)
  Image Tags (HTML):  {has_img:5d}/{len(rows)} ({has_img/len(rows)*100:5.1f}%)
  Image Attachments:  {has_img_att:5d}/{len(rows)} ({has_img_att/len(rows)*100:5.1f}%)
""")

    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dataset metadata index")
    parser.add_argument("--dir", default="data/dataset")
    parser.add_argument("--output", default="data/dataset/metadata.csv")
    args = parser.parse_args()

    generate_index(Path(args.dir), Path(args.output))
