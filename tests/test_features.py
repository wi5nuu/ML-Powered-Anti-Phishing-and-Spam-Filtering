# tests/test_features.py — contoh minimal

import pytest
from classifier.features import EmailParser, FeatureExtractor, EmailFeatures

PHISHING_EMAIL = """\
From: "Bank BCA" <noreply@bca-secure-login.xyz>
To: staf@lodaya.id
Subject: SEGERA! Akun Anda Akan Diblokir
Content-Type: text/html

<html><body>
<form action="http://1odaya.id/login">
  Klik <a href="http://bit.ly/verifikasi-akun">di sini</a> untuk verifikasi.
  Verifikasi sekarang atau akun ditangguhkan!
</form>
</body></html>
"""

LEGITIMATE_EMAIL = """\
From: "Tim LTI" <devops@lodaya.id>
To: all@lodaya.id
DKIM-Signature: v=1; a=rsa-sha256; d=lodaya.id; ...
Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass
Subject: Update sistem maintenance jadwal Minggu ini

Halo tim, berikut jadwal maintenance server...
"""


def test_phishing_email_high_urgency():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(PHISHING_EMAIL)
    features = extractor.extract(parsed)
    assert features.urgency_score > 0.3, "Urgency score harus tinggi untuk phishing"


def test_phishing_email_lookalike_domain():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(PHISHING_EMAIL)
    features = extractor.extract(parsed)
    # "1odaya.id" vs "lodaya.id" → Levenshtein distance 1
    assert features.has_lookalike_domain, "Harus deteksi lookalike domain"
    assert features.min_levenshtein_to_protected <= 3


def test_phishing_email_has_form():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(PHISHING_EMAIL)
    features = extractor.extract(parsed)
    assert features.num_forms > 0


def test_phishing_email_url_shortener():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(PHISHING_EMAIL)
    features = extractor.extract(parsed)
    assert features.has_url_shortener, "bit.ly harus terdeteksi sebagai URL shortener"


def test_legitimate_email_auth_pass():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(LEGITIMATE_EMAIL)
    features = extractor.extract(parsed)
    assert features.spf_pass
    assert features.dkim_pass
    assert features.dmarc_pass


def test_display_name_mismatch():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(PHISHING_EMAIL)
    features = extractor.extract(parsed)
    # "Bank BCA" tapi domain bukan bca.co.id → mismatch
    assert features.display_name_mismatch


def test_combined_text_subject_weighted():
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(PHISHING_EMAIL)
    features = extractor.extract(parsed)
    # Subject "SEGERA! Akun Anda Akan Diblokir" harus muncul 3x di combined_text
    count = features.combined_text.count("SEGERA")
    assert count >= 3, "Subject harus diberi bobot 3x di combined_text"
