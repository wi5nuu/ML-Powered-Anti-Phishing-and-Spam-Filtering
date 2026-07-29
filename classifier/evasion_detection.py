"""
Advanced Evasion Detection Module for CogniMail

This module implements state-of-the-art detection for advanced phishing evasion techniques:
1. Homograph/IDN attacks (using lookalike characters)
2. Zero-width character injection
3. HTML/JavaScript obfuscation
4. Base64/URL encoding tricks
5. Punycode attacks
6. Mixed-script attacks
7. RTL override attacks

These techniques are commonly used by attackers to bypass traditional detection.
"""

import re
import html
import unicodedata
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ── Homograph Attack Detection ───────────────────────────────────────────────

# Common lookalike characters used in homograph attacks
HOMOGRAPH_MAP = {
    # Latin lookalikes
    'a': ['а', 'ạ', 'ă', 'ą', 'ά', 'α', 'а'],  # Cyrillic а, Greek α
    'c': ['с', 'ϲ', 'ⅽ'],  # Cyrillic с
    'e': ['е', 'ė', 'ę', 'ё', 'ε', 'е'],  # Cyrillic е, Greek ε
    'i': ['і', 'ı', 'ί', 'ι', 'і'],  # Cyrillic і, Greek ι
    'o': ['о', 'ο', 'օ', 'ο', 'о'],  # Cyrillic о, Greek ο
    'p': ['р', 'ρ', 'р'],  # Cyrillic р, Greek ρ
    's': ['ѕ', 'ś', 'š'],  # Cyrillic ѕ
    'x': ['х', 'χ', 'х'],  # Cyrillic х, Greek χ
    'y': ['у', 'ý', 'ÿ', 'у'],  # Cyrillic у
    
    # Commonly spoofed brands
    'g': ['ɡ', 'ց', 'ǥ'],  # Latin small letter script g
    'm': ['м', 'ṁ', 'м'],  # Cyrillic м
    'n': ['ո', 'ñ', 'ń'],
    'l': ['ӏ', 'Ӏ', '1', 'I'],  # Cyrillic palochka, digit 1, capital I
    '0': ['о', 'ο', 'О', 'O'],  # Zero vs O
}

# Protected domains to check for homograph attacks
PROTECTED_BRANDS = [
    'paypal', 'google', 'microsoft', 'amazon', 'apple', 'facebook',
    'instagram', 'twitter', 'linkedin', 'netflix', 'adobe', 'dropbox',
    'github', 'gitlab', 'yahoo', 'outlook', 'gmail', 'icloud',
    'bank', 'visa', 'mastercard', 'amex', 'chase', 'wellsfargo'
]


def detect_homograph_attack(domain: str) -> Tuple[bool, float, str]:
    """
    Detect homograph/IDN attacks in domain names.
    
    Returns:
        (is_suspicious, confidence, details)
    """
    if not domain:
        return False, 0.0, ""
    
    domain_lower = domain.lower()
    suspicious = False
    confidence = 0.0
    details = []
    
    # Check for mixed scripts (major red flag)
    scripts = set()
    for char in domain_lower:
        if char.isalpha():
            script = unicodedata.name(char, '').split()[0]
            scripts.add(script)
    
    if len(scripts) > 1:
        suspicious = True
        confidence += 0.5
        details.append(f"Mixed scripts detected: {scripts}")
    
    # Check for lookalike characters
    for original_char, lookalikes in HOMOGRAPH_MAP.items():
        for lookalike in lookalikes:
            if lookalike in domain_lower:
                suspicious = True
                confidence += 0.3
                details.append(f"Lookalike character '{lookalike}' (resembles '{original_char}')")
    
    # Check for punycode (xn--)
    if domain_lower.startswith('xn--') or 'xn--' in domain_lower:
        suspicious = True
        confidence += 0.4
        details.append("Punycode IDN detected")
        
        # Decode punycode
        try:
            decoded = domain.encode('utf-8').decode('idna')
            if decoded != domain:
                details.append(f"Decoded: {decoded}")
        except:
            pass
    
    # Check if it's spoofing a protected brand
    for brand in PROTECTED_BRANDS:
        # Calculate similarity
        similarity = calculate_visual_similarity(domain_lower, brand)
        if similarity > 0.7:  # High visual similarity
            suspicious = True
            confidence += 0.6
            details.append(f"Possible {brand} spoofing (similarity: {similarity:.2f})")
    
    confidence = min(confidence, 1.0)  # Cap at 1.0
    details_str = "; ".join(details) if details else "No homograph detected"
    
    return suspicious, confidence, details_str


