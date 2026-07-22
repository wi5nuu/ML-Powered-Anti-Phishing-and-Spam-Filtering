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

    struct_df = df[MODEL_STRUCTURED_FEATURES].astype(float).fillna(0)
    if fit:
        struct_scaled = scaler.fit_transform(struct_df)
    else:
        struct_scaled = scaler.transform(struct_df)

    return hstack([tfidf_matrix, csr_matrix(struct_scaled)])
