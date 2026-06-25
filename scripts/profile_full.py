"""Full pipeline timing including SHAP and model loading."""
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

t_all = time.perf_counter()
t0 = time.perf_counter()

import joblib
import numpy as np
import pandas as pd
import shap
from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES
from classifier.train import build_feature_matrix

print(f"Imports: {(time.perf_counter()-t0)*1000:.0f}ms")

MODEL_DIR = Path("classifier/models")
model = joblib.load(MODEL_DIR / "xgb_model_latest.joblib")
tfidf = joblib.load(MODEL_DIR / "tfidf_latest.joblib")
scaler = joblib.load(MODEL_DIR / "scaler_latest.joblib")
print(f"Model load: {(time.perf_counter()-t0)*1000:.0f}ms")

explainer = shap.TreeExplainer(model)
print(f"SHAP explainer: {(time.perf_counter()-t0)*1000:.0f}ms")

# Pre-init lazy modules
import tldextract as _t
_t.TLDExtract()("http://test.com")
from langdetect import detect as _d
_d("test")
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
StemmerFactory().create_stemmer().stem("test")
print(f"Lazy init: {(time.perf_counter()-t0)*1000:.0f}ms")

# Cache feature names (simulate what predict.py now does)
tfidf_names = tfidf.get_feature_names_out().tolist()
all_names = tfidf_names + STRUCTURED_FEATURES
print(f"Feature names cached ({len(all_names)} total)")

# Full prediction pipeline
raw = Path("data/dataset/chris/chris_0001_8ca553d955a0bf88.eml").read_text(encoding="utf-8", errors="replace")
parser = EmailParser()
extractor = FeatureExtractor()
parsed = parser.parse(raw)
features = extractor.extract(parsed)
row = {"combined_text": features.combined_text, **{f: getattr(features, f, 0) for f in STRUCTURED_FEATURES}}
df_row = pd.DataFrame([row])
X = build_feature_matrix(df_row, tfidf, scaler, fit=False)
prob = float(model.predict_proba(X)[0, 1])
X_dense = X.toarray()
shap_vals = explainer.shap_values(X_dense)[0]
contrib_pairs = list(zip(all_names, shap_vals))
top_spam = sorted([(n, v) for n, v in contrib_pairs if v > 0], key=lambda x: abs(x[1]), reverse=True)[:5]
print(f"Full pipeline: {(time.perf_counter()-t0)*1000:.0f}ms")
print(f"Spam prob: {prob:.4f}, Label: {'SPAM' if prob > 0.5 else 'CLEAN'}")
print(f"Total startup to result: {(time.perf_counter()-t_all)*1000:.0f}ms")

# Second prediction (should be fast)
t1 = time.perf_counter()
parsed = parser.parse(raw)
features = extractor.extract(parsed)
row = {"combined_text": features.combined_text, **{f: getattr(features, f, 0) for f in STRUCTURED_FEATURES}}
df_row = pd.DataFrame([row])
X = build_feature_matrix(df_row, tfidf, scaler, fit=False)
prob = float(model.predict_proba(X)[0, 1])
X_dense = X.toarray()
shap_vals = explainer.shap_values(X_dense)[0]
print(f"Second prediction: {(time.perf_counter()-t1)*1000:.0f}ms")
