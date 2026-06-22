"""
Build dataset from local SA corpus + Enron + synthetic data, then train via proper pipeline.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import logging
from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES
from classifier.train import train

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

parser = EmailParser()
extractor = FeatureExtractor()
all_texts = []
all_features_list = []
y = []


def process_file(filepath: Path, label: int):
    raw = filepath.read_text(encoding="utf-8", errors="replace")[:3000]
    parsed = parser.parse(raw)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(label)


def load_corpus(corpus_dir: Path, label: int, max_count: int = 500):
    files = [f for f in corpus_dir.rglob("*") if f.is_file() and f.stat().st_size > 50]
    print(f"  {corpus_dir.name}: {len(files)} files, taking {min(max_count, len(files))}")
    for f in files[:max_count]:
        process_file(f, label)


# 1. SpamAssassin corpus (local)
print("=== Loading SpamAssassin corpus ===")
sa = RAW_DIR / "spamassassin_corpus"
load_corpus(sa / "spam_2", 1, 500)
load_corpus(sa / "easy_ham", 0, 500)

# 2. Enron dataset (local)
print("=== Loading Enron dataset ===")
enron = RAW_DIR / "enron"
load_corpus(enron / "enron1" / "spam", 1, 300)
load_corpus(enron / "enron1" / "ham", 0, 300)
load_corpus(enron / "enron2" / "spam", 1, 300)
load_corpus(enron / "enron2" / "ham", 0, 300)

# 3. Synthetic phishing/ham
print("=== Loading synthetic data ===")
SPAM_TEXTS = [
    "URGENT! Your account has been compromised. Click http://bit.ly/verify-now to secure it.",
    "CONGRATULATIONS! You won $1,000,000! Claim at http://tinyurl.com/winner",
    "Dear customer, your Netflix account is suspended. Update payment: http://netflix-verify.tk",
    "FREE iPhone 15! Get yours now! Limited time offer. http://free-phone.life",
    "Work from home and earn $5000/week! No experience needed. http://work-home.xyz",
    "Your PayPal account limited. Confirm now: http://paypal-security.ml",
    "SEGERA! Akun Anda akan ditutup jika tidak verifikasi dalam 24 jam. http://bca-secure.xyz",
    "You have unclaimed tax refund of $2,500. http://bit.ly/tax-refund",
    "Your Apple ID was used to sign in on a new device. Verify: http://apple-id.tk",
    "Get your degree online in just 2 weeks! http://diploma-online.life",
    "INTERNATIONAL PROTEIN - Enhance your performance! http://bit.ly/miracle-pill",
    "ACCOUNT ALERT: Suspicious login detected. http://bit.ly/secure-login",
    "You have 1 unread message from Bank Mandiri. http://mandiri-secure.xyz",
    "URGENT: Your domain will expire. Renew now! http://bit.ly/renew-domain",
    "Hot singles in your area are waiting! http://dating-site.tk",
]
EXTRA_SPAM_RAW = [
    'From: "Bank BCA" <noreply@bca-secure-login.xyz>\r\nTo: korban@email.com\r\nSubject: SEGERA! Akun Anda Akan Diblokir\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://bca-secure-login.xyz/login"><h2>SEGERA! Akun Anda Diblokir</h2><p>Klik <a href="http://bit.ly/verifikasi-akun">di sini</a> untuk verifikasi.</p><p>Verifikasi sekarang atau akun ditangguhkan!</p></form></body></html>',
    'From: "PayPal Security" <alert@paypal-verification.tk>\r\nTo: user@example.com\r\nSubject: Your PayPal Account Has Been Limited\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://paypal-verification.tk/signin"><h2>Your PayPal Account Has Been Limited</h2><p>Confirm your identity: <a href="http://tinyurl.com/paypal-confirm">Click Here</a></p></form></body></html>',
    'From: "Wells Fargo" <alert@wells-fargo-secure.life>\r\nTo: customer@example.com\r\nSubject: Unusual Sign-In Activity\r\n\r\nYour Wells Fargo account was accessed from a new device. Verify: http://wells-fargo-secure.life',
    'From: "Bank Mandiri" <noreply@mandiri-verifikasi.xyz>\r\nTo: nasabah@email.com\r\nSubject: Kartu ATM Anda Diblokir\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://mandiri-verifikasi.xyz/auth"><h2>Kartu ATM Anda Diblokir</h2><p>Hubungi kami: http://bit.ly/mandiri-bantuan</p><p>Jangan tunda! Segera verifikasi!</p></form></body></html>',
    'From: "Google Security" <alert@google-account-recovery.life>\r\nTo: user@gmail.com\r\nSubject: Security Alert\r\n\r\nALERT: Someone tried to sign in to your Google Account from a new device. Recover: http://google-account-recovery.life',
    "SELAMAT! Anda memenangkan undian Bank Indonesia senilai Rp 100.000.000! Klaim: http://bit.ly/klaim-hadiah",
    'From: "Microsoft Defender" <alert@microsoft-security.life>\r\nTo: user@outlook.com\r\nSubject: VIRUS DETECTED!\r\nContent-Type: text/html\r\n\r\n<html><body><div style="background:red;color:white;padding:20px;"><h1>VIRUS DETECTED!</h1><p>Your computer is infected! Scan now: <a href="http://bit.ly/antivirus-scan">Free Scan</a></p></div></body></html>',
]
HAM_TEXTS = [
    "Halo tim, berikut update jadwal maintenance server untuk minggu ini.",
    "Meeting reminder: Sprint planning besok jam 10.00 di ruang rapat utama.",
    "Invoice terlampir untuk pembelian bulan Maret. Terima kasih.",
    "Notulensi rapat sudah diupload di Google Drive. Silakan dicek.",
    "Reminder: Deadline pengumpulan laporan adalah hari Jumat pukul 17.00.",
    "Terima kasih atas konfirmasi kehadirannya. Acara akan dimulai pukul 13.00.",
    "Mohon review pull request #142 sebelum jam 3 sore. Terima kasih.",
    "Laporan keuangan Q1 2025 sudah siap. Silakan download dari portal.",
    "Hari ini ada sesi sharing knowledge tentang keamanan siber jam 15.00.",
    "Dokumen kontrak vendor sudah ditandatangani. Copy terlampir.",
    "Test environment untuk fitur baru sudah ready. Silakan dicek.",
    "Agenda rapat: - Review sprint - Planning sprint berikutnya - Diskusi teknis",
    "Mohon mengisi timesheet sebelum akhir bulan. Terima kasih.",
    "Proyek migrasi database dijadwalkan ulang menjadi pekan depan.",
    "Rekrutmen posisi Senior Developer dibuka sampai 30 Juni 2026.",
    "Pengingat: Password WIFI kantor diupdate setiap bulan.",
]
EXTRA_HAM = [
    "<html><body><p>Dear All,</p><p>Berikut laporan penjualan bulan ini. Silakan review.</p><p>Thanks,<br>Tim Finance</p></body></html>",
    "<html><body><p>Monthly newsletter - Edition #42</p><ul><li>New features launched</li><li>Team updates</li><li>Upcoming events</li></ul></body></html>",
    "The quarterly report is now available in the shared drive. Please review by Friday.",
    "Your order #12345 has been shipped. Estimated delivery: 3-5 business days. Track at http://shop.example.com/track",
    "Meeting notes from today's standup: 1) API review complete 2) Deploy scheduled 3) Documentation pending.",
]

for text in SPAM_TEXTS:
    parser = EmailParser()
    feats = extractor.extract(parser.parse(text))
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(1)
for text in EXTRA_SPAM_RAW:
    process_file.__wrapped__ = None
    raw = text
    parsed = parser.parse(raw)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(1)
for text in HAM_TEXTS:
    parsed = parser.parse(text)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(0)
for text in EXTRA_HAM:
    parsed = parser.parse(text)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(0)

spam_count = sum(y)
ham_count = len(y) - spam_count
print(f"\nTotal: {len(y)} samples (spam={spam_count}, ham={ham_count})")

# Save CSV
df = pd.DataFrame({"combined_text": all_texts, "label": y})
for f in STRUCTURED_FEATURES:
    df[f] = [d[f] for d in all_features_list]
csv_path = PROCESSED_DIR / "train.csv"
df.to_csv(csv_path, index=False)
print(f"Saved to {csv_path} ({csv_path.stat().st_size / 1024:.1f} KB)")

# Train
train(str(csv_path))
