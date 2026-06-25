"""Profile individual stages of prediction pipeline."""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.features import EmailParser, FeatureExtractor, STRUCTURED_FEATURES
import joblib
import joblib
import numpy as np
import pandas as pd
from classifier.train import build_feature_matrix

MODEL_DIR = Path("classifier/models")

print("Loading model artifacts...")
t0 = time.perf_counter()
model = joblib.load(MODEL_DIR / "xgb_model_latest.joblib")
tfidf = joblib.load(MODEL_DIR / "tfidf_latest.joblib")
scaler = joblib.load(MODEL_DIR / "scaler_latest.joblib")
print(f"  Model load: {(time.perf_counter()-t0)*1000:.0f}ms")

import shap
t0 = time.perf_counter()
explainer = shap.TreeExplainer(model)
print(f"  SHAP explainer: {(time.perf_counter()-t0)*1000:.0f}ms")

# Test email
raw = Path("data/dataset/chris/chris_0001_8ca553d955a0bf88.eml").read_text(encoding="utf-8", errors="replace")
raw_brian = Path("data/dataset/brian/brian_0001_316e50a87d13354c.eml").read_text(encoding="utf-8", errors="replace")

for label, email_raw in [("CHRIS (ham)", raw), ("BRIAN (spam)", raw_brian)]:
    print(f"\n--- {label} ---")
    
    parser = EmailParser()
    extractor = FeatureExtractor()

    t0 = time.perf_counter()
    parsed = parser.parse(email_raw)
    print(f"  Parse: {(time.perf_counter()-t0)*1000:.0f}ms")
    
    t0 = time.perf_counter()
    features = extractor.extract(parsed)
    print(f"  Extract features: {(time.perf_counter()-t0)*1000:.0f}ms")
    
    row = {
        "combined_text": features.combined_text,
        **{f: getattr(features, f, 0) for f in STRUCTURED_FEATURES},
    }
    df_row = pd.DataFrame([row])
    
    t0 = time.perf_counter()
    X = build_feature_matrix(df_row, tfidf, scaler, fit=False)
    print(f"  Build feature matrix: {(time.perf_counter()-t0)*1000:.0f}ms")
    
    t0 = time.perf_counter()
    prob = float(model.predict_proba(X)[0, 1])
    print(f"  XGBoost predict: {(time.perf_counter()-t0)*1000:.0f}ms")
    
    t0 = time.perf_counter()
    X_dense = X.toarray()
    shap_vals = explainer.shap_values(X_dense)[0]
    print(f"  SHAP values: {(time.perf_counter()-t0)*1000:.0f}ms")
    
    print(f"  Spam prob: {prob:.4f}")
    
    tfidf_names = tfidf.get_feature_names_out().tolist()
    all_names = tfidf_names + STRUCTURED_FEATURES
    contrib_pairs = list(zip(all_names, shap_vals))
    top_spam = sorted([(n, v) for n, v in contrib_pairs if v > 0], key=lambda x: abs(x[1]), reverse=True)[:5]
    top_ham  = sorted([(n, v) for n, v in contrib_pairs if v < 0], key=lambda x: abs(x[1]), reverse=True)[:3]
    print(f"  Top spam features: {[(n, f'{v:.3f}') for n,v in top_spam]}")
