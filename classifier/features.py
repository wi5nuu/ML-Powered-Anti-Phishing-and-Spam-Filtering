"""
Feature engineering pipeline untuk LTI Anti-Phishing Classifier.

Menghasilkan fitur hibrida: sparse (TF-IDF text) + dense (structured).
Kedua tipe digabung sebelum masuk ke XGBoost.
"""

import re
import email
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import numpy as np
import tldextract
from rapidfuzz.distance import Levenshtein
import dns.resolver
from langdetect import detect, DetectorFactory
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

# Seed langdetect supaya deterministik
DetectorFactory.seed = 42

# Stemmer Bahasa Indonesia
_id_stemmer = StemmerFactory().create_stemmer()

logger = logging.getLogger(__name__)

# ─── Konstanta ───────────────────────────────────────────────────────────────

# Kata-kata urgensi dalam konteks phishing — dwibahasa
URGENCY_WORDS_ID = {
    "segera", "mendesak", "darurat", "verifikasi", "konfirmasi",
    "akun", "diblokir", "ditangguhkan", "klik", "sekarang", "batas",
    "hadiah", "menang", "gratis", "transfer", "rekening", "password",
    "kata sandi", "login", "masuk", "update", "perbarui", "kedaluwarsa"
}

URGENCY_WORDS_EN = {
    "urgent", "immediately", "verify", "confirm", "suspended",
    "blocked", "click", "now", "deadline", "prize", "winner",
    "free", "transfer", "account", "password", "login", "update",
    "expire", "limited", "act now", "congratulations"
}

URGENCY_WORDS = URGENCY_WORDS_ID | URGENCY_WORDS_EN

# Domain shortener yang sering dipakai phishing
URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "buff.ly",
    "adf.ly", "shorte.st", "linktr.ee", "rb.gy", "cutt.ly", "is.gd"
}

# Domain LTI yang harus dilindungi
PROTECTED_DOMAIN = "lodaya.id"

# ─── Fitur Terstruktur ───────────────────────────────────────────────────────

STRUCTURED_FEATURES = [
    "num_urls",
    "num_unique_domains",
    "has_url_shortener",
    "has_lookalike_domain",
    "min_levenshtein_to_protected",
    "num_attachments",
    "has_executable_attachment",
    "urgency_score",
    "html_text_ratio",
    "num_images",
    "spf_pass",
    "dkim_pass",
    "dmarc_pass",
    "display_name_mismatch",
    "subject_has_re_fwd_fake",
    "num_recipients",
    "is_bulk_sender",
    "entropy_of_links",
    "num_forms",
    "javascript_present",
    # ── Business context features ───────────────────────────────────────────
    "safe_business_score",
    "bec_score",
    "urgency_level",
    "sender_reputation",
    "has_generic_greeting",
    "request_for_transfer",
    "ceo_impersonation",
    "business_context_weight",
]

# ─── Data Model ──────────────────────────────────────────────────────────────

@dataclass
class EmailFeatures:
    """Representasi terstruktur dari semua fitur satu email."""

    # Text content
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    combined_text: str = ""       # Untuk TF-IDF

    # Structured features — semua ini masuk ke model sebagai angka
    num_urls: int = 0
    num_unique_domains: int = 0
    has_url_shortener: bool = False
    has_lookalike_domain: bool = False
    min_levenshtein_to_protected: int = 999
    num_attachments: int = 0
    has_executable_attachment: bool = False
    urgency_score: float = 0.0
    html_text_ratio: float = 0.0   # >1.0 sering tanda spam
    num_images: int = 0
    sender_domain_age_days: Optional[int] = None
    spf_pass: bool = False
    dkim_pass: bool = False
    dmarc_pass: bool = False
    display_name_mismatch: bool = False   # "Bank BCA" tapi email dari gmail
    subject_has_re_fwd_fake: bool = False # RE/FWD palsu di subject
    num_recipients: int = 1
    is_bulk_sender: bool = False
    detected_language: str = "unknown"
    entropy_of_links: float = 0.0   # Entropy Shannon dari link URL
    num_forms: int = 0              # Form HTML dalam email
    javascript_present: bool = False
    # ── Business context ───────────────────────────────────────────────────
    safe_business_score: float = 1.0   # 0 (unsafe) - 1.0 (safe business email)
    bec_score: float = 0.0             # 0-1 likelihood of BEC/CEO fraud
    urgency_level: float = 0.0         # Business urgency (not just keywords)
    sender_reputation: float = 1.0     # 0 (malicious domain) - 1.0 (known corp)
    has_generic_greeting: bool = False # "Dear Sir/Madam" instead of personal
    request_for_transfer: bool = False # Asks for wire transfer / payment
    ceo_impersonation: bool = False    # Sender pretends to be C-level
    business_context_weight: float = 0.5  # Overall business relevance 0-1


