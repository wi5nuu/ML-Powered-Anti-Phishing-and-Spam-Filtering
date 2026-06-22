import pytest
from decision_engine.fusion import fuse, FusionResult
from decision_engine.router import route
from classifier.features import EmailFeatures


def test_fusion_clean():
    result = fuse(sa_score=0.0, ml_probability=0.05,
                  spf_pass=True, dkim_pass=True, dmarc_pass=True)
    assert result.label == "CLEAN"
    assert result.fused_score < 0.30
    assert isinstance(result, FusionResult)


def test_fusion_warn():
    result = fuse(sa_score=5.0, ml_probability=0.50,
                  spf_pass=True, dkim_pass=True, dmarc_pass=True)
    assert result.label in ("WARN", "CLEAN")


def test_fusion_quarantine():
    result = fuse(sa_score=10.0, ml_probability=0.85)
    assert result.label == "QUARANTINE"


def test_fusion_hard_threshold_sa():
    result = fuse(sa_score=16.0, ml_probability=0.10)
    assert result.label == "QUARANTINE"
    assert result.fused_score == 1.0


def test_fusion_hard_threshold_ml():
    result = fuse(sa_score=0.0, ml_probability=0.98)
    assert result.label == "QUARANTINE"
    assert result.fused_score == 1.0


def test_fusion_auth_override():
    result_no_auth = fuse(sa_score=3.0, ml_probability=0.40,
                          spf_pass=False, dkim_pass=False, dmarc_pass=False)
    result_auth = fuse(sa_score=3.0, ml_probability=0.40,
                       spf_pass=True, dkim_pass=True, dmarc_pass=True)
    assert result_auth.fused_score <= result_no_auth.fused_score


def test_route_clean():
    fusion = fuse(sa_score=0.0, ml_probability=0.05)
    features = EmailFeatures()
    decision = route(fusion, features)
    assert decision.action == "DELIVER"


def test_route_quarantine():
    fusion = fuse(sa_score=16.0, ml_probability=0.98)
    features = EmailFeatures()
    decision = route(fusion, features)
    assert decision.action == "QUARANTINE"
