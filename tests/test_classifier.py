import pytest
import pandas as pd
from classifier.features import STRUCTURED_FEATURES


def test_structured_features_list():
    assert len(STRUCTURED_FEATURES) >= 19
    assert "num_urls" in STRUCTURED_FEATURES
    assert "has_lookalike_domain" in STRUCTURED_FEATURES
    assert "spf_pass" in STRUCTURED_FEATURES
    assert "javascript_present" in STRUCTURED_FEATURES


def test_structured_features_no_duplicates():
    assert len(STRUCTURED_FEATURES) == len(set(STRUCTURED_FEATURES))


def test_feature_extractor_correct_types():
    from classifier.features import EmailParser, FeatureExtractor

    raw = """\
From: "Bank BCA" <noreply@bca-secure-login.xyz>
To: staf@lodaya.id
Subject: URGENT: Akun Diblokir

Klik http://1odaya.id sekarang!
"""
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(raw)
    features = extractor.extract(parsed)

    assert isinstance(features.num_urls, int)
    assert isinstance(features.has_url_shortener, bool)
    assert isinstance(features.urgency_score, float)
    assert isinstance(features.spf_pass, bool)
    assert isinstance(features.num_forms, int)
    assert isinstance(features.javascript_present, bool)
    assert isinstance(features.html_text_ratio, float)