def calculate_visual_similarity(str1: str, str2: str) -> float:
    """Calculate visual similarity between two strings considering lookalikes."""
    if not str1 or not str2:
        return 0.0
    
    # Normalize both strings by replacing lookalikes with originals
    normalized1 = normalize_lookalikes(str1)
    normalized2 = normalize_lookalikes(str2)
    
    # Simple character-based similarity
    matches = sum(c1 == c2 for c1, c2 in zip(normalized1, normalized2))
    max_len = max(len(normalized1), len(normalized2))
    
    return matches / max_len if max_len > 0 else 0.0


def normalize_lookalikes(text: str) -> str:
    """Replace lookalike characters with their original ASCII equivalents."""
    result = text.lower()
    
    for original, lookalikes in HOMOGRAPH_MAP.items():
        for lookalike in lookalikes:
            result = result.replace(lookalike, original)
    
    return result


# ── Zero-Width Character Detection ───────────────────────────────────────────

ZERO_WIDTH_CHARS = [
    '\u200B',  # Zero-width space
    '\u200C',  # Zero-width non-joiner
    '\u200D',  # Zero-width joiner
    '\u200E',  # Left-to-right mark
    '\u200F',  # Right-to-left mark
    '\uFEFF',  # Zero-width no-break space (BOM)
    '\u2060',  # Word joiner
    '\u2061',  # Function application
    '\u2062',  # Invisible times
    '\u2063',  # Invisible separator
    '\u2064',  # Invisible plus
]


def detect_zero_width_chars(text: str) -> Tuple[bool, int, List[str]]:
    """
    Detect zero-width and invisible characters that may hide malicious content.
    
    Returns:
        (is_suspicious, count, char_details)
    """
    if not text:
        return False, 0, []
    
    found_chars = []
    total_count = 0
    
    for zwc in ZERO_WIDTH_CHARS:
        count = text.count(zwc)
        if count > 0:
            total_count += count
            char_name = unicodedata.name(zwc, f'U+{ord(zwc):04X}')
            found_chars.append(f"{char_name} ({count}x)")
    
    # More than 3 zero-width chars is highly suspicious
    is_suspicious = total_count > 3
    
    return is_suspicious, total_count, found_chars


# ── HTML/JavaScript Obfuscation Detection ────────────────────────────────────

OBFUSCATION_PATTERNS = [
    # JavaScript obfuscation
    (r'eval\s*\(', 'eval() execution'),
    (r'document\.write\s*\(', 'document.write()'),
    (r'fromCharCode|charCodeAt', 'Character code conversion'),
    (r'\\x[0-9a-fA-F]{2}', 'Hex escape sequences'),
    (r'\\u[0-9a-fA-F]{4}', 'Unicode escape sequences'),
    (r'atob\s*\(', 'Base64 decoding (atob)'),
    (r'unescape\s*\(', 'URL unescape'),
    
    # HTML entity obfuscation
    (r'&#x[0-9a-fA-F]+;', 'Hex HTML entities'),
    (r'&#\d+;', 'Decimal HTML entities'),
    
    # Heavy obfuscation indicators
    (r'[a-zA-Z0-9+/]{40,}={0,2}', 'Long Base64 string'),
    (r'(\w)\1{10,}', 'Character repetition'),
    
    # Suspicious script patterns
    (r'<script[^>]*>.*?</script>', 'Inline script tag', re.DOTALL),
    (r'javascript:', 'JavaScript protocol'),
    (r'vbscript:', 'VBScript protocol'),
    (r'data:text/html', 'Data URI HTML'),
]


def detect_obfuscation(html_content: str) -> Tuple[bool, float, List[str]]:
    """
    Detect HTML/JavaScript obfuscation techniques.
    
    Returns:
        (is_obfuscated, confidence, techniques_detected)
    """
    if not html_content:
        return False, 0.0, []
    
    techniques_found = []
    confidence = 0.0
    
    for pattern, description, *flags in OBFUSCATION_PATTERNS:
        flag = flags[0] if flags else 0
        matches = re.findall(pattern, html_content, flag)
        
        if matches:
            count = len(matches)
            techniques_found.append(f"{description} ({count}x)")
            confidence += min(0.2 * count, 0.5)  # Cap per technique
    
    # Check for excessive HTML entities (obfuscation technique)
    entity_count = len(re.findall(r'&#?[a-zA-Z0-9]+;', html_content))
    if entity_count > 20:
        techniques_found.append(f"Excessive HTML entities ({entity_count})")
        confidence += 0.3
    
    is_obfuscated = len(techniques_found) > 0
    confidence = min(confidence, 1.0)
    
    return is_obfuscated, confidence, techniques_found


