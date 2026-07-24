"""
Unsupervised Anomaly Detection Layer untuk CogniMail Classifier.

Layer 2 — Unsupervised (Unknown / Zero-day threats):
  - Isolation Forest: dilatih HANYA dengan email bersih
  - One-Class SVM: alternatif yang lebih sensitif

Email yang "tidak normal" menurut baseline = anomali = waspada.
Tidak perlu data spam berlabel — cukup email bersih dari operasional organisasi.

Feature set (22 fitur numerik):
  Sama dengan STRUCTURED_FEATURES tapi tanpa TF-IDF — cocok untuk tree-based anomaly.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler

from classifier.features import (
    EmailParser, FeatureExtractor, ParsedEmail, STRUCTURED_FEATURES
)

logger = logging.getLogger(__name__)

MODEL_DIR = Path("classifier/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Fitur yang dipakai untuk unsupervised (subset dari STRUCTURED_FEATURES, tanpa TF-IDF).
# Defined explicitly instead of a fragile positional slice so that adding new
# features to STRUCTURED_FEATURES never silently shifts this list.
UNSUPERVISED_FEATURES = [
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

# Sanity-check: every unsupervised feature must exist in the master list.
_missing_unsupervised = [f for f in UNSUPERVISED_FEATURES if f not in STRUCTURED_FEATURES]
if _missing_unsupervised:
    raise RuntimeError(
        f"UNSUPERVISED_FEATURES references features not in STRUCTURED_FEATURES: "
        f"{_missing_unsupervised}. Update classifier/unsupervised.py to match "
        f"classifier/features.py STRUCTURED_FEATURES."
    )

# Validate all unsupervised features exist on the EmailFeatures dataclass.
from classifier.features import EmailFeatures
_missing_feature_attrs = [f for f in UNSUPERVISED_FEATURES if not hasattr(EmailFeatures, f)]
if _missing_feature_attrs:
    raise RuntimeError(
        f"UNSUPERVISED_FEATURES references fields not on EmailFeatures dataclass: "
        f"{_missing_feature_attrs}. Update classifier/features.py EmailFeatures."
    )

# Kolom boolean yang perlu dikonversi float (untuk StandardScaler)
BOOL_FEATURES = [
    "has_url_shortener", "has_lookalike_domain", "has_executable_attachment",
    "spf_pass", "dkim_pass", "dmarc_pass", "display_name_mismatch",
    "subject_has_re_fwd_fake", "is_bulk_sender", "javascript_present",
]


@dataclass
class AnomalyResult:
    """Hasil deteksi anomali untuk satu email."""
    anomaly_score: float        # 0.0 = normal, 1.0 = sangat anomali
    is_anomaly: bool            # True jika di atas threshold
    anomaly_type: str           # "isolation_forest" atau "one_class_svm"


class AnomalyDetector:
    """
    Detektor anomali dua-model: Isolation Forest + One-Class SVM.

    Keduanya dilatih HANYA dengan email bersih (ham).
    Semakin tinggi anomaly_score, semakin mencurigakan.
    """

    def __init__(self):
        self.isolation_forest: IsolationForest = None
        self.one_class_svm: OneClassSVM = None
        self.scaler: StandardScaler = None
        self._is_fitted = False

    def build_feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """
        Bangun feature matrix dari DataFrame untuk unsupervised.
        Hanya pakai fitur numerik — tanpa TF-IDF.

        Args:
            df: DataFrame dengan kolom STRUCTURED_FEATURES

        Returns:
            np.ndarray (n_samples, n_features)
        """
        missing = [c for c in UNSUPERVISED_FEATURES if c not in df.columns]
        if missing:
            raise ValueError(f"Kolom tidak ditemukan: {missing}")

        X = df[UNSUPERVISED_FEATURES].astype(float).fillna(0).values
        return X

    def extract_from_parsed(self, parsed: ParsedEmail) -> dict:
        """
        Ekstrak fitur dari ParsedEmail untuk inference.

        Returns:
            Dict dengan key = UNSUPERVISED_FEATURES
        """
        extractor = FeatureExtractor()
        features = extractor.extract(parsed)
        return {f: getattr(features, f, 0) for f in UNSUPERVISED_FEATURES}

    def extract_from_raw(self, raw_email: str) -> dict:
        """Parse + extract dari raw email string."""
        parser = EmailParser()
        parsed = parser.parse(raw_email)
        return self.extract_from_parsed(parsed)

    def fit(self, clean_emails_df: pd.DataFrame):
        """
        Latih Isolation Forest + One-Class SVM HANYA dari email bersih.

        Args:
            clean_emails_df: DataFrame dengan kolom STRUCTURED_FEATURES
                            HANYA dari email bersih (label=0/ham)
        """
        logger.info("Training unsupervised anomaly detectors on %d clean samples...",
                    len(clean_emails_df))

        X = self.build_feature_matrix(clean_emails_df)

        # StandardScaler: normalisasi fitur
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Isolation Forest — lebih cepat, lebih robust
        logger.info("Training Isolation Forest (contamination=0.05)...")
        self.isolation_forest = IsolationForest(
            n_estimators=200,
            max_samples=1.0,
            contamination=0.05,      # expect ~5% anomalies in production
            random_state=42,
            n_jobs=-1,
        )
        self.isolation_forest.fit(X_scaled)

        # One-Class SVM — lebih sensitif, cocok untuk zero-day
        logger.info("Training One-Class SVM (nu=0.05, kernel=rbf)...")
        self.one_class_svm = OneClassSVM(
            nu=0.05,
            kernel="rbf",
            gamma="scale",
        )
        self.one_class_svm.fit(X_scaled)

        self._is_fitted = True
        logger.info("Both unsupervised models trained successfully.")

        # Feature importance dari Isolation Forest (optional logging)
        if hasattr(self.isolation_forest, "feature_importances_"):
            importances = self.isolation_forest.feature_importances_
            top_n = min(10, len(UNSUPERVISED_FEATURES))
            top_idx = np.argsort(importances)[::-1][:top_n]
            logger.info("Top %d features (IForest importance):", top_n)
            for i in top_idx:
                logger.info("  %-35s %.4f", UNSUPERVISED_FEATURES[i], importances[i])

    def predict(self, raw_email: str) -> AnomalyResult:
        """
        Prediksi anomali untuk satu email.

        Args:
            raw_email: Raw email string

        Returns:
            AnomalyResult dengan score 0.0–1.0
        """
        if not self._is_fitted:
            raise RuntimeError("Model belum di-train. Jalankan fit() dulu.")

        feature_dict = self.extract_from_raw(raw_email)
        df = pd.DataFrame([feature_dict])
        X = self.build_feature_matrix(df)
        X_scaled = self.scaler.transform(X)

        # Isolation Forest: decision_function = higher = more normal
        # invert: higher anomaly_score = more anomalous
        if_score_raw = self.isolation_forest.decision_function(X_scaled)[0]
        if_pred = self.isolation_forest.predict(X_scaled)[0]

        # Konversi decision_function (-1 anomali, +1 normal) ke 0–1 score
        # decision_function range typically [-0.5, 0.5] for inliers
        # Normalisasi sigmoid-ish
        if_score = 1.0 - (if_score_raw + 1.0) / 2.0
        if_score = float(np.clip(if_score, 0.0, 1.0))

        # One-Class SVM: decision_function = signed distance
        # Hanya pakai IF untuk scoring final, OCSVM sebagai konfirmasi
        try:
            ocsvm_score_raw = self.one_class_svm.decision_function(X_scaled)[0]
            ocsvm_pred = self.one_class_svm.predict(X_scaled)[0]
        except Exception:
            ocsvm_score_raw = 0.0
            ocsvm_pred = 1

        # OCSVM decision: -1 = anomali, +1 = normal
        # Konversi juga ke 0–1
        ocsvm_score = 1.0 - (ocsvm_score_raw + 1.0) / 2.0
        ocsvm_score = float(np.clip(ocsvm_score, 0.0, 1.0))

        # Fusion: average kedua model untuk final anomaly score
        # IF diberi bobot 0.6, OCSVM 0.4 (IF lebih stabil)
        anomaly_score = (if_score * 0.6) + (ocsvm_score * 0.4)
        is_anomaly = if_pred == -1 or ocsvm_pred == -1

        return AnomalyResult(
            anomaly_score=round(anomaly_score, 4),
            is_anomaly=is_anomaly,
            anomaly_type="ensemble_if_ocsvm",
        )

    def save(self, suffix: str = ""):
        """Simpan semua artefak model."""
        if not self._is_fitted:
            raise RuntimeError("Belum ada model yang di-train.")

        suffix_str = f"_{suffix}" if suffix else ""
        if_path = MODEL_DIR / f"isolation_forest{suffix_str}.joblib"
        ocsvm_path = MODEL_DIR / f"one_class_svm{suffix_str}.joblib"
        scaler_path = MODEL_DIR / f"unsupervised_scaler{suffix_str}.joblib"

        joblib.dump(self.isolation_forest, if_path)
        joblib.dump(self.one_class_svm, ocsvm_path)
        joblib.dump(self.scaler, scaler_path)

        # Save _latest versions directly (not symlinks — Windows compatibility)
        versioned_to_latest = {
            if_path: MODEL_DIR / "isolation_forest_latest.joblib",
            ocsvm_path: MODEL_DIR / "one_class_svm_latest.joblib",
            scaler_path: MODEL_DIR / "unsupervised_scaler_latest.joblib",
        }
        for versioned, latest in versioned_to_latest.items():
            if latest.exists():
                latest.unlink()
            # Copy the actual file content to _latest name
            import shutil
            shutil.copy2(versioned, latest)

        logger.info("Unsupervised models saved to %s", MODEL_DIR)

        # Metadata
        meta = {
            "isolation_forest_path": str(if_path),
            "one_class_svm_path": str(ocsvm_path),
            "features": UNSUPERVISED_FEATURES,
            "n_features": len(UNSUPERVISED_FEATURES),
        }
        meta_path = MODEL_DIR / f"unsupervised_metadata{suffix_str}.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    def load(self):
        """Load model terbaru dari MODEL_DIR."""
        self.isolation_forest = None
        self.one_class_svm = None
        self.scaler = None
        self._is_fitted = False
        try:
            self.isolation_forest = joblib.load(
                MODEL_DIR / "isolation_forest_latest.joblib"
            )
            self.one_class_svm = joblib.load(
                MODEL_DIR / "one_class_svm_latest.joblib"
            )
            self.scaler = joblib.load(
                MODEL_DIR / "unsupervised_scaler_latest.joblib"
            )
            self._is_fitted = True
            logger.info("Unsupervised models loaded from %s", MODEL_DIR)
        except FileNotFoundError as e:
            logger.warning("Unsupervised model belum ada: %s", e)

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def predict_batch(self, raw_emails: list[str]) -> list[AnomalyResult]:
        """Batch prediction."""
        return [self.predict(email) for email in raw_emails]
