"""
FastAPI inference service untuk CogniMail Classifier.

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
import shap
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from classifier.features import (
    EmailParser, FeatureExtractor, STRUCTURED_FEATURES
)
from classifier.inference_matrix import build_feature_matrix
from classifier.unsupervised import AnomalyDetector

logger = logging.getLogger(__name__)

MODEL_DIR = Path("classifier/models")


# ─── Model State (singleton, load sekali waktu startup) ───────────────────────

class ModelState:
    model = None        # XGBoost
    tfidf = None
    scaler = None
    explainer = None
    anomaly = None      # Unsupervised detector
    tfidf_feature_names: list = []
    all_feature_names: list = []

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
        # Cache feature names (jangan panggil get_feature_names_out() per-request)
        state.tfidf_feature_names = state.tfidf.get_feature_names_out().tolist()
        state.all_feature_names = state.tfidf_feature_names + STRUCTURED_FEATURES

        # ── BUG-007: Validate model input dimension matches feature pipeline ──
        # The XGBoost model was trained with a fixed number of input columns.
        # If STRUCTURED_FEATURES drifted (feature added/removed/reordered) but
        # the model artifact was not retrained, every prediction will be silently
        # wrong or crash with a cryptic XGBoost error at inference time.
        # Catch this at startup instead of at request time.
        expected_n_features = len(state.all_feature_names)
        model_n_features = state.model.n_features_in_
        if model_n_features != expected_n_features:
            raise RuntimeError(
                f"Feature count mismatch: model was trained with "
                f"{model_n_features} features but the current pipeline produces "
                f"{expected_n_features} features "
                f"(tfidf={len(state.tfidf_feature_names)} + "
                f"structured={len(STRUCTURED_FEATURES)}). "
                f"Retrain the model or revert the STRUCTURED_FEATURES change."
            )

        logger.info(
            "Supervised (XGBoost) model loaded. TF-IDF vocab: %d words, "
            "structured: %d, total features: %d",
            len(state.tfidf_feature_names),
            len(STRUCTURED_FEATURES),
            expected_n_features,
        )
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

    # Warmup: paksa lazy initialization (tldextract, langdetect, Sastrawi)
    logger.info("Warming up lazy initializations...")
    try:
        import tldextract as _tld
        _tld.TLDExtract()("http://lodaya.id")
        from langdetect import detect as _detect
        _detect("test")
        from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
        StemmerFactory().create_stemmer().stem("testing")
        import numpy as np
        if state.explainer is not None:
            _dummy = np.zeros((1, len(state.all_feature_names)), dtype=np.float32)
            state.explainer.shap_values(_dummy)
        logger.info("  Lazy init complete")
    except Exception as e:
        logger.warning("Warmup failed (non-critical): %s", e)

    yield
    logger.info("Classifier service shutdown.")


app = FastAPI(
    title="CogniMail Classifier",
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

    all_names = state.all_feature_names

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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _predict_supervised_internal, req.raw_email, req.email_id
        )
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
    Worker pipeline — kedua skor dalam satu panggilan.
    Fungsi heavy (SHAP, XGBoost) di-offload ke thread biar gak blocking.
    """
    loop = asyncio.get_running_loop()
    supervised, unsupervised = await asyncio.gather(
        loop.run_in_executor(None, _predict_supervised_internal, req.raw_email, req.email_id),
        loop.run_in_executor(None, _predict_unsupervised_internal, req.raw_email, req.email_id),
    )
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
