"""
Decision Engine — menggabungkan skor SpamAssassin + ML Classifier + Anomaly Detection.

Tiga lapisan deteksi (Dual Detection Architecture):
  Layer 1 — Supervised (XGBoost + TF-IDF) — pola spam dikenal
  Layer 2 — Unsupervised (Isolation Forest + One-Class SVM) — zero-day / anomali
  Layer 3 — Rule-based (SpamAssassin) — spam pattern klasik

Metodologi penggabungan (3-way fusion):
  1. Normalisasi skor SA ke 0.0–1.0 (SA skala 0–20+)
  2. Weighted average: ML_prob * 0.50 + SA_normalized * 0.25 + Anomaly * 0.25
  3. Override: jika SA score > 15, ML prob > 0.95, ATAU Anomaly > 0.90 → QUARANTINE
  4. Override: jika SPF+DKIM+DMARC semua PASS dan ML prob < 0.5, turunkan

Rasio 50/25/25: supervised sebagai primary, anomaly detection sebagai
secondary — karena anomaly detection bisa catch zero-day yang tidak
pernah ada di training set supervised.
"""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Konfigurasi (bisa override via env vars)
ML_WEIGHT       = float(os.getenv("FUSION_ML_WEIGHT", "0.50"))
SA_WEIGHT       = float(os.getenv("FUSION_SA_WEIGHT", "0.25"))
ANOMALY_WEIGHT  = float(os.getenv("FUSION_ANOMALY_WEIGHT", "0.25"))
SA_HARD_LIMIT   = float(os.getenv("SA_QUARANTINE_THRESHOLD", "15.0"))
ML_HARD_LIMIT   = float(os.getenv("ML_QUARANTINE_THRESHOLD", "0.95"))
ANOMALY_HARD_LIMIT = float(os.getenv("ANOMALY_QUARANTINE_THRESHOLD", "0.90"))
SA_MAX_SCORE    = float(os.getenv("SA_MAX_SCORE", "20.0"))
THRESH_CLEAN    = float(os.getenv("THRESHOLD_CLEAN", "0.30"))
THRESH_WARN     = float(os.getenv("THRESHOLD_WARN", "0.70"))
WARN_EVIDENCE_GATED = os.getenv("WARN_EVIDENCE_GATED", "true").lower() in {"1", "true", "yes", "on"}
WARN_MIN_EVIDENCE = int(os.getenv("WARN_MIN_EVIDENCE", "2"))
WARN_ML_EVIDENCE_THRESHOLD = float(os.getenv("WARN_ML_EVIDENCE_THRESHOLD", "0.85"))
WARN_SA_EVIDENCE_THRESHOLD = float(os.getenv("WARN_SA_EVIDENCE_THRESHOLD", "8.0"))
WARN_ANOMALY_EVIDENCE_THRESHOLD = float(os.getenv("WARN_ANOMALY_EVIDENCE_THRESHOLD", "0.85"))
WARN_AUTH_EVIDENCE = os.getenv("WARN_AUTH_EVIDENCE", "false").lower() in {"1", "true", "yes", "on"}
QUARANTINE_EVIDENCE_GATED = os.getenv("QUARANTINE_EVIDENCE_GATED", "true").lower() in {"1", "true", "yes", "on"}
QUARANTINE_MIN_EVIDENCE = int(os.getenv("QUARANTINE_MIN_EVIDENCE", "2"))


@dataclass
class FusionResult:
    sa_score: float            # Raw SpamAssassin score
    ml_probability: float      # ML model probability
    anomaly_score: float       # Unsupervised anomaly score
    sa_normalized: float       # SA score dinormalisasi ke 0–1
    fused_score: float         # Skor akhir gabungan
    label: str                 # CLEAN / WARN / QUARANTINE
    routing_reason: str        # Penjelasan mengapa label ini


