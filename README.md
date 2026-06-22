# LTI Anti-Phishing and Spam Filtering -- President University Final Project

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A dual-layer machine learning-powered anti-phishing and spam filtering system for Lodaya Technologies Indonesia (LTI), a FinTech company handling 5 million daily financial transactions with a 25-person team.

**Team:**
- Wisnu Alfian Nur Ashar
- Muhammad Ilham Maulana
- Muhammad Ahda Briliantama
- Christofer
- Risly

**Supervisor:** Fandi Gunawan, S.T., M.T.I., CISSP, CC, ISO 27001 LI, ISO 42001 LA

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [System Architecture](#system-architecture)
3. [Dual Detection Layers](#dual-detection-layers)
4. [Key Features](#key-features)
5. [Tech Stack](#tech-stack)
6. [Getting Started](#getting-started)
7. [Project Structure](#project-structure)
8. [API Endpoints](#api-endpoints)
9. [Testing](#testing)
10. [Performance](#performance)
11. [License](#license)

---

## Problem Statement

LTI employees -- particularly in administration and customer service -- are non-technical staff who are the primary target of phishing attacks. Before this system, there was no email filtering infrastructure. With 5 million daily financial transactions, a single compromised account could lead to significant fraud losses.

**Key requirements:**
- Automated inbound email ingestion and parsing
- Hybrid detection (rule-based + supervised ML + unsupervised anomaly detection)
- Explainable decisions for non-technical staff
- Admin quarantine dashboard with release/feedback workflow
- Domain inconsistency detection (lookalike domains)
- Zero-day phishing detection without labeled spam data

---

## System Architecture

```
SMTP (port 1025) -> Mailpit (port 8025) -> REST API Fetcher -> Redis Queue
                                                               |
                                    +--------------------------+
                                    |                          |
                            SpamAssassin            Dual-Layer Classifier API
                            (rule-based)             /                    \
                                    +------------> Layer 1: XGBoost      |
                                    |              (supervised, TF-IDF)  |
                                    |              Layer 2: IForest+SVM  |
                                    |              (unsupervised, zero-  |
                                    |               shot anomaly)         |
                                    |                          |          |
                                    +-----------+--------------+----------+
                                                |
                                         Decision Engine
                                     (3-way weighted fusion
                                      ML 50% + SA 25% + Anomaly 25%)
                                                |
                                     +----------+----------+
                                     |          |          |
                                   CLEAN      WARN    QUARANTINE
                                   (inbox)   (+X-Spam-Reason)  (DB)
                                                              |
                                                        Admin Dashboard
                                                       (port 8081)
```

**Pipeline flow:**

1. Email arrives via SMTP to Mailpit (development email server)
2. Ingestion fetcher polls Mailpit REST API every 30 seconds
3. Raw email pushed to Redis queue `email_pipeline`
4. Worker consumes from queue, runs three parallel scoring tasks:
   - SpamAssassin rule-based scoring (via spamd protocol)
   - Supervised ML scoring (XGBoost with TF-IDF + 20 structured features)
   - Unsupervised anomaly scoring (Isolation Forest + One-Class SVM)
5. Decision Engine fuses all three scores into a single fused score
6. Email routed to CLEAN (inbox), WARN (inbox with X-Spam-Reason header), or QUARANTINE (database)
7. Admin reviews quarantined emails via the Dashboard

---

## Dual Detection Layers

### Layer 1 -- Supervised (XGBoost + TF-IDF)

| Item | Detail |
|---|---|
| Model | XGBoost Classifier, 300 trees, max_depth=6, learning_rate=0.05 |
| Text features | TF-IDF vectorizer, 50,000 unigrams + bigrams |
| Structured features | 20 features (urgency, URL analysis, authentication, headers) |
| Training data | 2,243 samples (SpamAssassin corpus + Enron dataset + synthetic) |
| Test ROC-AUC | 0.9938 |
| CV ROC-AUC | 0.9891 |
| Precision / Recall | 0.95 / 0.95 |
| False Positives | 8 of 337 test samples |
| False Negatives | 8 of 337 test samples |

### Layer 2 -- Unsupervised (Isolation Forest + One-Class SVM)

| Item | Detail |
|---|---|
| Model | Isolation Forest (200 trees) + One-Class SVM (RBF kernel) |
| Training data | 1,121 clean emails only (zero spam) |
| Strategy | Learn "normal email pattern" for LTI; flag deviations as anomalous |
| Contamination | 0.05 (expect ~5% anomalies in production) |
| Detection capability | Zero-day phishing, novel social engineering, never-before-seen attack patterns |
| Phishing email anomaly score | 0.706 (threshold > 0.5 = anomalous) |
| Clean email anomaly score | ~0.34 (below threshold, classified as normal) |

### Layer 3 -- Rule-based (SpamAssassin)

Industry-standard rule engine with thousands of spam detection rules. Scores range from -2 to 20+.

### Decision Engine Fusion

```
fused_score = (ml_probability * 0.50) + (sa_normalized * 0.25) + (anomaly_score * 0.25)
```

Hard overrides:
- SA score >= 15 or ML probability >= 0.95 or Anomaly score >= 0.90: immediate QUARANTINE
- SPF + DKIM + DMARC all pass with ML prob < 0.50: reduce fused score by 0.10

Routing thresholds:

| Fused Score | Label | Action |
|---|---|---|
| < 0.30 | CLEAN | Deliver to inbox |
| 0.30 -- 0.70 | WARN | Deliver with X-Spam-Reason header |
| >= 0.70 | QUARANTINE | Isolate in database, admin review |

---

## Key Features

### Explainable AI (XAI)

Every flagged email includes an `X-Spam-Reason` header explaining why it was flagged:

```
X-Spam-Reason: SpamProb=0.97; Urgency-Score:0.60; SPF:FAIL; DKIM:FAIL; URL-Shortener:DETECTED; Top-SHAP:guaranteed
```

Non-technical staff see human-readable explanations on the dashboard:
- "Email contains urgent/demanding language"
- "Link points to a domain similar to lodaya.id"
- "Sender identity verification (SPF) failed"

This passively trains staff to recognize phishing patterns over time, turning the weakest security link into a first line of defense.

### Domain Inconsistency Detection

- Levenshtein distance comparison against protected domain `lodaya.id`
- Detects lookalike domains: `1odaya.id`, `lodaya-secure.xyz`, etc.
- dnstwist integration: 2,448 domain permutations checked automatically

### Bilingual Support (Indonesian + English)

- Urgency word detection in both Bahasa Indonesia and English
- Sastrawi stemmer for Indonesian text normalization
- Dashboard UI in Indonesian with English technical terms

### Admin Dashboard

- Quarantine list sorted by fused score (highest risk first)
- Email detail view with all three scores (ML, SA, Anomaly)
- Human-readable XAI explanations
- Actions: release to inbox, confirm as spam, report false positive
- Metrics panel: label distribution, top blocked senders
- Dual Detection badge indicating both supervised + unsupervised layers contributed

### Async Pipeline

- Redis-backed work queue for non-blocking processing
- Parallel scoring: SpamAssassin, supervised ML, and unsupervised anomaly run concurrently
- Worker concurrency configurable via `WORKER_CONCURRENCY` environment variable
- Horizontal scaling: add more worker containers for higher throughput

---

## Tech Stack

| Component | Technology |
|---|---|
| Ingestion | Mailpit REST API |
| ML Framework | XGBoost + scikit-learn (Isolation Forest, One-Class SVM) |
| Text Vectorization | TF-IDF (50,000 features, scikit-learn) |
| Inference API | FastAPI (port 8001) |
| Task Queue | Redis (async, `email_pipeline` queue) |
| Database | SQLite (development) / PostgreSQL (production) |
| Rule Engine | Apache SpamAssassin |
| Dashboard | FastAPI + Jinja2 templates (port 8081) |
| Explainability | SHAP (TreeExplainer) |
| Containerization | Docker Compose |
| Monitoring | Prometheus |
| Domain Analysis | dnstwist, rapidfuzz (Levenshtein), tldextract |
| Language | Python 3.11+, Sastrawi (Indonesian), langdetect |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/wi5nuu/ML-Powered-Anti-Phishing-and-Spam-Filtering.git
cd lti-antiphishing

# Copy environment configuration
cp .env.example .env
# Edit .env to match your environment (database URLs, passwords, etc.)

# Start infrastructure services
docker compose up -d redis spamassassin mailpit postgres

# Install Python dependencies
pip install -r requirements.txt

# Train supervised model
python -m classifier.train data/processed/train.csv

# Train unsupervised anomaly detector (zero spam needed)
python scripts/train_unsupervised.py data/processed/train.csv

# Start application services
docker compose up -d classifier worker dashboard

# Seed test emails for verification
python scripts/seed_test_emails.py

# Open admin dashboard
# http://localhost:8081
```

### Verify Installation

```bash
# Check all services are healthy
curl http://localhost:8001/health

# Expected response:
# {"status":"ok","supervised_loaded":true,"unsupervised_loaded":true}

# Run tests
python -m pytest tests/ -v
# Expected: 23 passed
```

---

## Project Structure

```
lti-antiphishing/
|
+-- ingestion/                  # Email ingestion pipeline
|   +-- fetcher.py              # Mailpit REST API poller
|   +-- parser.py               # Raw email parsing (headers, body, attachments)
|   +-- queue_pusher.py         # Redis queue producer
|
+-- classifier/                 # ML model training and inference
|   +-- features.py             # Feature engineering (20 structured + TF-IDF)
|   +-- train.py                # Supervised XGBoost training pipeline
|   +-- predict.py              # FastAPI inference service (dual-layer)
|   +-- unsupervised.py         # Unsupervised anomaly detection module
|   +-- evaluate.py             # Model evaluation and metrics
|   +-- models/                 # Saved model artifacts
|       +-- xgb_model_latest.joblib
|       +-- tfidf_latest.joblib
|       +-- scaler_latest.joblib
|       +-- isolation_forest_latest.joblib
|       +-- one_class_svm_latest.joblib
|       +-- unsupervised_scaler_latest.joblib
|
+-- decision_engine/            # Routing decisions
|   +-- fusion.py               # 3-way score fusion (ML + SA + Anomaly)
|   +-- router.py               # Routing logic (CLEAN / WARN / QUARANTINE)
|   +-- xai.py                  # X-Spam-Reason header builder
|
+-- worker/                     # Async pipeline worker
|   +-- pipeline_worker.py      # Redis consumer, orchestrates scoring
|
+-- dashboard/                  # Admin web interface
|   +-- app.py                  # FastAPI dashboard (port 8081)
|   +-- templates/              # Jinja2 HTML templates
|   +-- static/                 # CSS styles
|
+-- database/                   # Data layer
|   +-- models.py               # SQLAlchemy models (QuarantineEmail, Feedback)
|   +-- migrations/             # Database migrations
|
+-- scripts/                    # Utility scripts
|   +-- train_real_model.py     # Full supervised training pipeline
|   +-- train_unsupervised.py   # Anomaly detector training
|   +-- seed_test_emails.py     # Generate test emails
|   +-- domain_monitor.py       # dnstwist lookalike domain scanner
|   +-- run_ingestion.py        # Background ingestion runner
|
+-- docs/                       # Documentation
|   +-- architecture.md         # System architecture
|   +-- admin_manual.md         # DevOps guide
|   +-- user_manual.md          # End-user guide
|   +-- presentation.md         # Final project presentation
|
+-- docker/                     # Container definitions
+-- monitoring/                 # Prometheus configuration
+-- screenshots/                # Project evidence
+-- tests/                      # Unit tests (23 tests)
|
+-- docker-compose.yml          # Multi-service orchestration
+-- .env                        # Environment configuration
+-- requirements.txt            # Python dependencies
+-- AI_USAGE.md                 # AI tools disclosure
+-- LICENSE                     # MIT License
```

---

## API Endpoints

### Classifier Service (port 8001)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/predict` | Supervised XGBoost prediction with SHAP explanation |
| POST | `/predict-unsupervised` | Unsupervised anomaly detection (Isolation Forest + One-Class SVM) |
| POST | `/predict-dual` | Both supervised and unsupervised scores in one call |
| GET | `/health` | Service health, model load status |
| GET | `/model-info` | Active model configuration |

### Dashboard Service (port 8081)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Quarantine email list, sorted by fused score |
| GET | `/email/{email_id}` | Email detail with XAI explanation and scores |
| POST | `/email/{email_id}/release` | Release email to inbox |
| POST | `/email/{email_id}/confirm-spam` | Confirm as spam |
| POST | `/email/{email_id}/report-false-positive` | Report false positive (for retraining) |
| GET | `/metrics-panel` | Label distribution, top senders, statistics |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_decision_engine.py -v
python -m pytest tests/test_features.py -v
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_classifier.py -v
```

**Test results: 23 passed, 0 failed**

| Module | Tests | Coverage |
|---|---|---|
| features.py | 7 | 96% |
| fusion.py | 9 | 100% |
| router.py | 2 | 93% |
| parser.py | 4 | 100% |
| classifier | 3 | -- |
| **Total** | **23** | Core modules 96-100% |

---

## Performance

### Throughput

- Single worker processes ~360 emails per hour (SA + ML + Anomaly parallel)
- With WORKER_CONCURRENCY=10: ~3,600 emails per hour
- For LTI's estimated 50-200 daily emails: capacity is 18-72x over-provisioned

### Model Accuracy

| Metric | Supervised (XGBoost) | Unsupervised (IForest) |
|---|---|---|
| ROC-AUC | 0.9938 | N/A (no labels) |
| Precision | 0.95 | 0.95 (estimated on clean data) |
| Recall | 0.95 | Strong on novel attack patterns |
| Training data | 2,243 labeled (50/50 split) | 1,121 clean (zero spam) |

### Dual Detection Benefit

| Scenario | Supervised Alone | With Anomaly Detection |
|---|---|---|
| Known spam pattern | Detects | Detects (same) |
| Zero-day phishing | May miss if text patterns differ | Detects as anomalous behavior |
| Novel social engineering (Indonesian) | Limited by training set | Detects as deviation from normal |
| Legitimate but unusual email | False positive risk | Anomaly score adds context |

---

## License

MIT License -- see [LICENSE](LICENSE).

---

*President University -- Faculty of Computer Science -- June 2026*