# ── Base64/URL Encoding Detection ────────────────────────────────────────────

def detect_suspicious_encoding(text: str) -> Tuple[bool, List[str]]:
    """
    Detect suspicious encoding patterns used to hide malicious content.
    
    Returns:
        (is_suspicious, encoding_types)
    """
    if not text:
        return False, []
    
    encodings_found = []
    
    # Detect Base64 - more lenient threshold
    base64_pattern = r'[A-Za-z0-9+/]{30,}={0,2}'
    base64_matches = re.findall(base64_pattern, text)
    if len(base64_matches) >= 3:
        encodings_found.append(f"Multiple Base64 strings ({len(base64_matches)})")
    
    # Detect URL encoding overuse
    url_encoded = re.findall(r'%[0-9A-Fa-f]{2}', text)
    if len(url_encoded) > 10:
        encodings_found.append(f"Excessive URL encoding ({len(url_encoded)} sequences)")
    
    # Detect double/triple encoding (evasion technique)
    double_encoded = re.findall(r'%25[0-9A-Fa-f]{2}', text)  # %25 is encoded %
    if double_encoded:
        encodings_found.append(f"Double URL encoding detected ({len(double_encoded)}x)")
    
    # Detect HTML entity overuse
    html_entities = re.findall(r'&#[0-9]+;|&#x[0-9A-Fa-f]+;', text)
    if len(html_entities) > 15:
        encodings_found.append(f"Excessive HTML entities ({len(html_entities)})")
    
    is_suspicious = len(encodings_found) > 0
    
    return is_suspicious, encodings_found


# ── RTL Override Attack Detection ─────────────────────────────────────────────

RTL_OVERRIDE_CHARS = [
    '\u202E',  # Right-to-left override (RLO)
    '\u202D',  # Left-to-right override (LRO)
    '\u202A',  # Left-to-right embedding
    '\u202B',  # Right-to-left embedding
    '\u202C',  # Pop directional formatting
]


def detect_rtl_override(text: str) -> Tuple[bool, int, str]:
    """
    Detect RTL override attacks (used to hide file extensions).
    
    Example: "invoice[RLO]gpj.exe" displays as "invoice.exe.jpg"
    
    Returns:
        (is_attack, count, details)
    """
    if not text:
        return False, 0, ""
    
    rtl_count = 0
    rtl_types = []
    
    for rtl_char in RTL_OVERRIDE_CHARS:
        count = text.count(rtl_char)
        if count > 0:
            rtl_count += count
            char_name = unicodedata.name(rtl_char, f'U+{ord(rtl_char):04X}')
            rtl_types.append(f"{char_name} ({count}x)")
    
    is_attack = rtl_count > 0
    details = "; ".join(rtl_types) if rtl_types else ""
    
    return is_attack, rtl_count, details


# ── Master Evasion Detection Function ────────────────────────────────────────

@dataclass
class EvasionDetectionResult:
    """Complete evasion detection result."""
    is_evasion_detected: bool
    overall_confidence: float
    homograph_detected: bool
    homograph_confidence: float
    homograph_details: str
    zero_width_detected: bool
    zero_width_count: int
    zero_width_chars: List[str]
    obfuscation_detected: bool
    obfuscation_confidence: float
    obfuscation_techniques: List[str]
    encoding_detected: bool
    encoding_types: List[str]
    rtl_override_detected: bool
    rtl_override_count: int
    rtl_override_details: str
    summary: str


