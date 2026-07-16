<!-- markdownlint-disable MD033 -->
<div align="center">
  <h1>🛡️ CogniMail</h1>
  <p><strong>ML-Powered Anti-Phishing & Spam Filtering System</strong></p>
  <p><em>Enterprise Edition — Dual-Layer AI Protection with Anomaly Detection</em></p>
</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Role-Based Access Control](#role-based-access-control)
- [ML Pipeline](#ml-pipeline)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Future-Proofing](#future-proofing)

---

## 🌟 Overview

CogniMail adalah **enterprise-grade** ML-powered anti-phishing & spam filtering dengan **dual-layer AI**:

| Layer | Type | Technology | Purpose |
|-------|------|-----------|---------|
| **Layer 1** | Supervised | XGBoost + TF-IDF + SHAP | Classify known threats |
| **Layer 2** | Unsupervised | Isolation Forest + OCSVM | Detect **unknown/zero-day** threats |

### Why Dual-Layer?

Email threats evolve constantly. While supervised models catch known patterns, **unsupervised anomaly detection catches what you haven't seen before** — zero-day attacks, novel phishing techniques, and emerging scam patterns.

---

## 🏗️ Architecture

```
Dashboard (FastAPI)  ────┬────  Worker (Pipeline)
       │                  │           │
       │                  │     Classifier (ML)
       │                  │           │
    Redis (Queue)    Database (SQLite/PostgreSQL)
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI + Python 3.11+ | High-performance async API |
| **ML Models** | XGBoost, scikit-learn | Spam/phishing classification |
| **Anomaly Detection** | Isolation Forest, One-Class SVM | Zero-day threat detection |
| **XAI** | SHAP (TreeExplainer) | Model explainability |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Data persistence |
| **Cache/Queue** | Redis | Message queue & pub/sub |
| **Auth** | JWT + bcrypt + OAuth2 | Authentication & RBAC |

---

## ✨ Features

- ✅ **Dual-layer ML detection** — Supervised + Unsupervised
- ✅ **Zero-day threat detection** — Catches never-before-seen attacks
- ✅ **SHAP explainability** — Know WHY an email was flagged
- ✅ **SpamAssassin integration** — Traditional spam scoring
- ✅ **DKIM/SPF/DMARC verification** — Email authentication checks
- ✅ **3-tier RBAC** — Superadmin, Admin, User
- ✅ **Organization isolation** — Admin sees only their org
- ✅ **Audit logging** — Every action is tracked
- ✅ **Real-time WebSocket feed** — Live email processing
- ✅ **Continuous learning** — Models improve over time
- ✅ **Auto-retrain scheduler** — Periodic model updates
- ✅ **Model versioning** — Track model performance

---

## 👑 Role-Based Access Control

### Role Hierarchy

```
SUPERADMIN (full system access)
├── Manage ALL users, mailboxes, organizations
├── View ALL analytics, audit logs, system health
├── Manage global settings and roles
└── Access everything across all organizations

ADMIN (organization-level access)
├── Manage users within their organization
├── Manage mailboxes within their organization
├── View org-level analytics and audit logs
└── CANNOT access other organizations

USER (personal access only)
├── Access personal mailbox
├── Report suspicious emails
├── View personal quarantine
└── Edit own profile
```

### Security Enforcement

- **All admin endpoints** require `Depends(get_current_user)` with role validation

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis (optional, for queue/pubsub)
- SpamAssassin (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/cognimail.git
cd cognimail

# Setup virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your settings

# Run the application
# Terminal 1: Dashboard
uvicorn dashboard.app:app --reload --port 8080

# Terminal 2: Classifier (ML service)
uvicorn classifier.predict:app --reload --port 8001

# Terminal 3: Worker
python -m worker.pipeline_worker
```

### Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Superadmin | `superadmin` | `superadmin123` |
| Admin | `admin` | `changeme` |

> ⚠️ **CHANGE THESE IMMEDIATELY** in production!

---

## ⚙️ Configuration

All configuration via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `production` enables stricter checks |
| `JWT_SECRET` | (random) | **Required in production** |
| `DATABASE_URL` | `sqlite:///./cognimail.db` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `RATE_LIMIT` | `30/minute` | API rate limit |
| `ANOMALY_THRESHOLD` | `0.7` | Anomaly detection sensitivity |
| `AUTO_RETRAIN_INTERVAL_HOURS` | `168` | Model retrain interval (7 days) |

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_rbac.py -v
```

---

## 🐳 Deployment (Docker)

```bash
# Build and start all services
docker-compose up --build

# Production deployment
docker-compose -f docker-compose.yml up -d

# Development with hot-reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

---

## 🔮 Future-Proofing

CogniMail was designed for **long-term evolution** (50+ years):

| Feature | How It's Future-Proof |
|---------|----------------------|
| **New threat types** | Add to `EmailCategory` enum — no code changes needed |
| **New roles** | Add to `UserRole` enum + define permissions |
| **New features** | Add to `STRUCTURED_FEATURES` list — model auto-adapts |
| **New ML models** | Plug into `classifier/predict.py` — extensible architecture |
| **New databases** | SQLAlchemy ORM — swap SQLite for PostgreSQL, MySQL, etc. |
| **New integrations** | Webhook/API endpoints — extensible plugin system |
| **New auth methods** | Modular auth system — add OAuth, SAML, LDAP |

### Continuous Learning

The system automatically improves over time:
1. User feedback (spam/phishing reports) saved as training data
2. Periodic auto-retrain incorporates new patterns
3. Model versioning enables rollback if performance drops
4. Performance metrics tracked across versions

---

<div align="center">
  <p><strong>Built with ❤️ for a safer email ecosystem</strong></p>
</div>

- **Superadmin endpoints** have `_require_superadmin()` guard
- **Organization boundaries** enforced for Admin role
- **Input validation** on all user-management endpoints
- **Audit logging** on all sensitive operations
- **Failed auth attempts** logged with detailed context

---

## 🧠 ML Pipeline

### Dual-Layer Classification Flow

```
1. Raw Email arrives
2. SpamAssassin scoring (traditional)
3. Layer 1: XGBoost (supervised) + SHAP explanation
4. Layer 2: Isolation Forest + OCSVM (unsupervised)
5. Decision Engine: 3-way fusion (SA + ML + Anomaly)
6. Result: DELIVER, WARN, or QUARANTINE
7. Real-time broadcast via WebSocket
8. Save to database with full audit trail
```

### Feature Engineering

The system extracts **31 structured features** plus **TF-IDF text features**:

- **URL Analysis**: count, unique domains, shorteners, lookalike detection, entropy
- **Authentication**: SPF, DKIM, DMARC results
- **Content**: urgency score, HTML/text ratio, images, forms, JavaScript
- **Business Context**: BEC score, CEO impersonation, payment requests
- **Sender Reputation**: trusted domains, suspicious TLDs, display name mismatch
