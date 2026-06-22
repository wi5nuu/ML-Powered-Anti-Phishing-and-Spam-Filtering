# Architecture — LTI Anti-Phishing & Spam Filtering

## Overview

Sistem ini adalah pipeline filtering email asinkron dengan **Dual Detection Architecture**:
tiga lapisan deteksi yang bekerja paralel untuk mendeteksi spam, phishing, dan zero-day threats.

### Tiga Lapisan Deteksi

| Lapisan | Metode | Data Training | Keunggulan |
|---------|--------|--------------|------------|
| **Layer 1** — Supervised | XGBoost + TF-IDF (50.000 fitur) | Dataset berlabel spam/ham | Akurat untuk pola spam yang sudah dikenal |
| **Layer 2** — Unsupervised | Isolation Forest + One-Class SVM | HANYA email bersih (0 data spam!) | Deteksi zero-day / anomali yang belum pernah ada labelnya |
| **Layer 3** — Rule-based | SpamAssassin | Rule signatures | Reliable untuk spam pattern klasik |

## Flow

```
Email Masuk (SMTP -> Mailpit) -> Mailpit API Fetcher -> Redis Queue
                                               |
                    +--------------------------+
                    |                          |
            SpamAssassin          Dual-Layer Classifier API
            (rule-based)           /                    \
                    +-----------> Layer 1: XGBoost      |
                    |             (supervised, TF-IDF)  |
                    |             Layer 2: IForest+OCSVM|
                    |             (unsupervised, zero-  |
                    |              shot anomaly)         |
                    |                          |         |
                    +-----------+--------------+---------+
                                |
                         Decision Engine
                     (3-way weighted fusion
                      ML 50% + SA 25% + Anomaly 25%)
                                |
                     +----------+----------+
                     |          |          |
                   CLEAN      WARN    QUARANTINE
                   (inbox)   (+header)   (DB)
                                           |
                                     Admin Dashboard
```

## Komponen Utama

1. **Ingestion** — Mailpit API fetcher, email parser, Redis queue producer
2. **Classifier API** — FastAPI service, 3 endpoints:
   - `POST /predict` — supervised XGBoost + TF-IDF + SHAP
   - `POST /predict-unsupervised` — Isolation Forest + One-Class SVM (zero-shot anomaly)
   - `POST /predict-dual` — kedua layer sekaligus (untuk worker)
3. **Worker** — Redis consumer, orchestrates SA + Dual ML scoring, 3-way decision engine
4. **Decision Engine** — 3-way weighted fusion (ML 50%, SA 25%, Anomaly 25%), hard overrides
5. **Dashboard** — FastAPI + Jinja2, quarantine review, anomaly score display, metrics, feedback loop
6. **Domain Monitor** — dnstwist-based lookalike domain detection

## Stack

- Python 3.11, FastAPI, SQLAlchemy, XGBoost, scikit-learn
- Isolation Forest, One-Class SVM (scikit-learn)
- Redis (queue), PostgreSQL (storage), SpamAssassin (rule scoring)
- Docker Compose (orchestration), Prometheus (monitoring)