def detect_evasion_techniques(
    subject: str = "",
    body_text: str = "",
    body_html: str = "",
    urls: List[str] = None
) -> EvasionDetectionResult:
    """
    Comprehensive evasion technique detection across all email components.
    
    Args:
        subject: Email subject line
        body_text: Plain text body
        body_html: HTML body
        urls: List of URLs found in email
    
    Returns:
        EvasionDetectionResult with detailed findings
    """
    urls = urls or []
    combined_text = f"{subject} {body_text}"
    
    # 1. Homograph detection on URLs and domains
    homograph_detected = False
    homograph_confidence = 0.0
    homograph_details = []
    
    for url in urls:
        # Extract domain from URL
        domain_match = re.search(r'://([^/:]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            is_sus, conf, details = detect_homograph_attack(domain)
            if is_sus:
                homograph_detected = True
                homograph_confidence = max(homograph_confidence, conf)
                homograph_details.append(f"{domain}: {details}")
    
    # 2. Zero-width character detection
    zw_detected, zw_count, zw_chars = detect_zero_width_chars(combined_text)
    
    # 3. Obfuscation detection
    obf_detected, obf_conf, obf_techs = detect_obfuscation(body_html)
    
    # 4. Encoding detection
    enc_detected, enc_types = detect_suspicious_encoding(body_html)
    
    # 5. RTL override detection
    rtl_detected, rtl_count, rtl_details = detect_rtl_override(combined_text)
    
    # Calculate overall confidence
    confidences = [
        homograph_confidence,
        0.8 if zw_detected and zw_count > 5 else 0.0,
        obf_conf,
        0.6 if enc_detected else 0.0,
        0.9 if rtl_detected else 0.0,
    ]
    overall_confidence = max(confidences) if any(confidences) else 0.0
    
    # Determine if evasion detected
    is_evasion = any([
        homograph_detected,
        zw_detected,
        obf_detected,
        enc_detected,
        rtl_detected,
    ])
    
    # Generate summary
    summary_parts = []
    if homograph_detected:
        summary_parts.append(f"Homograph attack ({homograph_confidence:.0%} confidence)")
    if zw_detected:
        summary_parts.append(f"{zw_count} zero-width characters")
    if obf_detected:
        summary_parts.append(f"Obfuscation ({len(obf_techs)} techniques)")
    if enc_detected:
        summary_parts.append(f"Suspicious encoding ({len(enc_types)} types)")
    if rtl_detected:
        summary_parts.append(f"RTL override attack ({rtl_count} chars)")
    
    summary = "; ".join(summary_parts) if summary_parts else "No evasion detected"
    
    return EvasionDetectionResult(
        is_evasion_detected=is_evasion,
        overall_confidence=overall_confidence,
        homograph_detected=homograph_detected,
        homograph_confidence=homograph_confidence,
        homograph_details="; ".join(homograph_details),
        zero_width_detected=zw_detected,
        zero_width_count=zw_count,
        zero_width_chars=zw_chars,
        obfuscation_detected=obf_detected,
        obfuscation_confidence=obf_conf,
        obfuscation_techniques=obf_techs,
        encoding_detected=enc_detected,
        encoding_types=enc_types,
        rtl_override_detected=rtl_detected,
        rtl_override_count=rtl_count,
        rtl_override_details=rtl_details,
        summary=summary,
    )


# ── Integration Example ───────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example usage
    
    # Test 1: Homograph attack
    print("Test 1: Homograph Attack")
    result = detect_evasion_techniques(
        subject="Verify your Pаypal account",  # Note: 'а' is Cyrillic
        urls=["https://pаypal.com/verify"]  # Cyrillic 'а'
    )
    print(f"  Evasion detected: {result.is_evasion_detected}")
    print(f"  Confidence: {result.overall_confidence:.2%}")
    print(f"  Summary: {result.summary}\n")
    
    # Test 2: Zero-width characters
    print("Test 2: Zero-Width Characters")
    text_with_zw = "Click here\u200B\u200C\u200D\u200B\u200C for prize"
    result = detect_evasion_techniques(subject=text_with_zw)
    print(f"  Evasion detected: {result.is_evasion_detected}")
    print(f"  Zero-width count: {result.zero_width_count}")
    print(f"  Summary: {result.summary}\n")
    
    # Test 3: HTML obfuscation
    print("Test 3: HTML Obfuscation")
    obfuscated_html = """
    <script>eval(atob('dmFyIHg9ZG9jdW1lbnQ='))</script>
    <a href="javascript:void(0)">Click</a>
    """
    result = detect_evasion_techniques(body_html=obfuscated_html)
    print(f"  Evasion detected: {result.is_evasion_detected}")
    print(f"  Obfuscation confidence: {result.obfuscation_confidence:.2%}")
    print(f"  Techniques: {result.obfuscation_techniques}\n")
