# Architecture — LTI Anti-Phishing & Spam Filtering

## Overview

Sistem ini adalah pipeline filtering email asinkron yang menggabungkan rule-based
scoring (SpamAssassin) dengan ML classifier (TF-IDF + XGBoost) untuk mendeteksi
phishing dan spam.

## Flow

```
Email Masuk (SMTP -> Mailpit) -> Mailpit API Fetcher -> Redis Queue
                                               |
                    +--------------------------+
                    |                          |
            SpamAssassin                ML Classifier
            (rule-based)                (TF-IDF + XGBoost)
                    |                          |
                    +-----------+--------------+
                                |
                         Decision Engine
                         (weighted fusion)
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
2. **Classifier** — FastAPI service, TF-IDF vectorizer, XGBoost model, SHAP explainer
3. **Worker** — Redis consumer, orchestrates SA + ML scoring, decision engine
4. **Decision Engine** — Weighted fusion, threshold routing, auth override
5. **Dashboard** — FastAPI + Jinja2, quarantine review, metrics, feedback loop
6. **Domain Monitor** — dnstwist-based lookalike domain detection

## Stack

- Python 3.11, FastAPI, SQLAlchemy, XGBoost, scikit-learn
- Redis (queue), PostgreSQL (storage), SpamAssassin (rule scoring)
- Docker Compose (orchestration), Prometheus (monitoring)
