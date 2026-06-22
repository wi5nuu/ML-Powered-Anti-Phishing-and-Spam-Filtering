# Admin Manual — LTI Anti-Phishing & Spam Filtering

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Git

## Quick Start

```bash
# Clone
git clone https://github.com/your-org/lti-antiphishing.git
cd lti-antiphishing

# Copy env
cp .env.example .env
# Edit .env sesuai environment

# Start all services
docker compose up -d

# Train supervised model (XGBoost + TF-IDF)
python -m classifier.train data/processed/train.csv

# Train unsupervised model (Isolation Forest + One-Class SVM)
# Hanya butuh email bersih — 0 data spam!
python scripts/train_unsupervised.py data/processed/train.csv

# Run tests
pytest tests/ -v
```

### Dual Detection Architecture

Sistem memiliki **tiga lapisan deteksi** paralel:

| Lapisan | Metode | Endpoint API | Training Data |
|---|---|---|---|
| Layer 1 — Supervised | XGBoost + TF-IDF | `POST /predict` | Dataset berlabel spam/ham |
| Layer 2 — Unsupervised | Isolation Forest + One-Class SVM | `POST /predict-unsupervised` | **HANYA** email bersih (0 spam!) |
| Layer 3 — Rule-Based | SpamAssassin via spamd | Socket langsung ke SA | Rule signatures |

Worker memanggil `POST /predict-dual` yang mengembalikan supervised + unsupervised score.

## Services

| Service | Port | Description |
|---|---|---|
| Mailpit | 8025 | Email lab UI |
| Mailpit SMTP | 1025 | SMTP untuk kirim email test |
| Mailpit API | 8025 | REST API untuk fetcher |
| Classifier API | 8001 | ML inference (dual detection) |
| Dashboard | 8081 | Admin UI (8080 di Docker) |
| Prometheus | 9090 | Metrics |
| Redis | 6379 | Queue |
| PostgreSQL | 5432 | Database |
| SpamAssassin | 783 | Rule scoring |

## Postfix Header Checks

Untuk menginjeksi X-Spam-Reason header di Postfix produksi:

```
# /etc/postfix/header_checks
/^X-Spam-Reason:/ INFO
/^X-Spam-Status:/ INFO
```

## Training Ulang Model

### Supervised (XGBoost)
```bash
python -m classifier.train data/processed/train.csv
python -m classifier.evaluate data/processed/test.csv
```

### Unsupervised (Isolation Forest + One-Class SVM)
```bash
# HANYA butuh clean emails — tidak perlu data spam!
python scripts/train_unsupervised.py data/processed/train.csv
```

Model terbaru otomatis dipakai oleh classifier service (symlink `latest`).

### Cek Status Model
```bash
curl http://localhost:8001/health
# {"status":"ok","supervised_loaded":true,"unsupervised_loaded":true}
```

## Domain Monitor

```bash
# Manual
python scripts/domain_monitor.py

# Cron (setiap 24 jam)
0 2 * * * cd /opt/lti-antiphishing && python scripts/domain_monitor.py
```

## Backup Database

```bash
docker exec lti-antiphishing-postgres-1 pg_dump -U ltiuser lti_antiphishing > backup.sql
```
