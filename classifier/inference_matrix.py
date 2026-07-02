from scipy.sparse import csr_matrix, hstack


MODEL_STRUCTURED_FEATURES = [
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
