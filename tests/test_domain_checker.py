import pytest
from analysis.domain_checker import DomainChecker, levenshtein_distance, jaro_winkler

def test_levenshtein_distance():
    assert levenshtein_distance("lodaya", "lodoya") == 1
    assert levenshtein_distance("lodaya", "lodaya") == 0
    assert levenshtein_distance("lodaya", "lodayatech") == 4

def test_jaro_winkler():
    # Basic Jaro-Winkler tests
    assert jaro_winkler("lodaya", "lodaya") == pytest.approx(1.0)
    assert jaro_winkler("lodaya", "google") < 0.5

def test_domain_checker_clean():
    checker = DomainChecker()
    
    # Protected domains should be clean and not suspicious
    for dom in ["lodaya.id", "lodayatech.id", "lodaya.co.id", "lodaya.com"]:
        res = checker.check(f"http://{dom}/index.html")
        assert not res.is_suspicious
        assert res.risk_level == "SAFE"

    # Completely unrelated safe domains
    for dom in ["google.com", "github.com", "president.ac.id"]:
        res = checker.check(f"https://{dom}/home")
        assert not res.is_suspicious
        assert res.risk_level == "SAFE"

def test_domain_checker_typosquatting():
    checker = DomainChecker()
    
    # Typosquatting lookalikes
    typo_domains = ["lodoya.id", "lodaye.id"]
    for dom in typo_domains:
        res = checker.check(f"https://{dom}/login")
        assert res.is_suspicious
        assert res.attack_type == "typosquatting"
        assert res.risk_level in ["HIGH", "MEDIUM"]

def test_domain_checker_combosquatting():
    checker = DomainChecker()
    
    # Combosquatting lookalikes
    combo_domains = [
        "lodaya-secure.id", 
        "lodaya-verify.id", 
        "login-lodaya.com", 
        "lodayatech-support.id"
    ]
    for dom in combo_domains:
        res = checker.check(f"https://{dom}/auth")
        assert res.is_suspicious
        assert res.attack_type == "combosquatting"
        assert res.risk_level in ["HIGH", "MEDIUM"]

def test_domain_checker_homograph():
    checker = DomainChecker()
    
    # Homograph attacks (Latin visual confusables or cyrillic equivalents)
    homoglyphs = [
        "l0daya.id",       # 0 instead of o
        "1odaya.id",       # 1 instead of l
    ]
    for dom in homoglyphs:
        res = checker.check(f"https://{dom}/verify")
        assert res.is_suspicious
        assert res.risk_level in ["HIGH", "MEDIUM"]
