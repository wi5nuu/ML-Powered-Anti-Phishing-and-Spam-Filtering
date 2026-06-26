"""
Heuristic Domain Lookalike Checker — LTI Anti-Phishing System.

Mendeteksi serangan domain spoofing terhadap domain LTI (lodaya.id dll).

Metode deteksi:
  1. Levenshtein distance — typosquatting (lodaya → lodoya, lodaya → Iodaya)
  2. Jaro-Winkler similarity — lebih akurat untuk prefix similarity
  3. Homograph detection — karakter visually similar (l→1, 0→o, rn→m, vv→w)
  4. Combosquatting — "lodaya-secure.id", "lodaya-verify.id"
  5. DNS age check — domain terdaftar < 30 hari = suspicious

Usage:
    from analysis.domain_checker import DomainChecker, DomainAnalysis
    checker = DomainChecker()
    result = checker.check("http://l0daya.id/login")
    print(result.is_suspicious, result.attack_type)
"""

import logging
import re
import socket
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, List
from urllib.parse import urlparse
import os

logger = logging.getLogger(__name__)

# ─── Protected domains (from config / env) ──────────────────────────────────────

DEFAULT_PROTECTED_DOMAINS = [
    "lodaya.id",
    "lodayatech.id",
    "lodaya.co.id",
    "lodaya.com",
]


def _load_protected_domains() -> List[str]:
    env_val = os.getenv("PROTECTED_DOMAINS", "")
    if env_val:
        return [d.strip().lower() for d in env_val.split(",") if d.strip()]
    return DEFAULT_PROTECTED_DOMAINS


# ─── Homograph character map ─────────────────────────────────────────────────────

HOMOGRAPH_MAP = {
    # Visual confusables (Latin + Cyrillic lookalikes)
    "0": "o",
    "1": "l",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "b",
    "8": "b",
    "@": "a",
    "|": "l",
    "ο": "o",   # Greek omicron
    "а": "a",   # Cyrillic а
    "е": "e",   # Cyrillic е
    "і": "i",   # Cyrillic і
    "о": "o",   # Cyrillic о
    "р": "p",   # Cyrillic р
    "с": "c",   # Cyrillic с
    "ν": "v",   # Greek nu
    "μ": "u",   # Greek mu
}

# Multi-char substitutions checked separately
MULTI_CHAR_SUBS = {
    "rn": "m",
    "vv": "w",
    "cl": "d",
    "li": "h",
    "nn": "m",
    "ij": "y",
}

# Common combosquatting prefixes/suffixes
COMBOSQUATTING_KEYWORDS = [
    "secure", "verify", "login", "signin", "account",
    "update", "alert", "confirm", "support", "help",
    "service", "official", "portal", "online", "web",
    "safe", "auth", "banking", "pay", "payment",
    "reset", "password", "mail", "inbox", "id",
]


# ─── Data classes ────────────────────────────────────────────────────────────────

@dataclass
class DomainAnalysis:
    """Hasil analisis satu URL / domain."""
    original_url: str
    extracted_domain: str
    is_suspicious: bool
    lookalike_of: Optional[str]             # Protected domain yang paling mirip
    similarity_score: float                 # 0.0 = tidak mirip, 1.0 = identik
    attack_type: Optional[str]              # "typosquatting" | "combosquatting" | "homograph" | None
    levenshtein_distance: int
    jaro_winkler_score: float
    domain_age_days: Optional[int]
    risk_level: str                         # "HIGH" | "MEDIUM" | "LOW" | "SAFE"
    reasons: List[str] = field(default_factory=list)


# ─── Levenshtein distance ─────────────────────────────────────────────────────────

def levenshtein_distance(s1: str, s2: str) -> int:
    """Standard Levenshtein distance (edit distance)."""
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1

    # DP matrix — space-optimized (two rows)
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)
    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,       # insertion
                prev[j] + 1,           # deletion
                prev[j - 1] + cost,    # substitution
            )
        prev, curr = curr, [0] * (len2 + 1)
    return prev[len2]


# ─── Jaro-Winkler similarity ──────────────────────────────────────────────────────

