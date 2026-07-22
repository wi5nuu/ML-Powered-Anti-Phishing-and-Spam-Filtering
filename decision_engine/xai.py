"""
XAI module — membangun X-Spam-Reason header string dari hasil fusion dan fitur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classifier.features import EmailFeatures


XAI_HUMAN_LABELS = {
    "urgency_score": "Email mengandung kata-kata mendesak/darurat",
    "has_lookalike_domain": "Link mengarah ke domain yang mirip lodaya.id",
    "spf_pass": "Verifikasi identitas pengirim (SPF) berhasil",
    "dkim_pass": "Tanda tangan digital email (DKIM) valid",
    "dmarc_pass": "Kebijakan keamanan email (DMARC) dipenuhi",
    "has_executable_attachment": "Email memiliki lampiran program/script berbahaya",
    "has_url_shortener": "Link dipersingkat (menyembunyikan tujuan asli)",
    "display_name_mismatch": "Nama pengirim tidak cocok dengan alamat email aslinya",
    "html_text_ratio": "Email hampir seluruhnya berupa gambar/HTML (tanpa teks)",
    "num_forms": "Email memiliki formulir input (mencurigakan di email)",
    "javascript_present": "Email mengandung kode JavaScript",
    "subject_has_re_fwd_fake": "Reply/forward palsu di judul email",
}


def build_xai_header(features: EmailFeatures, spam_prob: float,
                     fused_score: float, label: str) -> str:
    """
    Bangun string X-Spam-Reason dari fitur dan skor.
    """
    parts = [f"SpamProb={spam_prob:.2f}", f"FusedScore={fused_score:.2f}"]

    if spam_prob > 0.30:
        if features.urgency_score > 0.3:
            parts.append(f"Urgency-Score:{features.urgency_score:.2f}")
        if features.has_lookalike_domain:
            parts.append(
                f"Lookalike-Domain:Distance={features.min_levenshtein_to_protected}"
            )
        if not features.spf_pass:
            parts.append("SPF:FAIL")
        if not features.dkim_pass:
            parts.append("DKIM:FAIL")
        if features.has_executable_attachment:
            parts.append("Executable-Attachment:YES")
        if features.has_url_shortener:
            parts.append("URL-Shortener:DETECTED")
        if features.display_name_mismatch:
            parts.append("DisplayName-Mismatch:YES")
        if features.num_forms > 0:
            parts.append(f"HTML-Forms:{features.num_forms}")

    return "; ".join(parts)


def human_readable_reasons(features: EmailFeatures) -> list[str]:
    """
    Kembalikan daftar alasan yang bisa dibaca manusia non-teknis.
    """
    reasons = []
    if features.urgency_score > 0.3:
        reasons.append(XAI_HUMAN_LABELS["urgency_score"])
    if features.has_lookalike_domain:
        reasons.append(XAI_HUMAN_LABELS["has_lookalike_domain"])
    if features.has_executable_attachment:
        reasons.append(XAI_HUMAN_LABELS["has_executable_attachment"])
    if features.has_url_shortener:
        reasons.append(XAI_HUMAN_LABELS["has_url_shortener"])
    if features.display_name_mismatch:
        reasons.append(XAI_HUMAN_LABELS["display_name_mismatch"])
    if features.num_forms > 0:
        reasons.append(XAI_HUMAN_LABELS["num_forms"])
    if features.javascript_present:
        reasons.append(XAI_HUMAN_LABELS["javascript_present"])
    if features.subject_has_re_fwd_fake:
        reasons.append(XAI_HUMAN_LABELS["subject_has_re_fwd_fake"])
    return reasons
