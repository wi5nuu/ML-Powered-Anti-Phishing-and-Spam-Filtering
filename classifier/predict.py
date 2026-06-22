"""
FastAPI inference service untuk LTI Anti-Phishing Classifier.

Endpoint:
  POST /predict            — Supervised XGBoost (TF-IDF + structured) + SHAP
  POST /predict-unsupervised — Unsupervised anomaly detection (IForest + OCSVM)
  POST /predict-dual       — Kedua layer sekaligus
  GET  /health
  GET  /model-info
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
from classifier.unsupervised import AnomalyDetector, AnomalyResult

logger = logging.getLogger(__name__)

MODEL_DIR = Path("classifier/models")


# ─── Model State (singleton, load sekali waktu startup) ───────────────────────

class ModelState:
    model = None        # XGBoost
    tfidf = None
    scaler = None
    explainer = None
    anomaly = None      # Unsupervised detector

state = ModelState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model saat startup, cleanup saat shutdown."""
    logger.info("Loading model artifacts...")

    # Supervised (XGBoost)
    try:
        state.model   = joblib.load(MODEL_DIR / "xgb_model_latest.joblib")
        state.tfidf   = joblib.load(MODEL_DIR / "tfidf_latest.joblib")
        state.scaler  = joblib.load(MODEL_DIR / "scaler_latest.joblib")
        try:
            state.explainer = shap.TreeExplainer(state.model)
        except Exception as e:
            logger.warning("SHAP explainer init failed: %s", e)
            state.explainer = None
        logger.info("Supervised (XGBoost) model loaded.")
    except FileNotFoundError as e:
        logger.critical("Supervised model tidak ditemukan: %s", e)
        raise

    # Unsupervised (Isolation Forest + One-Class SVM)
    state.anomaly = AnomalyDetector()
    state.anomaly.load()
    if state.anomaly.is_fitted:
        logger.info("Unsupervised anomaly detectors loaded.")
    else:
        logger.warning("Unsupervised model tidak ada — jalankan train_unsupervised.py dulu.")

    yield
    logger.info("Classifier service shutdown.")


app = FastAPI(
    title="LTI Anti-Phishing Classifier",
    version="2.0.0",       # Dual-layer version
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)


# ─── Request/Response Schema ──────────────────────────────────────────────────

class EmailPredictRequest(BaseModel):
    raw_email: str
    email_id: str = ""


class FeatureContribution(BaseModel):
    feature: str
    shap_value: float
    direction: str


class PredictResponse(BaseModel):
    email_id: str
    spam_probability: float       # Supervised ML score
    is_spam: bool
    label: str
    top_reasons: list[FeatureContribution]
    xai_summary: str


class UnsupervisedPredictResponse(BaseModel):
    email_id: str
    anomaly_score: float          # Unsupervised anomaly score
    is_anomaly: bool
    anomaly_type: str


class DualPredictResponse(BaseModel):
    email_id: str
    spam_probability: float       # Supervised
    anomaly_score: float          # Unsupervised
    is_anomaly: bool
    label: str
    top_reasons: list[FeatureContribution]
    xai_summary: str


# ─── Helper ───────────────────────────────────────────────────────────────────

def _compute_label(prob: float) -> str:
    """Tentukan label routing dari supervised probability."""
    clean_thresh = float(app.state.threshold_clean if hasattr(app.state, "threshold_clean") else 0.30)
    warn_thresh  = float(app.state.threshold_warn  if hasattr(app.state, "threshold_warn")  else 0.70)
    if prob < clean_thresh:
        return "CLEAN"
    elif prob < warn_thresh:
        return "WARN"
    else:
        return "QUARANTINE"


# ─── Internal Functions (reusable by multiple endpoints) ──────────────────────

def _predict_supervised_internal(raw_email: str, email_id: str) -> PredictResponse:
    """Internal supervised prediction — tidak tergantung FastAPI request."""
    parser = EmailParser()
    extractor = FeatureExtractor()
    parsed = parser.parse(raw_email)
    features = extractor.extract(parsed)

    import pandas as pd
    row = {
        "combined_text": features.combined_text,
        **{f: getattr(features, f, 0) for f in STRUCTURED_FEATURES},
    }
    df_row = pd.DataFrame([row])
    X = build_feature_matrix(df_row, state.tfidf, state.scaler, fit=False)
    prob = float(state.model.predict_proba(X)[0, 1])
    label = _compute_label(prob)

    if state.explainer is not None:
        try:
            X_dense = X.toarray()
            shap_vals = state.explainer.shap_values(X_dense)[0]
        except Exception as e:
            logger.warning("SHAP failed: %s", e)
            shap_vals = None
    else:
        shap_vals = None

    tfidf_names = state.tfidf.get_feature_names_out().tolist()
    all_names = tfidf_names + STRUCTURED_FEATURES

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

    reasons = []
    for name, val in top_spam:
        reasons.append(FeatureContribution(
            feature=name, shap_value=round(float(val), 4), direction="spam",
        ))
    for name, val in top_ham:
        reasons.append(FeatureContribution(
            feature=name, shap_value=round(float(val), 4), direction="ham",
        ))

    xai_parts = []
    if prob > 0.30:
        if features.urgency_score > 0.3:
            xai_parts.append(f"Urgency-Score:{features.urgency_score:.2f}")
        if features.has_lookalike_domain:
            xai_parts.append(f"Lookalike-Domain:Distance={features.min_levenshtein_to_protected}")
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
            xai_parts.append(f"Top-SHAP:{top_spam[0][0]}")

    xai_summary = (
        f"SpamProb={prob:.2f}; " + "; ".join(xai_parts)
        if xai_parts else f"SpamProb={prob:.2f}; No major red flags"
    )

    return PredictResponse(
        email_id=email_id or parsed.raw_id,
        spam_probability=round(prob, 4),
        is_spam=label in ("QUARANTINE", "WARN"),
        label=label,
        top_reasons=reasons,
        xai_summary=xai_summary,
    )