@dataclass
class ParsedEmail:
    """Email yang sudah diparsing dari raw bytes/string."""
    raw_id: str                       # SHA-256 dari raw content
    sender: str = ""
    sender_domain: str = ""
    display_name: str = ""
    recipient_list: list = field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    headers: dict = field(default_factory=dict)
    attachments: list = field(default_factory=list)
    urls: list = field(default_factory=list)
    received_spf: str = ""
    dkim_signature: bool = False
    authentication_results: str = ""
    raw_content: str = ""


# ─── Parser ──────────────────────────────────────────────────────────────────

class EmailParser:
    """Parser email dari raw string ke ParsedEmail."""

    EXECUTABLE_EXTENSIONS = {
        ".exe", ".js", ".vbs", ".bat", ".cmd", ".ps1", ".jar",
        ".com", ".scr", ".pif", ".hta", ".msi", ".docm", ".xlsm"
    }

    URL_PATTERN = re.compile(
        r'https?://[^\s<>"\'()]+',
        re.IGNORECASE
    )

    def parse(self, raw_email_str: str) -> ParsedEmail:
        """Parse raw email string -> ParsedEmail."""
        msg = email.message_from_string(raw_email_str)

        # Hash untuk deduplikasi
        raw_id = hashlib.sha256(raw_email_str.encode()).hexdigest()

        # Sender parsing
        from_header = msg.get("From", "")
        sender, display_name = self._parse_from(from_header)
        sender_domain = sender.split("@")[-1].lower() if "@" in sender else ""

        # Recipients
        recipients = []
        for field in ["To", "Cc", "Bcc"]:
            if msg.get(field):
                recipients.extend(msg.get(field, "").split(","))

        # Body parsing
        body_text, body_html = self._extract_body(msg)

        # URLs
        all_text = body_text + " " + body_html
        urls = list(set(self.URL_PATTERN.findall(all_text)))

        # Attachments
        attachments = self._extract_attachments(msg)

        # Auth headers
        auth_results = msg.get("Authentication-Results", "")
        received_spf = msg.get("Received-SPF", "")
        dkim_sig = bool(msg.get("DKIM-Signature"))

        return ParsedEmail(
            raw_id=raw_id,
            sender=sender,
            sender_domain=sender_domain,
            display_name=display_name,
            recipient_list=[r.strip() for r in recipients if r.strip()],
            subject=msg.get("Subject", ""),
            body_text=body_text,
            body_html=body_html,
            headers=dict(msg.items()),
            attachments=attachments,
            urls=urls,
            received_spf=received_spf,
            dkim_signature=dkim_sig,
            authentication_results=auth_results,
            raw_content=raw_email_str,
        )

    def _parse_from(self, from_header: str) -> tuple[str, str]:
        """Ekstrak email address dan display name dari header From."""
        from email.utils import parseaddr
        display_name, email_addr = parseaddr(from_header)
        return email_addr.lower(), display_name

    def _extract_body(self, msg) -> tuple[str, str]:
        """Ekstrak plain text dan HTML body dari pesan multipart."""
        body_text = ""
        body_html = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_text += part.get_payload(decode=True).decode(
                            charset, errors="replace"
                        )
                    except Exception:
                        pass
                elif ctype == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_html += part.get_payload(decode=True).decode(
                            charset, errors="replace"
                        )
                    except Exception:
                        pass
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    decoded = payload.decode("utf-8", errors="replace")
                if msg.get_content_type() == "text/html":
                    body_html = decoded
                else:
                    body_text = decoded
        return body_text, body_html

    def _extract_attachments(self, msg) -> list[dict]:
        """Daftarkan semua attachment beserta metadata-nya."""
        attachments = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename() or ""
                ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                attachments.append({
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "extension": ext,
                    "is_executable": ext in self.EXECUTABLE_EXTENSIONS,
                    "size": len(part.get_payload(decode=True) or b""),
                })
        return attachments


# ─── Feature Extractor ───────────────────────────────────────────────────────