def jaro_similarity(s1: str, s2: str) -> float:
    """Jaro similarity score (0.0–1.0)."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_dist = max(len1, len2) // 2 - 1
    match_dist = max(0, match_dist)

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3.0


def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    """Jaro-Winkler similarity (0.0–1.0). Higher = more similar."""
    jaro = jaro_similarity(s1, s2)
    prefix_len = 0
    for i in range(min(4, len(s1), len(s2))):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return jaro + prefix_len * p * (1.0 - jaro)


# ─── Normalization helpers ────────────────────────────────────────────────────────

def normalize_homographs(domain: str) -> str:
    """Substitute visual confusables with ASCII equivalents."""
    # NFKC normalize first (handles Unicode homoglyphs)
    normalized = unicodedata.normalize("NFKC", domain).lower()
    # Apply char-level substitutions
    result = []
    i = 0
    while i < len(normalized):
        # Check multi-char subs first
        found_multi = False
        for src, dst in MULTI_CHAR_SUBS.items():
            if normalized[i:i + len(src)] == src:
                result.append(dst)
                i += len(src)
                found_multi = True
                break
        if not found_multi:
            c = normalized[i]
            result.append(HOMOGRAPH_MAP.get(c, c))
            i += 1
    return "".join(result)


def extract_root_domain(domain: str) -> str:
    """
    Strip www and subdomains but keep known multi-part TLDs.
    lodaya.co.id → lodaya.co.id
    login.lodaya.id → lodaya.id
    """
    domain = domain.lower().strip(".")
    # Remove www prefix
    if domain.startswith("www."):
        domain = domain[4:]

    # Known multi-part TLDs in Indonesia
    multi_tlds = [".co.id", ".or.id", ".ac.id", ".net.id", ".web.id", ".sch.id"]
    for tld in multi_tlds:
        if domain.endswith(tld):
            # Keep only last 2 labels before TLD
            parts = domain[: -len(tld)].split(".")
            return parts[-1] + tld

    # For standard TLDs: keep last 2 labels
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def extract_domain_from_url(url: str) -> str:
    """Extract hostname from URL string."""
    url = url.strip()
    if not url.startswith(("http://", "https://", "ftp://")):
        url = "http://" + url
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return url


# ─── DNS age check ────────────────────────────────────────────────────────────────

def get_domain_age_days(domain: str) -> Optional[int]:
    """
    Best-effort domain age check via WHOIS.
    Returns None if unavailable (don't block on DNS errors).
    """
    try:
        import whois  # python-whois — optional dependency
        w = whois.whois(domain)
        creation_date = w.creation_date
        if creation_date is None:
            return None
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        from datetime import datetime, timezone
        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - creation_date).days
        return max(0, age)
    except ImportError:
        logger.debug("python-whois not installed; skipping domain age check")
        return None
    except Exception as e:
        logger.debug("Domain age check failed for %s: %s", domain, e)
        return None


def is_domain_resolvable(domain: str) -> bool:
    """Check if domain resolves (basic DNS check)."""
    try:
        socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
        return True
    except socket.gaierror:
        return False


# ─── Main DomainChecker class ────────────────────────────────────────────────────

class DomainChecker:
    """
    Heuristic domain lookalike detector.

    Cek URL / domain apakah mirip dengan protected domains LTI
    menggunakan kombinasi Levenshtein, Jaro-Winkler, homograph, dan combosquatting detection.
    """

    # Risk thresholds
    LEVE_HIGH = 2      # edit distance ≤ 2 → HIGH RISK
    LEVE_MEDIUM = 4    # edit distance ≤ 4 → MEDIUM RISK
    JW_HIGH = 0.92     # Jaro-Winkler ≥ 0.92 → HIGH RISK
    JW_MEDIUM = 0.85   # Jaro-Winkler ≥ 0.85 → MEDIUM RISK
    NEW_DOMAIN_DAYS = 30  # domain < 30 hari = suspicious

    def __init__(self, protected_domains: Optional[List[str]] = None):
        self.protected_domains = protected_domains or _load_protected_domains()
        # Pre-compute normalized versions of protected domains
        self._protected_roots = [
            (d, extract_root_domain(d), normalize_homographs(extract_root_domain(d)))
            for d in self.protected_domains
        ]

    def check(self, url: str) -> DomainAnalysis:
        """
        Analyze a URL for domain lookalike attacks.

        Args:
            url: Full URL or bare domain to analyze

        Returns:
            DomainAnalysis with full details
        """
        extracted = extract_domain_from_url(url)
        if not extracted:
            return DomainAnalysis(
                original_url=url, extracted_domain="", is_suspicious=False,
                lookalike_of=None, similarity_score=0.0, attack_type=None,
                levenshtein_distance=999, jaro_winkler_score=0.0,
                domain_age_days=None, risk_level="UNKNOWN",
                reasons=["Could not extract domain from URL"],
            )

        root = extract_root_domain(extracted)
        normalized_root = normalize_homographs(root)
        reasons: List[str] = []
        best_match = None
        best_lev = 999
        best_jw = 0.0
        attack_type = None

        for (orig_domain, prot_root, prot_normalized) in self._protected_roots:
            # Skip if it's literally the same domain (not suspicious)
            if root == prot_root:
                return DomainAnalysis(
                    original_url=url, extracted_domain=extracted,
                    is_suspicious=False, lookalike_of=orig_domain,
                    similarity_score=1.0, attack_type=None,
                    levenshtein_distance=0, jaro_winkler_score=1.0,
                    domain_age_days=None, risk_level="SAFE",
                    reasons=["Domain matches protected domain exactly"],
                )

            lev = levenshtein_distance(normalized_root, prot_normalized)
            jw = jaro_winkler(normalized_root, prot_normalized)

            if lev < best_lev or jw > best_jw:
                best_lev = lev
                best_jw = jw
                best_match = orig_domain

            # Homograph check: normalized differs from original
            if normalized_root != root and normalized_root == prot_normalized:
                attack_type = "homograph"
                reasons.append(
                    f"Homograph attack: '{root}' normalizes to '{prot_normalized}' "
                    f"(looks like {orig_domain})"
                )

            # Combosquatting: protected domain name appears as substring
            prot_name = prot_root.split(".")[0]  # e.g. "lodaya"
            if prot_name in root and root != prot_root:
                for kw in COMBOSQUATTING_KEYWORDS:
                    if kw in root:
                        if attack_type is None:
                            attack_type = "combosquatting"
                        reasons.append(
                            f"Combosquatting: '{root}' contains '{prot_name}' + "
                            f"keyword '{kw}' (targets {orig_domain})"
                        )
                        break

        if best_match is None:
            return DomainAnalysis(
                original_url=url, extracted_domain=extracted,
                is_suspicious=False, lookalike_of=None,
                similarity_score=0.0, attack_type=None,
                levenshtein_distance=999, jaro_winkler_score=0.0,
                domain_age_days=None, risk_level="SAFE",
            )

        # Determine typosquatting
        if best_lev <= self.LEVE_HIGH and attack_type is None:
            attack_type = "typosquatting"
            reasons.append(
                f"Typosquatting: '{root}' is {best_lev} edit(s) away from '{best_match}'"
            )
        elif best_lev <= self.LEVE_MEDIUM and attack_type is None:
            attack_type = "typosquatting"
            reasons.append(
                f"Near-typosquatting: '{root}' is {best_lev} edits from '{best_match}'"
            )

        # DNS / age check (optional, best-effort)
        domain_age = get_domain_age_days(extracted)
        if domain_age is not None and domain_age < self.NEW_DOMAIN_DAYS:
            reasons.append(
                f"New domain: registered only {domain_age} day(s) ago (< {self.NEW_DOMAIN_DAYS} days)"
            )

        # Risk level determination
        is_suspicious = False
        if attack_type == "homograph":
            risk_level = "HIGH"
            is_suspicious = True
        elif attack_type == "combosquatting":
            risk_level = "HIGH"
            is_suspicious = True
        elif best_lev <= self.LEVE_HIGH or best_jw >= self.JW_HIGH:
            risk_level = "HIGH"
            is_suspicious = True
        elif best_lev <= self.LEVE_MEDIUM or best_jw >= self.JW_MEDIUM:
            risk_level = "MEDIUM"
            is_suspicious = True
        elif domain_age is not None and domain_age < self.NEW_DOMAIN_DAYS:
            risk_level = "LOW"
            is_suspicious = True
        else:
            risk_level = "SAFE"
            is_suspicious = False
            best_match = None

        similarity_score = round(best_jw, 4)

        return DomainAnalysis(
            original_url=url,
            extracted_domain=extracted,
            is_suspicious=is_suspicious,
            lookalike_of=best_match if is_suspicious else None,
            similarity_score=similarity_score,
            attack_type=attack_type if is_suspicious else None,
            levenshtein_distance=best_lev,
            jaro_winkler_score=round(best_jw, 4),
            domain_age_days=domain_age,
            risk_level=risk_level,
            reasons=reasons,
        )

    def check_many(self, urls: List[str]) -> List[DomainAnalysis]:
        """Analyze multiple URLs and return list of results."""
        return [self.check(url) for url in urls]

    def any_suspicious(self, urls: List[str]) -> bool:
        """Quick check: True if ANY URL is suspicious."""
        return any(self.check(u).is_suspicious for u in urls)


# ─── Module-level singleton ───────────────────────────────────────────────────────

_checker: Optional[DomainChecker] = None


def get_checker() -> DomainChecker:
    """Get or create a module-level DomainChecker singleton."""
    global _checker
    if _checker is None:
        _checker = DomainChecker()
    return _checker


def check_lookalike_domain(url: str) -> DomainAnalysis:
    """Convenience function — check a single URL using the singleton checker."""
    return get_checker().check(url)
