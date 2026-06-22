# LTI Anti-Phishing & Spam Filtering

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ML-Powered anti-phishing dan spam filtering system untuk Lodaya Technologies Indonesia (LTI).

## Fitur

- **Hybrid Detection** — Rule-based (SpamAssassin) + ML (TF-IDF + XGBoost)
- **Async Pipeline** — Redis queue-based, non-blocking email processing
- **XAI** — SHAP-based explanation untuk setiap keputusan
- **Admin Dashboard** — Review, release, false positive reporting
- **Domain Monitor** — dnstwist-based lookalike domain detection
- **Bahasa Indonesia Support** — Sastrawi stemmer, urgency word detection
- **MIT Licensed** — Open source, bebas digunakan

## Arsitektur

```
Email Masuk → Ingestion → Redis Queue → SA + ML → Decision Engine → Dashboard
```

## Quick Start

```bash
# 1. Clone & setup
cp .env.example .env
# Edit .env sesuai environment

# 2. Start infrastructure
docker compose up -d redis spamassassin mailpit postgres

# 3. Install dependencies
pip install -r requirements.txt

# 4. Train model
python -m classifier.train data/processed/train.csv

# 5. Start services
docker compose up -d classifier worker dashboard

# 6. Seed test emails
python scripts/seed_test_emails.py

# 7. Open dashboard
# http://localhost:8080
```

## Project Structure

```
lti-antiphishing/
├── ingestion/        # IMAP fetcher, parser, queue pusher
├── classifier/       # Feature extraction, training, inference
├── decision_engine/  # Fusion, XAI, routing
├── worker/           # Pipeline worker (Redis consumer)
├── dashboard/        # Admin dashboard (FastAPI + Jinja2)
├── database/         # SQLAlchemy models
├── scripts/          # Dataset download, training, domain monitor
├── docs/             # Documentation
├── docker/           # Dockerfiles
└── docker-compose.yml
```

## Testing

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

## Lisensi

MIT License — lihat [LICENSE](LICENSE).

## Video Demo

[Link video demo](https://youtu.be/your-video-link)