class FeatureExtractor:
    """
    Konversi ParsedEmail -> EmailFeatures.

    Semua fitur yang diextract di sini juga jadi sumber X-Spam-Reason.
    Jangan hapus fitur apapun — semuanya ada alasannya.
    """

    def extract(self, parsed: ParsedEmail) -> EmailFeatures:
        """Pipeline utama ekstraksi fitur."""
        features = EmailFeatures()

        # ── Text content ──────────────────────────────────────────────────
        features.subject = parsed.subject
        features.body_text = parsed.body_text
        features.body_html = parsed.body_html
        features.combined_text = self._build_combined_text(parsed)

        # ── URL analysis ──────────────────────────────────────────────────
        features.num_urls = len(parsed.urls)
        url_domains = [
            tldextract.extract(url).top_domain_under_public_suffix
            for url in parsed.urls
        ]
        url_domains = [d for d in url_domains if d]
        features.num_unique_domains = len(set(url_domains))

        features.has_url_shortener = any(
            d in URL_SHORTENERS for d in url_domains
        )

        # Levenshtein check — lookalike domain
        lev_distances = [
            Levenshtein.distance(d, PROTECTED_DOMAIN)
            for d in url_domains
            if d != PROTECTED_DOMAIN
        ]
        if lev_distances:
            features.min_levenshtein_to_protected = min(lev_distances)
            # Jarak 1–3 = sangat mencurigakan
            features.has_lookalike_domain = features.min_levenshtein_to_protected <= 3
        else:
            features.min_levenshtein_to_protected = 999
            features.has_lookalike_domain = False

        # Entropy Shannon dari semua URL (diversifikasi link = red flag)
        features.entropy_of_links = self._url_entropy(parsed.urls)

        # ── Attachment analysis ───────────────────────────────────────────
        features.num_attachments = len(parsed.attachments)
        features.has_executable_attachment = any(
            a["is_executable"] for a in parsed.attachments
        )

        # ── HTML analysis ─────────────────────────────────────────────────
        len_html = len(parsed.body_html)
        len_text = len(parsed.body_text)
        features.html_text_ratio = (
            len_html / max(len_text, 1)
        )

        # Deteksi form dan JavaScript di HTML
        html_lower = parsed.body_html.lower()
        features.num_forms = html_lower.count("<form")
        features.javascript_present = (
            "<script" in html_lower or "javascript:" in html_lower
        )

        # Hitung jumlah gambar
        features.num_images = html_lower.count("<img")

        # ── Urgency scoring ───────────────────────────────────────────────
        combined_lower = features.combined_text.lower()
        hit_count = sum(
            1 for w in URGENCY_WORDS if w in combined_lower
        )
        # Normalisasi ke 0.0–1.0 (>10 kata urgensi = hampir pasti spam)
        features.urgency_score = min(hit_count / 10.0, 1.0)

        # ── Authentication headers ────────────────────────────────────────
        auth = parsed.authentication_results.lower()
        features.spf_pass = "spf=pass" in auth or "pass" in parsed.received_spf.lower()
        features.dkim_pass = "dkim=pass" in auth
        features.dmarc_pass = "dmarc=pass" in auth

        # ── Sender analysis ───────────────────────────────────────────────
        # Display name mismatch: "Bank BCA" tapi email dari domain mencurigakan
        display_lower = parsed.display_name.lower()
        known_brands = {
            "bca", "mandiri", "bni", "bri", "permata", "cimb",
            "paypal", "google", "microsoft", "amazon", "apple",
            "lodaya", "lti", "gojek", "grab", "shopee", "tokopedia"
        }
        if any(b in display_lower for b in known_brands):
            sender_ext = tldextract.extract(parsed.sender_domain)
            sender_brand = sender_ext.domain.lower()
            features.display_name_mismatch = not any(
                re.search(rf"(?:^|\.){re.escape(b)}(?:$|\.)", sender_brand)
                for b in known_brands
                if b in display_lower
            )

        # Fake RE/FWD (subject mulai dengan RE: atau FWD: tapi bukan reply asli)
        subject_lower = parsed.subject.lower()
        if subject_lower.startswith(("re:", "fwd:", "fw:")):
            # Heuristik: tidak ada References header = kemungkinan fake
            features.subject_has_re_fwd_fake = not bool(
                parsed.headers.get("References") or parsed.headers.get("In-Reply-To")
            )

        # Recipients
        features.num_recipients = len(parsed.recipient_list)
        features.is_bulk_sender = features.num_recipients > 5

        # ── Language detection ────────────────────────────────────────────
        try:
            features.detected_language = detect(
                features.combined_text[:500]
            ) if len(features.combined_text) > 20 else "unknown"
        except Exception:
            features.detected_language = "unknown"

        # ── Business context scoring ───────────────────────────────────────
        combined_lower = features.combined_text.lower()
        body_lower = parsed.body_text.lower()
        sender_domain = parsed.sender_domain.lower()

        # safe_business_score: legitimate business patterns
        # Also boost score when email has NO malicious indicators at all
        biz_indicators = [
            "invoice", "pembayaran", "payment", "transaction", "laporan",
            "report", "meeting", "contract", "kontrak", "proposal",
            "purchase order", "po ", "quotation", "quote", "rfq",
            "delivery order", "do ", "faktur", "receipt", "statement",
            "reminder", "update", "review", "schedule", "timesheet",
        ]
        biz_hits = sum(1 for w in biz_indicators if w in combined_lower)
        features.safe_business_score = min(biz_hits / 5.0, 1.0)
        # Floor: if email is from a trusted domain with no malicious features, boost
        no_malicious = (features.num_urls == 0 and features.has_executable_attachment is False
                        and features.num_attachments == 0 and features.display_name_mismatch is False)
        if no_malicious and features.sender_reputation >= 0.7 and features.safe_business_score < 0.4:
            # This looks like a clean personal/conversational email
            features.safe_business_score = max(features.safe_business_score, 0.4)

        # bec_score: Business Email Compromise indicators
        bec_indicators = [
            "wire transfer", "bank transfer", "urgent payment",
            "confidential", "ceo", "cfi", "director", "vp ",
            "i'm in a meeting", "i am in a meeting", "can't talk",
            "do not discuss", "keep this confidential", "gift card",
            "purchase gift card", "payment change", "bank details changed",
            "new banking details", "need you to process", "kindly do",
            "wire ${amount}", "settlement #{ref}", "legal settlement",
        ]
        bec_hits = sum(1 for w in bec_indicators if w in combined_lower)
        features.bec_score = min(bec_hits / 3.0, 1.0)

        # urgency_level: business-context urgency (meeting deadlines, etc)
        urgent_biz = [
            "eod", "today", "immediately", "asap", "deadline",
            "before end of day", "urgent", "time-sensitive", "rush",
            "priority", "critical", "by tomorrow", "before friday",
        ]
        urgency_biz_hits = sum(1 for w in urgent_biz if w in combined_lower)
        features.urgency_level = min(urgency_biz_hits / 4.0, 1.0)

        # sender_reputation: known corporate domains vs suspicious
        trusted_domains = {
            "lodaya.id", "bca.co.id", "mandiri.co.id", "bni.co.id",
            "bri.co.id", "gojek.com", "tokopedia.com", "shopee.co.id",
            "traveloka.com", "telkom.co.id", "gmail.com", "yahoo.com",
            "outlook.com", "office365.com",
        }
        suspicious_tlds = {".tk", ".ml", ".ga", ".cf", ".xyz", ".life", ".top", ".gq"}
        sender_ext = tldextract.extract(sender_domain)
        sender_reg = sender_ext.top_domain_under_public_suffix or sender_domain
        if sender_reg in trusted_domains:
            features.sender_reputation = 1.0
        elif any(sender_domain.endswith(t) for t in suspicious_tlds):
            features.sender_reputation = 0.0
        else:
            features.sender_reputation = 0.5

        # has_generic_greeting
        generic_greetings = [
            "dear sir", "dear madam", "dear customer", "dear user",
            "kepada yth", "kepada nasabah", "kepada pengguna",
            "kepada pelanggan", "kepada customer", "to whom it may concern",
        ]
        features.has_generic_greeting = any(g in body_lower[:200] for g in generic_greetings)

        # request_for_transfer
        transfer_phrases = [
            "wire transfer", "transfer dana", "transfer uang",
            "kirim uang", "process payment", "process a payment",
            "pay this invoice", "pay immediately", "send payment",
            "please pay", "payment required", "purchase gift card",
            "gift cards", "payment change", "new account",
        ]
        features.request_for_transfer = any(p in combined_lower for p in transfer_phrases)

        # ceo_impersonation: sender display name has C-level title
        c_level_titles = [
            "ceo", "cfo", "coo", "cto", "director", "president",
            "vp ", "vice president", "managing director",
        ]
        display = parsed.display_name.lower()
        features.ceo_impersonation = any(t in display for t in c_level_titles)

        # business_context_weight: composite
        biz_features = [
            features.safe_business_score,
            features.sender_reputation,
            1.0 - features.bec_score,
            1.0 - features.request_for_transfer,
            1.0 - features.ceo_impersonation,
        ]
        features.business_context_weight = float(np.mean(biz_features))

        return features

    def _build_combined_text(self, parsed: ParsedEmail) -> str:
        """
        Gabungkan semua teks relevan untuk TF-IDF.
        Subject diberi bobot lebih dengan mengulang 3x — subject phishing
        sering paling telltale.
        """
        # Bersihkan HTML minimal
        clean_html = re.sub(r"<[^>]+>", " ", parsed.body_html)
        subject_weighted = (parsed.subject + " ") * 3
        return f"{subject_weighted}{parsed.body_text} {clean_html}".strip()

    def _url_entropy(self, urls: list[str]) -> float:
        """
        Shannon entropy dari URL path strings.
        Entropy tinggi = banyak URL random-looking = red flag.
        """
        if not urls:
            return 0.0
        all_chars = "".join(urlparse(u).path for u in urls)
        if not all_chars:
            return 0.0
        freq = {}
        for c in all_chars:
            freq[c] = freq.get(c, 0) + 1
        total = len(all_chars)
        entropy = -sum(
            (cnt / total) * np.log2(cnt / total)
            for cnt in freq.values()
        )
        return float(entropy)
