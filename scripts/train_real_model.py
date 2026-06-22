"""Train model with SpamAssassin public corpus + synthetic data."""

"""
Build dataset from SA corpus + synthetic data, then train via proper pipeline.
"""
import hashlib, tarfile, io, logging
import numpy as np
import pandas as pd
from pathlib import Path
import httpx
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES
from classifier.train import train

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

parser = EmailParser()
extractor = FeatureExtractor()

all_texts = []
all_features_list = []
y = []

# 1. SpamAssassin public corpus (easy_ham + spam)
CORPUS_URLS = {
    "ham": "https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2",
    "spam": "https://spamassassin.apache.org/old/publiccorpus/20030228_spam_2.tar.bz2",
}

def process_text(text, label, is_raw=False):
    if not is_raw:
        raw = f"Subject: test\n\n{text}"
    else:
        raw = text
    parsed = parser.parse(raw)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(label)

# Try to download and extract SA corpus
import asyncio

async def download_and_extract():
    for label_name, url in CORPUS_URLS.items():
        label = 1 if label_name == "spam" else 0
        try:
            print(f"Downloading {label_name} corpus...")
            async with httpx.AsyncClient() as client:
                r = await client.get(url, timeout=60, follow_redirects=True)
                print(f"  Got {len(r.content)} bytes")
            with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:bz2") as tar:
                members = [m for m in tar.getmembers() if m.isfile()]
                count = 0
                for m in members[:200]:  # 200 emails per category
                    f = tar.extractfile(m)
                    if f:
                        text = f.read().decode("utf-8", errors="replace")
                        process_text(text[:2000], label)
                        count += 1
                print(f"  Extracted {count} emails")
        except Exception as e:
            print(f"  Failed: {e}")

asyncio.run(download_and_extract())

# 2. Synthetic data (spam emails with urgency, links, etc.)
SPAM_TEXTS = [
    "URGENT! Your account has been compromised. Click http://bit.ly/verify-now to secure it.",
    "CONGRATULATIONS! You won $1,000,000! Claim at http://tinyurl.com/winner",
    "Dear customer, your Netflix account is suspended. Update payment: http://netflix-verify.tk",
    "FREE iPhone 15! Get yours now! Limited time offer. http://free-phone.life",
    "Work from home and earn $5000/week! No experience needed. http://work-home.xyz",
    "Your PayPal account limited. Confirm now: http://paypal-security.ml",
    "SEGERA! Akun Anda akan ditutup jika tidak verifikasi dalam 24 jam. http://bca-secure.xyz",
    "You have unclaimed tax refund of $2,500. http://bit.ly/tax-refund",
    "Hi, I'm a prince from Nigeria who needs your help transferring $25M...",
    "Weight loss 100% guaranteed! Order now: http://bit.ly/lose-weight",
    "Your Apple ID was used to sign in on a new device. Verify: http://apple-id.tk",
    "Get your degree online in just 2 weeks! http://diploma-online.life",
    "You are selected for a free vacation to Bali! http://bit.ly/vacation-prize",
    "INTERNATIONAL PROTEIN - Enhance your performance! http://bit.ly/miracle-pill",
    "SMS: Your package is waiting. Track here: http://bit.ly/tracking-package",
    "ACCOUNT ALERT: Suspicious login detected. http://bit.ly/secure-login",
    "You have 1 unread message from Bank Mandiri. http://mandiri-secure.xyz",
    "LOWEST PRICES guaranteed on all medications! http://cheap-rx.life",
    "URGENT: Your domain will expire. Renew now! http://bit.ly/renew-domain",
    "Hot singles in your area are waiting! http://dating-site.tk",
]
# Additional phishing emails with HTML forms and lookalike domains
EXTRA_SPAM_RAW = [
    'From: "Bank BCA" <noreply@bca-secure-login.xyz>\r\nTo: korban@email.com\r\nSubject: SEGERA! Akun Anda Akan Diblokir\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://bca-secure-login.xyz/login"><h2>SEGERA! Akun Anda Diblokir</h2><p>Klik <a href="http://bit.ly/verifikasi-akun">di sini</a> untuk verifikasi.</p><p>Verifikasi sekarang atau akun ditangguhkan!</p></form></body></html>',
    'From: "PayPal Security" <alert@paypal-verification.tk>\r\nTo: user@example.com\r\nSubject: Your PayPal Account Has Been Limited\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://paypal-verification.tk/signin"><h2>Your PayPal Account Has Been Limited</h2><p>Confirm your identity: <a href="http://tinyurl.com/paypal-confirm">Click Here</a></p></form></body></html>',
    "PENTING! Akun email Anda akan dihapus! Verifikasi di http://email-verif.ml dalam 24 jam.",
    'From: "Wells Fargo" <alert@wells-fargo-secure.life>\r\nTo: customer@example.com\r\nSubject: Unusual Sign-In Activity\r\n\r\nYour Wells Fargo account was accessed from a new device. Verify: http://wells-fargo-secure.life',
    'From: "Bank Mandiri" <noreply@mandiri-verifikasi.xyz>\r\nTo: nasabah@email.com\r\nSubject: Kartu ATM Anda Diblokir\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://mandiri-verifikasi.xyz/auth"><h2>Kartu ATM Anda Diblokir</h2><p>Hubungi kami: http://bit.ly/mandiri-bantuan</p><p>Jangan tunda! Segera verifikasi!</p></form></body></html>',
    'From: "Amazon Orders" <orders@amzn-order-update.tk>\r\nTo: customer@example.com\r\nSubject: Your Order Has Been Delayed\r\n\r\nDear Amazon customer, your order has been delayed. Check details: http://amzn-order-update.tk',
    'From: "Google Security" <alert@google-account-recovery.life>\r\nTo: user@gmail.com\r\nSubject: Security Alert\r\n\r\nALERT: Someone tried to sign in to your Google Account from a new device. Recover: http://google-account-recovery.life',
    "SELAMAT! Anda memenangkan undian Bank Indonesia senilai Rp 100.000.000! Klaim: http://bit.ly/klaim-hadiah",
    'From: "Dropbox" <noreply@dropbox-reactivate.xyz>\r\nTo: user@example.com\r\nSubject: Your Dropbox Account Has Been Deactivated\r\n\r\nYour Dropbox account has been deactivated due to inactivity. Reactivate: http://dropbox-reactivate.xyz',
    'From: "Microsoft Defender" <alert@microsoft-security.life>\r\nTo: user@outlook.com\r\nSubject: VIRUS DETECTED!\r\nContent-Type: text/html\r\n\r\n<html><body><div style="background:red;color:white;padding:20px;"><h1>VIRUS DETECTED!</h1><p>Your computer is infected! Scan now: <a href="http://bit.ly/antivirus-scan">Free Scan</a></p></div></body></html>',
]

