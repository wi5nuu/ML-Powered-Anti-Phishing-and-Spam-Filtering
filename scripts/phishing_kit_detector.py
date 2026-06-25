"""
Phishing Kit Detection — Identifies phishing emails using known templates.
Computes HTML structural similarity to known phishing kits.
"""

import hashlib
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_KITS_DIR = Path("data/phishing_kits")
KNOWN_KITS_DIR.mkdir(parents=True, exist_ok=True)

# Known phishing kit signatures (structural hashes)
# In production, these would be populated from a threat feed
KNOWN_KIT_SIGNATURES = set()

def load_known_kits():
    """Load known phishing kit signatures from disk."""
    sig_file = KNOWN_KITS_DIR / "signatures.json"
    if sig_file.exists():
        with open(sig_file) as f:
            data = json.load(f)
            KNOWN_KIT_SIGNATURES.update(data.get("signatures", []))
    logger.info("Loaded %d known phishing kit signatures", len(KNOWN_KIT_SIGNATURES))


def compute_html_structure_hash(html_content: str) -> str:
    """Compute a hash of the HTML structure (ignoring text content)."""
    # Remove text content between tags
    structural = re.sub(r'>[^<]+<', '><', html_content)
    structural = re.sub(r'\s+', '', structural)
    return hashlib.sha256(structural.encode()).hexdigest()[:16]


def detect_phishing_kit(html_content: str) -> dict:
    """Check if email HTML matches known phishing kit signatures."""
    if not html_content or len(html_content) < 50:
        return {"kit_detected": False, "confidence": 0.0}

    structure_hash = compute_html_structure_hash(html_content)
    is_known = structure_hash in KNOWN_KIT_SIGNATURES

    # Check for kit indicators in HTML
    indicators = []
    kit_indicators = [
        (r'base64_decode\s*\(', "base64 encoded content"),
        (r'document\.write\(atob\(', "obfuscated JavaScript"),
        (r'<form[^>]*action=["\']https?://[^"\']*\.(ru|cn|tk|ml|ga|cf|gq)', "Suspicious TLD in form action"),
        (r'<input[^>]*name=["\']?(cc|credit|card|cvv|cvc|ssn|bank|account)', "Credit card input field"),
        (r'submit\(\);\s*\}', "Auto-submit form"),
        (r'var\s+\w+\s*=\s*["\'][a-zA-Z0-9+/=]{20,}["\']', "Suspicious base64-like strings"),
    ]

    for pattern, desc in kit_indicators:
        if re.search(pattern, html_content, re.IGNORECASE):
            indicators.append(desc)

    confidence = 0.0
    if is_known:
        confidence = 0.95
    elif len(indicators) >= 3:
        confidence = 0.80
    elif len(indicators) >= 1:
        confidence = 0.40

    return {
        "kit_detected": confidence > 0.5,
        "confidence": round(confidence, 4),
        "structure_hash": structure_hash,
        "is_known_kit": is_known,
        "indicators_found": indicators,
        "indicator_count": len(indicators),
    }


def add_kit_signature(html_content: str, label: str = "phishing"):
    """Add a new phishing kit signature to the database."""
    structure_hash = compute_html_structure_hash(html_content)
    KNOWN_KIT_SIGNATURES.add(structure_hash)

    sig_file = KNOWN_KITS_DIR / "signatures.json"
    existing = {"signatures": [], "metadata": {}}
    if sig_file.exists():
        with open(sig_file) as f:
            existing = json.load(f)
    existing["signatures"] = list(KNOWN_KIT_SIGNATURES)
    existing["metadata"][structure_hash] = {
        "label": label,
        "added_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
    with open(sig_file, "w") as f:
        json.dump(existing, f, indent=2)

    return structure_hash
