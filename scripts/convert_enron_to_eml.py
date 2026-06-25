"""
Convert Enron plain text emails to .eml format.

Enron emails are stored as plain text files (one per email) with:
  Subject: <subject line>
  <body>

This script wraps them into proper RFC 2822 .eml format so our
pipeline can parse them alongside the generated .eml files.
"""

import email.utils
import hashlib
import os
import re
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

RNG = random.Random(42)

ENRON_DOMAINS = ["enron.com", "ect.enron.com", "enron.net",
                 "houston.enron.com", "california.enron.com"]

ENRON_SENDERS = [
    "Jeff Dasovich", "Sally Beck", "John Lavorato", "Louise Kitchen",
    "Greg Whalley", "Andy Zipper", "Tim Belden", "John Arnold",
    "Eric Bass", "Mark Taylor", "Michael Swartz", "Scott Neal",
    "Chris Germany", "Kevin Hyatt", "Phillip Love", "Mike Grigsby",
    "Vince Kaminski", "John Forney", "Don Black", "Benjy Himstreet",
]

ENRON_RECIPIENTS = [
    "Richard Shapiro", "David Delainey", "Steven Kean", "Ken Lay",
    "Jeff Skilling", "Andrew Fastow", "Rick Buy", "Marty Sunde",
    "Mike Swerzbin", "Susan Bailey", "James Steffes", "Janet Dietrich",
    "Kim Ward", "Lynn Blair", "Mary Hain", "Paul Kaufman",
    "Robert Superty", "Steve Soderstrom", "Tom Morron", "Wanda Curry",
]


def generate_message_id(filename: str) -> str:
    raw = f"{filename}.{RNG.randint(1000,9999)}"
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"<{h}@enron-converter.local>"


def make_header_email(name: str) -> str:
    name_part = name.lower().replace(" ", ".").replace("'", "")
    return f"{name_part}@{RNG.choice(ENRON_DOMAINS)}"


def generate_date_from_mtime(mtime: float) -> str:
    d = datetime.fromtimestamp(mtime)
    return email.utils.formatdate(timeval=d.timestamp(), localtime=True)


def convert_enron_file(filepath: Path, label: str) -> tuple[str, str]:
    """Convert an Enron plain text file to .eml content.

    Returns (eml_content, subject).
    """
    content = filepath.read_text(encoding="utf-8", errors="replace")
    content = content.strip()

    subject = "(no subject)"
    body_lines = []
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Subject:"):
            subject = line[len("Subject:"):].strip()
        elif line.startswith("Subject :"):
            subject = line[len("Subject :"):].strip()
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()

    sender = RNG.choice(ENRON_SENDERS)
    recipient = RNG.choice(ENRON_RECIPIENTS)

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"{sender} <{make_header_email(sender)}>"
    msg["To"] = f"{recipient} <{make_header_email(recipient)}>"
    msg["Subject"] = subject
    msg["Date"] = generate_date_from_mtime(filepath.stat().st_mtime)
    msg["Message-ID"] = generate_message_id(filepath.name)
    msg["MIME-Version"] = "1.0"
    msg["X-Mailer"] = "Enron Outlook 2000"
    msg["X-Enron-Source"] = f"enron_{label}"

    return msg.as_string(), subject


def convert_enron_dataset(raw_dir: str, output_dir: str):
    """Convert all enron1 and enron2 ham/spam to .eml format."""
    raw = Path(raw_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    total = 0
    for enron_sub in ["enron1", "enron2"]:
        for label in ["ham", "spam"]:
            src_dir = raw / enron_sub / label
            if not src_dir.exists():
                continue
            dst_dir = output / f"{enron_sub}_{label}"
            dst_dir.mkdir(parents=True, exist_ok=True)

            files = sorted(src_dir.iterdir())
            for fpath in files:
                if not fpath.is_file():
                    continue
                try:
                    eml_content, subject = convert_enron_file(fpath, label)
                    clean_name = re.sub(r'[<>:"/\\|?*]', "_", fpath.name)
                    outf = dst_dir / f"{clean_name}.eml"
                    outf.write_text(eml_content, encoding="utf-8")
                    total += 1
                    if total % 1000 == 0:
                        print(f"  Converted {total}...")
                except Exception as e:
                    print(f"  ERROR {fpath.name}: {e}")

    print(f"\nTotal Enron emails converted: {total}")
    print(f"Output: {output}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert Enron to .eml")
    parser.add_argument("--raw", default="data/raw/enron",
                        help="Enron raw data directory")
    parser.add_argument("--output", default="data/dataset_merged/_enron",
                        help="Output directory for .eml files")
    args = parser.parse_args()

    print("Enron -> .eml Converter")
    print(f"Input:  {args.raw}")
    print(f"Output: {args.output}")
    convert_enron_dataset(args.raw, args.output)
