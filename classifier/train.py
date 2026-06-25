"""
Training pipeline untuk LTI Anti-Phishing Classifier.

Arsitektur model:
  - Stage 1: TF-IDF (50.000 fitur) dari combined_text
  - Stage 2: 20 fitur terstruktur dari EmailFeatures
  - Stage 3: scipy.sparse.hstack untuk gabungkan keduanya
  - Model: XGBoostClassifier dengan hyperparameter tuned via RandomizedSearchCV
  - Explainability: SHAP values untuk X-Spam-Reason
"""

import json
import logging
from pathlib import Path
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import shap
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import (
    train_test_split, StratifiedKFold, cross_validate, RandomizedSearchCV
)
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve, precision_recall_curve,
    average_precision_score
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

MODEL_DIR = Path("classifier/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ─── Fitur terstruktur yang dipakai (JANGAN ubah urutan — breaking change) ───

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
]


def build_feature_matrix(df: pd.DataFrame, tfidf: TfidfVectorizer,
                          scaler: StandardScaler, fit: bool = False):
    """
    Bangun feature matrix hybrid dari DataFrame.

    Args:
        df: DataFrame dengan kolom combined_text + semua STRUCTURED_FEATURES
        tfidf: TF-IDF vectorizer (sudah fit atau akan di-fit)
        scaler: StandardScaler untuk fitur numerik
        fit: Jika True, fit tfidf dan scaler sebelum transform

    Returns:
        scipy sparse matrix: TF-IDF + structured features digabung
    """
    # Fill NaN combined_text and ensure string type
    texts = df["combined_text"].fillna("").astype(str)
    # TF-IDF sparse matrix
    if fit:
        tfidf_matrix = tfidf.fit_transform(texts)
    else:
        tfidf_matrix = tfidf.transform(texts)

    # Structured features (dense -> sparse)
    struct_df = df[STRUCTURED_FEATURES].astype(float).fillna(0)
    if fit:
        struct_scaled = scaler.fit_transform(struct_df)
    else:
        struct_scaled = scaler.transform(struct_df)

    from scipy.sparse import csr_matrix
    struct_sparse = csr_matrix(struct_scaled)

    # Gabungkan horizontal
    return hstack([tfidf_matrix, struct_sparse])