def _predict_unsupervised_internal(raw_email: str, email_id: str) -> UnsupervisedPredictResponse:
    """Internal unsupervised prediction — tidak tergantung FastAPI request."""
    result = state.anomaly.predict(raw_email)
    return UnsupervisedPredictResponse(
        email_id=email_id or "unknown",
        anomaly_score=result.anomaly_score,
        is_anomaly=result.is_anomaly,
        anomaly_type=result.anomaly_type,
    )


# ─── Endpoint: Supervised ─────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictResponse)
async def predict(req: EmailPredictRequest):
    """Layer 1 — Supervised XGBoost prediction with SHAP XAI."""
    if state.model is None:
        raise HTTPException(503, "Model belum diload.")
    try:
        return _predict_supervised_internal(req.raw_email, req.email_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Prediction error: %s", e)
        raise HTTPException(500, f"Prediction error: {e}")


# ─── Endpoint: Unsupervised ───────────────────────────────────────────────────

@app.post("/predict-unsupervised", response_model=UnsupervisedPredictResponse)
async def predict_unsupervised(req: EmailPredictRequest):
    """Layer 2 — Unsupervised anomaly detection (Isolation Forest + One-Class SVM).
    Tidak butuh data spam — hanya deteksi penyimpangan dari pola email normal.
    """
    if state.anomaly is None or not state.anomaly.is_fitted:
        raise HTTPException(503, "Unsupervised model belum diload / belum di-train.")
    try:
        return _predict_unsupervised_internal(req.raw_email, req.email_id)
    except Exception as e:
        logger.error("Anomaly detection error: %s", e)
        raise HTTPException(500, f"Anomaly detection error: {e}")


# ─── Endpoint: Dual Layer ─────────────────────────────────────────────────────

@app.post("/predict-dual", response_model=DualPredictResponse)
async def predict_dual(req: EmailPredictRequest):
    """Dual-layer prediction: Supervised (XGBoost) + Unsupervised (IForest/OCSVM).
    Untuk worker pipeline — mendapatkan kedua skor dalam satu panggilan.
    """
    supervised = _predict_supervised_internal(req.raw_email, req.email_id)
    unsupervised = _predict_unsupervised_internal(req.raw_email, req.email_id)
    return DualPredictResponse(
        email_id=supervised.email_id,
        spam_probability=supervised.spam_probability,
        anomaly_score=unsupervised.anomaly_score,
        is_anomaly=unsupervised.is_anomaly,
        label=supervised.label,
        top_reasons=supervised.top_reasons,
        xai_summary=supervised.xai_summary,
    )

    return PredictResponse(
        email_id=req.email_id or parsed.raw_id,
        spam_probability=round(prob, 4),
        is_spam=label in ("QUARANTINE", "WARN"),
        label=label,
        top_reasons=reasons,
        xai_summary=xai_summary,
    )


# ─── Endpoint: Unsupervised ───────────────────────────────────────────────────

@app.post("/predict-unsupervised", response_model=UnsupervisedPredictResponse)
async def predict_unsupervised(req: EmailPredictRequest):
    """Layer 2 — Unsupervised anomaly detection (Isolation Forest + One-Class SVM).

    Tidak butuh data spam — hanya deteksi penyimpangan dari pola email normal.
    """
    if state.anomaly is None or not state.anomaly.is_fitted:
        raise HTTPException(503, "Unsupervised model belum diload / belum di-train.")

    try:
        result = state.anomaly.predict(req.raw_email)
    except Exception as e:
        logger.error("Anomaly detection error: %s", e)
        raise HTTPException(500, f"Anomaly detection error: {e}")

    return UnsupervisedPredictResponse(
        email_id=req.email_id or "unknown",
        anomaly_score=result.anomaly_score,
        is_anomaly=result.is_anomaly,
        anomaly_type=result.anomaly_type,
    )


# ─── Endpoint: Dual Layer ─────────────────────────────────────────────────────

@app.post("/predict-dual", response_model=DualPredictResponse)
async def predict_dual(req: EmailPredictRequest):
    """Dual-layer prediction: Supervised (XGBoost) + Unsupervised (IForest/OCSVM).

    Untuk worker pipeline — mendapatkan kedua skor dalam satu panggilan.
    """
    supervised = await predict(req)
    unsupervised = await predict_unsupervised(req)

    return DualPredictResponse(
        email_id=supervised.email_id,
        spam_probability=supervised.spam_probability,
        anomaly_score=unsupervised.anomaly_score,
        is_anomaly=unsupervised.is_anomaly,
        label=supervised.label,
        top_reasons=supervised.top_reasons,
        xai_summary=supervised.xai_summary,
    )


# ─── Utility Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "supervised_loaded": state.model is not None,
        "unsupervised_loaded": state.anomaly is not None and state.anomaly.is_fitted,
    }


@app.get("/model-info")
async def model_info():
    if state.model is None:
        raise HTTPException(503, "Model belum diload.")
    info = {
        "supervised": {
            "n_estimators": state.model.n_estimators,
            "tfidf_vocab_size": len(state.tfidf.vocabulary_),
            "structured_features": STRUCTURED_FEATURES,
        },
        "unsupervised": {
            "loaded": state.anomaly is not None and state.anomaly.is_fitted,
        }
    }
    return info
