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

# Train model (after dataset is ready)
python -m classifier.train data/processed/train.csv

# Run tests
pytest tests/ -v --cov=.
```

## Services

| Service | Port | Description |
|---|---|---|
| Mailpit | 8025 | Email lab UI |
| Mailpit SMTP | 1025 | SMTP untuk kirim email test |
| Mailpit API | 8025 | REST API untuk fetcher |
| Classifier API | 8001 | ML inference |
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

```bash
python -m classifier.train data/processed/train.csv
python -m classifier.evaluate data/processed/test.csv
```

Model terbaru otomatis dipakai oleh classifier service (symlink `latest`).

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