for text in SPAM_TEXTS:
    process_text(text, 1)
for text in EXTRA_SPAM_RAW:
    process_text(text, 1, is_raw=True)

HAM_TEXTS = [
    "Halo tim, berikut update jadwal maintenance server untuk minggu ini.",
    "Meeting reminder: Sprint planning besok jam 10.00 di ruang rapat utama.",
    "Mohon maaf atas ketidaknyamanannya. Sistem akan kembali normal dalam 30 menit.",
    "Invoice terlampir untuk pembelian bulan Maret. Terima kasih.",
    "Notulensi rapat sudah diupload di Google Drive. Silakan dicek.",
    "Selamat pagi, berikut laporan mingguan progress project kita.",
    "Reminder: Deadline pengumpulan laporan adalah hari Jumat pukul 17.00.",
    "Terima kasih atas konfirmasi kehadirannya. Acara akan dimulai pukul 13.00.",
    "Mohon review pull request #142 sebelum jam 3 sore. Terima kasih.",
    "Update: Jadwal training telah berubah menjadi hari Selasa, 14 Mei 2025.",
    "Laporan keuangan Q1 2025 sudah siap. Silakan download dari portal.",
    "Hari ini ada sesi sharing knowledge tentang keamanan siber jam 15.00.",
    "Dokumen kontrak vendor sudah ditandatangani. Copy terlampir.",
    "Test environment untuk fitur baru sudah ready. Silakan dicek.",
    "Agenda rapat: - Review sprint - Planning sprint berikutnya - Diskusi teknis",
    "Mohon mengisi timesheet sebelum akhir bulan. Terima kasih.",
    "Selamat! Kamu mendapatkan reward employee of the month! (internal email)",
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

for text in HAM_TEXTS:
    process_text(text, 0)
for text in EXTRA_HAM:
    process_text(text, 0)

print(f"\nTotal samples: {len(all_texts)} spam={sum(y)} ham={len(y)-sum(y)}")

# Save as CSV for training pipeline
df_out = pd.DataFrame({"combined_text": all_texts, "label": y})
for f in STRUCTURED_FEATURES:
    df_out[f] = [d[f] for d in all_features_list]
csv_path = PROCESSED_DIR / "train.csv"
df_out.to_csv(csv_path, index=False)
print(f"Dataset saved to {csv_path}")

# Train via proper pipeline (RandomizedSearchCV, 50k TF-IDF, SHAP, metadata)
train(str(csv_path))
