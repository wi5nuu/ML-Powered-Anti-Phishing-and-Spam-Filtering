"""Deterministic high-risk content guards used after statistical scoring."""

import re


PHISHING_STRONG_HINTS = (
    "verify your account", "verify account", "confirm your account",
    "account suspended", "account locked", "update your account",
    "security alert", "unusual activity", "credential", "password",
    "login", "log in", "reset your", "verifikasi", "konfirmasi",
    "submit your payment information", "payment information", "bank details",
    "credit card details", "banking password", "confirm your credentials",
    "confirm your password", "mailbox is full", "mailbox full",
    "mailbox quota", "account will be blocked", "account will be deleted",
)
SUSPICIOUS_URL_HINTS = (
    "secure-account", "account-verification", "verification", "verify",
    "login", "signin", "password", "session", "update",
)
SPAM_STRONG_HINTS = (
    "lose weight", "life insurance", "insurance", "mortgage", "viagra",
    "lowest price", "special offer", "earn money", "cash grants",
    "fortune 500", "at home reps", "customer base", "e-mail marketing",
    "email marketing", "limited time", "guaranteed to lose",
    "membership to 5 sites", "multiply your customer", "bank account",
    "adult dvd", "adult content", "porn", "free cell phone", "cash back",
    "blood pressure", "cholesterol", "save on your medications", "cheap meds",
    "best quality", "per minute", "wives and girlfriends", "click.yahoo.com",
    # Indonesian unsolicited-promotion patterns. A phrase match alone never
    # quarantines a message; it is corroborated by statistical scoring below.
    "hadiah gratis", "diskon 90", "pemenang undian", "obat murah",
    "tanpa resep", "hasilkan uang", "promo kasino", "jackpot kasino",
    "pinjaman instan", "produk ajaib", "turunkan berat badan",
    "keuntungan pasti", "kupon gratis", "beli sekarang", "klaim bonus",
    "penawaran terbatas",
)
RULE_ONLY_THREAT_HINTS = (
    "submit your payment information", "credit card information",
    "send your banking details", "huge and rock hard",
)
CREDENTIAL_REQUEST_HINTS = (
    "password", "credential", "login", "log in", "credit card details",
    "bank details", "banking password", "national id", "identity details",
    "kredensial", "rekening bank", "konfirmasi kartu", "nomor kartu",
    "kode otp", "pin dan password",
)
ACCOUNT_SCARE_HINTS = (
    "account suspended", "account locked", "account will be blocked",
    "account will be deleted", "mailbox is full", "mailbox full",
    "mailbox quota", "retain access", "avoid closure", "security alert",
    "akun akan dinonaktifkan", "akun akan dikunci", "akun tidak diblokir",
    "kotak surat akan dihapus",
)
URGENCY_HINTS = (
    "urgent", "immediately", "immediate action", "within 30 minutes",
    "act now", "today", "expires tonight", "segera", "mendesak",
    "hari ini", "dalam 15 menit",
)
BEC_PAYMENT_HINTS = (
    "wire transfer", "bank transfer", "urgent payment", "process payment",
    "gift card", "transfer money",
)
BEC_SECRECY_HINTS = (
    "do not discuss", "keep this confidential", "confidential",
    "i am in a meeting", "i'm in a meeting", "cannot talk", "can't talk",
)
DANGEROUS_ATTACHMENT_EXTENSIONS = (
    "exe", "scr", "bat", "cmd", "com", "pif", "vbs", "js", "jar",
    "ps1", "hta", "msi", "dll", "docm", "xlsm", "pptm",
)


def _urls_from_text(raw_email: str) -> list[str]:
    return re.findall(r"https?://[^\s\"'<>)]{4,}", raw_email or "", flags=re.IGNORECASE)


def dangerous_attachment_name(raw_email: str) -> str:
    """Return a risky MIME attachment filename, if one is present."""
    extension_pattern = "|".join(map(re.escape, DANGEROUS_ATTACHMENT_EXTENSIONS))
    match = re.search(
        rf"(?im)\bfilename\*?\s*=\s*(?:utf-8''|[\"'])?([^\"';\r\n]+\.(?:{extension_pattern}))\b",
        raw_email or "",
    )
    return match.group(1).strip() if match else ""


