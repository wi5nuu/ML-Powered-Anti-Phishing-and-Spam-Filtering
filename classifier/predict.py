"""
FastAPI inference service untuk LTI Anti-Phishing Classifier.

Endpoint utama: POST /predict
Menerima ParsedEmail JSON, mengembalikan skor spam + SHAP explanation.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
import shap
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from classifier.features import (
    EmailParser, FeatureExtractor, EmailFeatures, STRUCTURED_FEATURES
)
from classifier.train import build_feature_matrix

logger = logging.getLogger(__name__)

MODEL_DIR = Path("classifier/models")


# ─── Model State (singleton, load sekali waktu startup) ───────────────────────

class ModelState:
    model = None
    tfidf = None
    scaler = None
    explainer = None

state = ModelState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model saat startup, cleanup saat shutdown."""
    logger.info("Loading model artifacts...")
    try:
        state.model   = joblib.load(MODEL_DIR / "xgb_model_latest.joblib")
        state.tfidf   = joblib.load(MODEL_DIR / "tfidf_latest.joblib")
        state.scaler  = joblib.load(MODEL_DIR / "scaler_latest.joblib")
        try:
            state.explainer = shap.TreeExplainer(state.model, check_additivity=False)
        except Exception as e:
            logger.warning("SHAP explainer init failed: %s", e)
            state.explainer = None
        logger.info("✅ Model berhasil diload.")
    except FileNotFoundError as e:
        logger.critical("Model tidak ditemukan: %s. Jalankan training dulu.", e)
        raise
    yield
    logger.info("Classifier service shutdown.")


app = FastAPI(
    title="LTI Anti-Phishing Classifier",
    version="1.0.0",
    lifespan=lifespan,
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)


# ─── Request/Response Schema ──────────────────────────────────────────────────

class EmailPredictRequest(BaseModel):
    raw_email: str
    email_id: str = ""


class FeatureContribution(BaseModel):
    feature: str
    shap_value: float
    direction: str  # "spam" atau "ham"


class PredictResponse(BaseModel):
    email_id: str
    spam_probability: float
    is_spam: bool
    label: str          # "CLEAN", "WARN", "QUARANTINE"
    top_reasons: list[FeatureContribution]
    xai_summary: str    # String ringkas untuk X-Spam-Reason header


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictResponse)
async def predict(req: EmailPredictRequest):
    """
    Classifikasi satu email.

    Input: raw email string
    Output: spam probability + XAI explanation
    """
    if state.model is None:
        raise HTTPException(503, "Model belum diload.")

    # Parse email
    parser = EmailParser()
    extractor = FeatureExtractor()
    try:
        parsed = parser.parse(req.raw_email)
        features = extractor.extract(parsed)
    except Exception as e:
        logger.error("Gagal parse email %s: %s", req.email_id, e)
        raise HTTPException(400, f"Email parsing error: {e}")

    # Build feature row (DataFrame dengan 1 baris)
    import pandas as pd
    row = {
        "combined_text": features.combined_text,
        **{f: getattr(features, f, 0) for f in STRUCTURED_FEATURES},
    }
    df_row = pd.DataFrame([row])

    # Feature matrix
    try:
        X = build_feature_matrix(df_row, state.tfidf, state.scaler, fit=False)
    except Exception as e:
        raise HTTPException(500, f"Feature extraction error: {e}")

    # Prediksi
    prob = float(state.model.predict_proba(X)[0, 1])

    # Routing label
    clean_thresh = float(app.state.threshold_clean if hasattr(app.state, "threshold_clean") else 0.30)
    warn_thresh  = float(app.state.threshold_warn  if hasattr(app.state, "threshold_warn")  else 0.70)

    if prob < clean_thresh:
        label = "CLEAN"
    elif prob < warn_thresh:
        label = "WARN"
    else:
        label = "QUARANTINE"

    if state.explainer is not None:
        try:
            X_dense = X.toarray()
            shap_vals = state.explainer.shap_values(X_dense, check_additivity=False)[0]
        except Exception as e:
            logger.warning("SHAP failed: %s", e)
            shap_vals = None
    else:
        shap_vals = None

    tfidf_names = state.tfidf.get_feature_names_out().tolist()
    all_names = tfidf_names + STRUCTURED_FEATURES

    # Ambil top 5 kontributor spam (shap_val positif terbesar)
    if shap_vals is not None:
        contrib_pairs = list(zip(all_names, shap_vals))
        top_spam = sorted(
            [(n, v) for n, v in contrib_pairs if v > 0],
            key=lambda x: abs(x[1]), reverse=True
        )[:5]
        top_ham = sorted(
            [(n, v) for n, v in contrib_pairs if v < 0],
            key=lambda x: abs(x[1]), reverse=True
        )[:3]
    else:
        top_spam = []
        top_ham = []

    reasons: list[FeatureContribution] = []
    for name, val in top_spam:
        reasons.append(FeatureContribution(
            feature=name,
            shap_value=round(float(val), 4),
            direction="spam",
        ))
    for name, val in top_ham:
        reasons.append(FeatureContribution(
            feature=name,
            shap_value=round(float(val), 4),
            direction="ham",
        ))

    # Build X-Spam-Reason string yang informatif
    xai_parts = []
    if prob > clean_thresh:
        if features.urgency_score > 0.3:
            xai_parts.append(f"Urgency-Score:{features.urgency_score:.2f}")
        if features.has_lookalike_domain:
            xai_parts.append(
                f"Lookalike-Domain:Distance={features.min_levenshtein_to_protected}"
            )
        if not features.spf_pass:
            xai_parts.append("SPF:FAIL")
        if not features.dkim_pass:
            xai_parts.append("DKIM:FAIL")
        if features.has_executable_attachment:
            xai_parts.append("Executable-Attachment:YES")
        if features.has_url_shortener:
            xai_parts.append("URL-Shortener:DETECTED")
        if features.display_name_mismatch:
            xai_parts.append("DisplayName-Mismatch:YES")
        if features.num_forms > 0:
            xai_parts.append(f"HTML-Forms:{features.num_forms}")
        if top_spam:
            top_term = top_spam[0][0]
            xai_parts.append(f"Top-SHAP:{top_term}")

    xai_summary = (
        f"SpamProb={prob:.2f}; " + "; ".join(xai_parts)
        if xai_parts else f"SpamProb={prob:.2f}; No major red flags"
    )

    return PredictResponse(
        email_id=req.email_id or parsed.raw_id,
        spam_probability=round(prob, 4),
        is_spam=label in ("QUARANTINE", "WARN"),
        label=label,
        top_reasons=reasons,
        xai_summary=xai_summary,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": state.model is not None,
    }


@app.get("/model-info")
async def model_info():
    """Informasi model yang sedang aktif."""
    if state.model is None:
        raise HTTPException(503, "Model belum diload.")
    return {
        "n_estimators": state.model.n_estimators,
        "tfidf_vocab_size": len(state.tfidf.vocabulary_),
        "structured_features": STRUCTURED_FEATURES,
    }