def train(data_path: str, output_suffix: str = ""):
    """
    Pipeline training lengkap.

    Args:
        data_path: Path ke CSV dengan kolom: combined_text, [STRUCTURED_FEATURES], label
        output_suffix: Suffix tambahan untuk nama file model
    """
    logger.info("Loading dataset dari %s", data_path)
    df = pd.read_csv(data_path)

    # Validasi kolom
    required_cols = ["combined_text", "label"] + STRUCTURED_FEATURES
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom tidak ditemukan di dataset: {missing}")

    logger.info("Dataset: %d baris, distribusi label:\n%s",
                len(df), df["label"].value_counts().to_string())

    X_text_all = df["combined_text"]
    y = df["label"]

    # Split stratified — pertahankan proporsi label
    X_train_df, X_test_df, y_train, y_test = train_test_split(
        df, y, test_size=0.15, random_state=42, stratify=y
    )
    logger.info("Train: %d, Test: %d", len(X_train_df), len(X_test_df))

    # ── Inisialisasi komponen ─────────────────────────────────────────────
    tfidf = TfidfVectorizer(
        max_features=50_000,
        ngram_range=(1, 2),          # Unigram + bigram
        sublinear_tf=True,           # Kurangi dominasi term yang terlalu sering
        strip_accents="unicode",
        analyzer="word",
        min_df=2,                    # Abaikan term yang muncul <2x
        max_df=0.95,                 # Abaikan term di >95% dokumen
    )
    scaler = StandardScaler()

    # Build feature matrix
    logger.info("Building feature matrices...")
    X_train = build_feature_matrix(X_train_df, tfidf, scaler, fit=True)
    X_test  = build_feature_matrix(X_test_df,  tfidf, scaler, fit=False)

    # ── Model ────────────────────────────────────────────────────────────
    n_samples = X_train.shape[0]
    scale_pos = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    if n_samples > 50000:
        # Skip hyperparameter search for large datasets — train directly
        logger.info("Large dataset (%d samples): training directly (skip search)", n_samples)
        best_model = XGBClassifier(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos,
            tree_method="hist",
            device="cuda",
            eval_metric="logloss",
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1,
        )
        best_model.fit(X_train, y_train)
    else:
        # Dataset <50k: full search with CPU hist
        xgb_params = {
            "n_estimators": [300, 500, 700],
            "max_depth": [4, 6, 8],
            "learning_rate": [0.05, 0.1, 0.2],
            "subsample": [0.7, 0.8, 1.0],
            "colsample_bytree": [0.6, 0.8, 1.0],
            "scale_pos_weight": [scale_pos],
            "tree_method": ["hist"],
            "eval_metric": ["logloss"],
        }
        base_xgb = XGBClassifier(
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1,
            device="cuda",
        )
        logger.info("Mulai RandomizedSearchCV (10 iter x 3 fold)...")
        search = RandomizedSearchCV(
            base_xgb, xgb_params,
            n_iter=10, cv=3, scoring="roc_auc",
            verbose=1, random_state=42, n_jobs=-1,
            refit=True,
        )
        search.fit(X_train, y_train)
        best_model = search.best_estimator_
        logger.info("Best params: %s", search.best_params_)
        logger.info("Best CV ROC-AUC: %.4f", search.best_score_)

    # ── Evaluasi Test Set ─────────────────────────────────────────────────
    y_pred      = best_model.predict(X_test)
    y_prob      = best_model.predict_proba(X_test)[:, 1]
    roc_auc     = roc_auc_score(y_test, y_prob)
    avg_prec    = average_precision_score(y_test, y_prob)
    cm          = confusion_matrix(y_test, y_pred)
    report_str  = classification_report(y_test, y_pred,
                                        target_names=["ham", "spam"])

    # False Positive & False Negative breakdown
    tn, fp, fn, tp = cm.ravel()

    logger.info("\n%s", report_str)
    logger.info("ROC-AUC: %.4f | Avg Precision: %.4f", roc_auc, avg_prec)
    logger.info("TP=%d  FP=%d  FN=%d  TN=%d", tp, fp, fn, tn)
    logger.info(
        "False Positive Rate (email legit tanda spam): %.2f%%",
        (fp / max(fp + tn, 1)) * 100
    )

    # ── Adversarial test set evaluation ───────────────────────────────────
    # Cek apakah ada adversarial test set
    adversarial_path = Path("data/processed/adversarial_test.csv")
    if adversarial_path.exists():
        logger.info("Mengevaluasi adversarial test set...")
        adv_df = pd.read_csv(adversarial_path)
        X_adv = build_feature_matrix(adv_df, tfidf, scaler, fit=False)
        adv_pred = best_model.predict(X_adv)
        adv_prob = best_model.predict_proba(X_adv)[:, 1]
        logger.info("Adversarial set classification report:\n%s",
                    classification_report(adv_df["label"], adv_pred,
                                         target_names=["ham", "spam"]))
        logger.info("Adversarial ROC-AUC: %.4f",
                    roc_auc_score(adv_df["label"], adv_prob))
    else:
        logger.warning(
            "Adversarial test set tidak ditemukan di %s. "
            "Buat data/processed/adversarial_test.csv untuk evaluasi lengkap.",
            adversarial_path
        )

    # ── SHAP untuk explainability (skip untuk dataset besar >50k) ─────────
    if n_samples <= 50000 and y_prob is not None:
        logger.info("Computing SHAP values (sample 200 untuk efisiensi)...")
        sample_idx = np.random.choice(X_test.shape[0],
                                      size=min(200, X_test.shape[0]),
                                      replace=False)
        X_test_dense = X_test[sample_idx].toarray()
        explainer = shap.TreeExplainer(best_model)
        shap_values = explainer.shap_values(X_test_dense)
    else:
        shap_values = None
        logger.info("Skipping SHAP (large dataset)")

    # Feature names untuk SHAP
    tfidf_feature_names = tfidf.get_feature_names_out().tolist()
    all_feature_names = tfidf_feature_names + STRUCTURED_FEATURES

    # Top 20 global feature importance (jika SHAP dihitung)
    top_features = []
    if shap_values is not None:
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        top_features = sorted(
            zip(all_feature_names, mean_abs_shap),
            key=lambda x: x[1], reverse=True
        )[:20]
        logger.info("Top 20 Global SHAP Features:")
        for fname, importance in top_features:
            logger.info("  %-40s %.4f", fname, importance)
    else:
        # Gunakan feature_importances_ dari XGBoost sebagai alternatif
        fi = best_model.feature_importances_
        top_idx = np.argsort(fi)[-20:][::-1]
        for idx in top_idx:
            if idx < len(all_feature_names):
                top_features.append((all_feature_names[idx], float(fi[idx])))
        logger.info("Top 20 Global Feature Importances (XGBoost):")
        for fname, importance in top_features:
            logger.info("  %-40s %.4f", fname, importance)

    # ── Simpan artefak model ──────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{output_suffix}" if output_suffix else ""
    model_path = MODEL_DIR / f"xgb_model{suffix}_{timestamp}.joblib"
    tfidf_path = MODEL_DIR / f"tfidf{suffix}_{timestamp}.joblib"
    scaler_path = MODEL_DIR / f"scaler{suffix}_{timestamp}.joblib"

    # Symlink "latest" supaya serving service selalu pakai model terbaru
    latest_model  = MODEL_DIR / "xgb_model_latest.joblib"
    latest_tfidf  = MODEL_DIR / "tfidf_latest.joblib"
    latest_scaler = MODEL_DIR / "scaler_latest.joblib"

    joblib.dump(best_model, model_path)
    joblib.dump(tfidf, tfidf_path)
    joblib.dump(scaler, scaler_path)

    for latest, versioned in [
        (latest_model, model_path),
        (latest_tfidf, tfidf_path),
        (latest_scaler, scaler_path),
    ]:
        if latest.exists():
            latest.unlink()
        import shutil
        shutil.copy2(versioned, latest)

    # Simpan metadata evaluasi sebagai JSON
    best_params = getattr(search, 'best_params_', None) if 'search' in dir() else None
    cv_score = float(getattr(search, 'best_score_', 0.0)) if 'search' in dir() and hasattr(search, 'best_score_') else None
    metadata = {
        "timestamp": timestamp,
        "dataset": data_path,
        "train_size": len(X_train_df),
        "test_size": len(X_test_df),
        "best_params": best_params if best_params else "direct_fit",
        "cv_roc_auc": cv_score,
        "test_roc_auc": float(roc_auc),
        "test_avg_precision": float(avg_prec),
        "confusion_matrix": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
        "false_positive_rate_pct": round((fp / max(fp + tn, 1)) * 100, 2),
        "false_negative_rate_pct": round((fn / max(fn + tp, 1)) * 100, 2),
        "top_features": [
            {"feature": f, "importance": float(v)}
            for f, v in top_features
        ],
        "model_path": str(model_path),
        "tfidf_path": str(tfidf_path),
        "scaler_path": str(scaler_path),
        "structured_features": STRUCTURED_FEATURES,
        "tfidf_vocab_size": len(tfidf.vocabulary_),
    }

    meta_path = MODEL_DIR / f"metadata{suffix}_{timestamp}.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("✅ Model tersimpan: %s", model_path)
    logger.info("✅ Metadata evaluasi: %s", meta_path)

    return best_model, tfidf, scaler, metadata


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    data_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/train.csv"
    train(data_path)