def content_threat_evidence(
    raw_email: str,
    ml_probability: float,
    sa_score: float,
    anomaly_score: float,
) -> tuple[str, str]:
    """Return a category and auditable reason for deterministic threat evidence."""
    text = (raw_email or "").lower()
    urls = [url.lower() for url in _urls_from_text(raw_email)]

    phishing_hint = any(hint in text for hint in PHISHING_STRONG_HINTS)
    suspicious_url = any(any(hint in url for hint in SUSPICIOUS_URL_HINTS) for url in urls)
    spam_matches = {hint for hint in SPAM_STRONG_HINTS if hint in text}
    spam_hint = bool(spam_matches)
    credential_hint = any(hint in text for hint in CREDENTIAL_REQUEST_HINTS)
    account_scare = any(hint in text for hint in ACCOUNT_SCARE_HINTS)
    urgency_hint = any(hint in text for hint in URGENCY_HINTS)
    bec_payment = any(hint in text for hint in BEC_PAYMENT_HINTS)
    bec_secrecy = any(hint in text for hint in BEC_SECRECY_HINTS)
    has_url = bool(urls)
    dangerous_attachment = dangerous_attachment_name(raw_email)

    # Executable/script and macro-enabled attachments are treated as phishing
    # for the mailbox taxonomy, and always require quarantine review. The
    # filename remains in the auditable reason so this mapping does not hide
    # the original malware evidence.
    if dangerous_attachment:
        return "phishing", f"dangerous attachment={dangerous_attachment}"

    if (
        credential_hint and has_url
        and (urgency_hint or account_scare or suspicious_url)
        and (ml_probability >= 0.35 or sa_score >= 4.0 or anomaly_score >= 0.60)
    ):
        evidence = ["credential request", "external link"]
        if urgency_hint:
            evidence.append("urgency language")
        if account_scare:
            evidence.append("account/mailbox pressure")
        if suspicious_url:
            evidence.append("verification/login URL")
        evidence.extend((
            f"ML={ml_probability:.3f}", f"SA={sa_score:.1f}",
            f"anomaly={anomaly_score:.3f}",
        ))
        return "phishing", ", ".join(evidence)

    if (
        bec_payment and bec_secrecy and urgency_hint
        and (ml_probability >= 0.25 or sa_score >= 4.0 or anomaly_score >= 0.40)
    ):
        return (
            "phishing",
            "BEC payment request, secrecy language, urgency language, "
            f"ML={ml_probability:.3f}, SA={sa_score:.1f}, anomaly={anomaly_score:.3f}",
        )

    rule_only_hint = next((hint for hint in RULE_ONLY_THREAT_HINTS if hint in text), "")
    if rule_only_hint and sa_score >= 5.0 and anomaly_score >= 0.60:
        return "spam", f"explicit high-risk phrase={rule_only_hint}, SA={sa_score:.1f}, anomaly={anomaly_score:.3f}"

    if spam_hint and not suspicious_url and (
        len(spam_matches) >= 2
        or ml_probability >= 0.70
        or (ml_probability >= 0.50 and (sa_score >= 5.0 or anomaly_score >= 0.70))
    ):
        evidence = [f"strong spam language ({', '.join(sorted(spam_matches))})"]
        if ml_probability >= 0.70:
            evidence.append(f"ML={ml_probability:.3f}")
        if sa_score >= 5.0:
            evidence.append(f"SA={sa_score:.1f}")
        if anomaly_score >= 0.70:
            evidence.append(f"anomaly={anomaly_score:.3f}")
        return "spam", ", ".join(evidence)

    if ml_probability >= 0.85 and phishing_hint and (suspicious_url or anomaly_score >= 0.72 or sa_score >= 8.0):
        evidence = ["ML high", "phishing language"]
        if suspicious_url:
            evidence.append("suspicious verification/login URL")
        if anomaly_score >= 0.72:
            evidence.append(f"anomaly={anomaly_score:.3f}")
        if sa_score >= 8.0:
            evidence.append(f"SA={sa_score:.1f}")
        return "phishing", ", ".join(evidence)

    if ml_probability >= 0.85 and spam_hint and (sa_score >= 5.0 or anomaly_score >= 0.72):
        evidence = ["ML high", "strong spam language"]
        if sa_score >= 5.0:
            evidence.append(f"SA={sa_score:.1f}")
        if anomaly_score >= 0.72:
            evidence.append(f"anomaly={anomaly_score:.3f}")
        return "spam", ", ".join(evidence)

    return "", ""
