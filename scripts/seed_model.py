"""Train and save dummy model for testing."""

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES

MODEL_DIR = Path("classifier/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

SPAM_EXAMPLES = [
    "SEGERA! Akun Anda Akan Diblokir! Klik http://bit.ly/verifikasi-sekarang untuk verifikasi.",
    "CONGRATULATIONS! You won $10,000,000! Click here to claim now: http://bit.ly/winner",
    "Akun BCA Anda telah diakses dari perangkat tidak dikenal. Verifikasi: http://bca-secure-login.xyz",
    "URGENT: Your PayPal account has been suspended. Verify now: http://paypal-verify.tk",
    "FREE iPhone 15! Claim yours now! Limited offer. http://free-iphone.life",
    "Dear Customer, your account will be closed if not verified within 24 hours. http://bank-verification.ml",
    "You have an unclaimed tax refund of $2,500. Click to receive: http://bit.ly/tax-refund",
    "Hi there, I'm a prince from Nigeria who needs your help transferring $25,000,000...",
    "Get your dream body now! 100% guaranteed weight loss supplement. http://bit.ly/dream-body",
    "Work from home and earn $5000/week! No experience needed. http://work-home.xyz",
]

HAM_EXAMPLES = [
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
]

parser = EmailParser()
extractor = FeatureExtractor()

all_texts = []
all_features_list = []
y = []

for text in SPAM_EXAMPLES:
    raw = f"Subject: {text}\n\n{text}"
    parsed = parser.parse(raw)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(1)

for text in HAM_EXAMPLES:
    raw = f"Subject: {text}\n\n{text}"
    parsed = parser.parse(raw)
    feats = extractor.extract(parsed)
    all_texts.append(feats.combined_text)
    all_features_list.append({f: getattr(feats, f, 0) for f in STRUCTURED_FEATURES})
    y.append(0)

y = np.array(y)

tfidf = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
X_tfidf = tfidf.fit_transform(all_texts)

feat_df = pd.DataFrame(all_features_list)
scaler = StandardScaler()
feat_scaled = scaler.fit_transform(feat_df)

from scipy.sparse import hstack, csr_matrix
X_combined = hstack([X_tfidf, csr_matrix(feat_scaled)])

model = xgb.XGBClassifier(
    n_estimators=20,
    max_depth=3,
    learning_rate=0.1,
    use_label_encoder=False,
    eval_metric="logloss",
    random_state=42,
)
model.fit(X_combined, y)

joblib.dump(model, MODEL_DIR / "xgb_model_latest.joblib")
joblib.dump(tfidf, MODEL_DIR / "tfidf_latest.joblib")
joblib.dump(scaler, MODEL_DIR / "scaler_latest.joblib")

print("[OK] Model files created in", MODEL_DIR)
print(f"   - xgb_model_latest.joblib ({Path(MODEL_DIR / 'xgb_model_latest.joblib').stat().st_size / 1024:.1f} KB)")
print(f"   - tfidf_latest.joblib ({Path(MODEL_DIR / 'tfidf_latest.joblib').stat().st_size / 1024:.1f} KB)")
print(f"   - scaler_latest.joblib ({Path(MODEL_DIR / 'scaler_latest.joblib').stat().st_size / 1024:.1f} KB)")

spam_pred = model.predict_proba(X_combined[:len(SPAM_EXAMPLES)])[:, 1]
ham_pred = model.predict_proba(X_combined[len(SPAM_EXAMPLES):])[:, 1]
print(f"   Spam avg prob: {spam_pred.mean():.3f}, Ham avg prob: {ham_pred.mean():.3f}")