def fuse(sa_score: float, ml_probability: float,
         anomaly_score: float = 0.0,
         spf_pass: bool = False, dkim_pass: bool = False,
         dmarc_pass: bool = False) -> FusionResult:
    """
    Gabungkan tiga lapisan skor → routing decision.

    Args:
        sa_score: Skor dari SpamAssassin (biasanya -2 s/d 20+)
        ml_probability: Probabilitas spam dari ML model (0.0–1.0)
        anomaly_score: Skor anomali dari unsupervised detector (0.0–1.0)
        spf_pass, dkim_pass, dmarc_pass: Hasil validasi email authentication

    Returns:
        FusionResult dengan label routing dan penjelasan.
    """
    # Normalisasi SA score ke [0, 1]
    sa_clamped = max(0.0, min(sa_score, SA_MAX_SCORE))
    sa_normalized = sa_clamped / SA_MAX_SCORE

    # Hard overrides — langsung QUARANTINE tanpa fusion
    hard_evidence = []
    if sa_score >= SA_HARD_LIMIT:
        hard_evidence.append(f"SA={sa_score:.1f}")
    if ml_probability >= ML_HARD_LIMIT:
        hard_evidence.append(f"ML={ml_probability:.3f}")
    if anomaly_score >= ANOMALY_HARD_LIMIT:
        hard_evidence.append(f"Anomaly={anomaly_score:.3f}")

    if hard_evidence and (not QUARANTINE_EVIDENCE_GATED or len(hard_evidence) >= QUARANTINE_MIN_EVIDENCE):
        reason = f"Hard threshold triggered: {', '.join(hard_evidence)}"
        return FusionResult(
            sa_score=sa_score,
            ml_probability=ml_probability,
            anomaly_score=anomaly_score,
            sa_normalized=sa_normalized,
            fused_score=1.0,
            label="QUARANTINE",
            routing_reason=reason,
        )
    hard_gate_reason = ""
    if hard_evidence:
        hard_gate_reason = (
            f"Hard threshold evidence weak ({len(hard_evidence)}/{QUARANTINE_MIN_EVIDENCE}: "
            f"{', '.join(hard_evidence)})"
        )

    # 3-way weighted fusion
    fused = (
        (ml_probability * ML_WEIGHT) +
        (sa_normalized * SA_WEIGHT) +
        (anomaly_score * ANOMALY_WEIGHT)
    )

    # Override ke bawah: authentication lengkap = lebih percaya
    if spf_pass and dkim_pass and dmarc_pass and ml_probability < 0.50:
        fused = max(0.0, fused - 0.10)
        logger.debug("Auth override applied (SPF+DKIM+DMARC pass), fused reduced.")

    # Routing
    if fused < THRESH_CLEAN:
        label = "CLEAN"
        reason = f"Score below clean threshold ({THRESH_CLEAN})"
    elif fused < THRESH_WARN:
        evidence = []
        if ml_probability >= WARN_ML_EVIDENCE_THRESHOLD:
            evidence.append(f"ML={ml_probability:.3f}")
        if sa_score >= WARN_SA_EVIDENCE_THRESHOLD:
            evidence.append(f"SA={sa_score:.1f}")
        if anomaly_score >= WARN_ANOMALY_EVIDENCE_THRESHOLD:
            evidence.append(f"Anomaly={anomaly_score:.3f}")
        if WARN_AUTH_EVIDENCE and not (spf_pass and dkim_pass and dmarc_pass):
            evidence.append("Auth incomplete/failed")

        if WARN_EVIDENCE_GATED and len(evidence) < WARN_MIN_EVIDENCE:
            label = "CLEAN"
            reason = (
                f"Score in warning zone ({THRESH_CLEAN}\u2013{THRESH_WARN}) "
                f"but weak evidence ({len(evidence)}/{WARN_MIN_EVIDENCE}: {', '.join(evidence) or 'none'})"
            )
            if hard_gate_reason:
                reason = f"{hard_gate_reason}; {reason}"
        else:
            label = "WARN"
            reason = (
                f"Score in warning zone ({THRESH_CLEAN}\u2013{THRESH_WARN}); "
                f"evidence: {', '.join(evidence) or 'score only'}"
            )
            if hard_gate_reason:
                reason = f"{hard_gate_reason}; {reason}"
    else:
        label = "QUARANTINE"
        reason = f"Score above quarantine threshold ({THRESH_WARN})"
        if hard_gate_reason:
            reason = f"{hard_gate_reason}; {reason}"

    return FusionResult(
        sa_score=sa_score,
        ml_probability=ml_probability,
        anomaly_score=anomaly_score,
        sa_normalized=sa_normalized,
        fused_score=round(fused, 4),
        label=label,
        routing_reason=reason,
    )
