"""
Decision Engine — menggabungkan skor SpamAssassin + ML Classifier.

Metodologi penggabungan:
  1. Normalisasi skor SA ke 0.0–1.0 (SA skala 0–20+)
  2. Weighted average: ML_prob * 0.65 + SA_normalized * 0.35
  3. Override: jika SA score > 15 ATAU ML prob > 0.95, langsung QUARANTINE
  4. Override: jika SPF+DKIM+DMARC semua PASS dan ML prob < 0.5, turunkan ke CLEAN

Rasio 65/35 dipilih karena ML lebih adaptif terhadap pola baru,
SA lebih reliable untuk spam pattern yang sudah dikenal.
Ratio ini dapat dikalibrasi ulang via konfigurasi.
"""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Konfigurasi (bisa override via env vars)
ML_WEIGHT     = float(os.getenv("FUSION_ML_WEIGHT", "0.65"))
SA_WEIGHT     = float(os.getenv("FUSION_SA_WEIGHT", "0.35"))
SA_HARD_LIMIT = float(os.getenv("SA_QUARANTINE_THRESHOLD", "15.0"))
ML_HARD_LIMIT = float(os.getenv("ML_QUARANTINE_THRESHOLD", "0.95"))
SA_MAX_SCORE  = float(os.getenv("SA_MAX_SCORE", "20.0"))
THRESH_CLEAN  = float(os.getenv("THRESHOLD_CLEAN", "0.30"))
THRESH_WARN   = float(os.getenv("THRESHOLD_WARN", "0.70"))


@dataclass
class FusionResult:
    sa_score: float            # Raw SpamAssassin score
    ml_probability: float      # ML model probability
    sa_normalized: float       # SA score dinormalisasi ke 0–1
    fused_score: float         # Skor akhir gabungan
    label: str                 # CLEAN / WARN / QUARANTINE
    routing_reason: str        # Penjelasan mengapa label ini


def fuse(sa_score: float, ml_probability: float,
         spf_pass: bool = False, dkim_pass: bool = False,
         dmarc_pass: bool = False) -> FusionResult:
    """
    Gabungkan skor SpamAssassin dan probabilitas ML → routing decision.

    Args:
        sa_score: Skor dari SpamAssassin (biasanya -2 s/d 20+)
        ml_probability: Probabilitas spam dari ML model (0.0–1.0)
        spf_pass, dkim_pass, dmarc_pass: Hasil validasi email authentication

    Returns:
        FusionResult dengan label routing dan penjelasan.
    """
    # Normalisasi SA score ke [0, 1]
    sa_clamped = max(0.0, min(sa_score, SA_MAX_SCORE))
    sa_normalized = sa_clamped / SA_MAX_SCORE

    # Hard overrides — tidak perlu hitung weighted average
    if sa_score >= SA_HARD_LIMIT or ml_probability >= ML_HARD_LIMIT:
        reason = (
            f"Hard threshold triggered: SA={sa_score:.1f}, ML={ml_probability:.3f}"
        )
        return FusionResult(
            sa_score=sa_score,
            ml_probability=ml_probability,
            sa_normalized=sa_normalized,
            fused_score=1.0,
            label="QUARANTINE",
            routing_reason=reason,
        )

    # Weighted fusion
    fused = (ml_probability * ML_WEIGHT) + (sa_normalized * SA_WEIGHT)

    # Override ke bawah: authentication lengkap = lebih percaya
    if spf_pass and dkim_pass and dmarc_pass and ml_probability < 0.50:
        fused = max(0.0, fused - 0.10)  # Diskon 10 poin
        logger.debug("Auth override applied (SPF+DKIM+DMARC pass), fused reduced.")

    # Routing
    if fused < THRESH_CLEAN:
        label = "CLEAN"
        reason = f"Score below clean threshold ({THRESH_CLEAN})"
    elif fused < THRESH_WARN:
        label = "WARN"
        reason = f"Score in warning zone ({THRESH_CLEAN}\u2013{THRESH_WARN})"
    else:
        label = "QUARANTINE"
        reason = f"Score above quarantine threshold ({THRESH_WARN})"

    return FusionResult(
        sa_score=sa_score,
        ml_probability=ml_probability,
        sa_normalized=sa_normalized,
        fused_score=round(fused, 4),
        label=label,
        routing_reason=reason,
    )
