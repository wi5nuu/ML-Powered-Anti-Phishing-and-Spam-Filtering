"""
Word Cloud Generator — Visualize most common words in phishing vs legitimate emails.
Usage: python scripts/wordcloud_gen.py [--output screenshots/wordcloud.png]
"""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from wordcloud import WordCloud
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from database.models import QuarantineEmail

DB_URL = os.getenv("DB_URL", "sqlite:///./lti_antiphishing.db")
OUTPUT_DIR = Path("screenshots")
OUTPUT_DIR.mkdir(exist_ok=True)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def generate_wordcloud(output: str = None):
    db = SessionLocal()
    phishing_texts = []
    legit_texts = []

    emails = db.query(QuarantineEmail.subject, QuarantineEmail.label).all()
    for subject, label in emails:
        text = (subject or "").lower()
        if label == "QUARANTINE":
            phishing_texts.append(text)
        else:
            legit_texts.append(text)

    db.close()

    if not phishing_texts:
        phishing_texts = ["no phishing data yet"]
    if not legit_texts:
        legit_texts = ["no legitimate data yet"]

    fig, axes = plt.subplots(1, 2, figsize=(20, 8))

    for ax, texts, title, color in [
        (axes[0], phishing_texts, "Phishing / QUARANTINE", "Reds"),
        (axes[1], legit_texts, "Legitimate / WARN", "Greens"),
    ]:
        combined = " ".join(texts)
        if combined.strip() == "no phishing data yet no legitimate data yet":
            combined = "no data yet"

        wc = WordCloud(
            width=800, height=400,
            background_color="white",
            colormap=color,
            max_words=100,
            contour_width=1,
            contour_color="gray",
        ).generate(combined)

        ax.imshow(wc, interpolation="bilinear")
        ax.set_title(title, fontsize=16, fontweight="bold")
        ax.axis("off")

    plt.tight_layout()
    output_path = output or str(OUTPUT_DIR / "wordcloud_comparison.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Word cloud saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate word cloud comparison")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    generate_wordcloud(output=args.output)
