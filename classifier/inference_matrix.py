import numpy as np
from scipy.sparse import csr_matrix, hstack

# Single source-of-truth: import from features so inference_matrix and
# classifier/predict always use the identical feature list in the exact
# same order as the model was trained with.
from classifier.features import STRUCTURED_FEATURES as MODEL_STRUCTURED_FEATURES  # noqa: F401


def build_feature_matrix(df, tfidf, scaler, fit: bool = False):
    texts = df["combined_text"].fillna("").astype(str)
    if fit:
        tfidf_matrix = tfidf.fit_transform(texts)
    else:
        tfidf_matrix = tfidf.transform(texts)

    missing = [c for c in MODEL_STRUCTURED_FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"Missing structured features in input DataFrame: {missing}")

    struct_df = df[MODEL_STRUCTURED_FEATURES].astype(float).fillna(0)
    if fit:
        struct_scaled = scaler.fit_transform(struct_df)
    else:
        struct_scaled = scaler.transform(struct_df)

    struct_scaled = np.nan_to_num(struct_scaled, nan=0.0, posinf=0.0, neginf=0.0)

    return hstack([tfidf_matrix, csr_matrix(struct_scaled)])
