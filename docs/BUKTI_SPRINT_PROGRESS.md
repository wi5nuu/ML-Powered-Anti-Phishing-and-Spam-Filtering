# Bukti Progress Sprint — LTI Anti-Phishing

> **File ini di-generate otomatis dari state repository saat ini.**
> Jalankan ulang: `python scripts/generate_sprint_evidence.py`

| Field | Nilai |
|-------|-------|
| **Generated (UTC)** | `2026-06-28T16:55:37.350877+00:00` |
| **Git Commit** | `94fe1e9bfd528991a5a5ee7c752a1c2f20f1483f` |
| **Branch** | `master` |
| **Total Commits** | 22 |
| **Last Commit** | docs: add workflow, sequence, and class diagrams to README |

---

## Ringkasan Sprint

- **Completed Tasks:** 39 of 40+ planned
- **Sprint Velocity:** High throughput across ML, infra, dan security

---

## Milestone (Verified Live)

### Dual-Layer ML Training — DONE

| Metrik | Nilai | Sumber |
|--------|-------|--------|
| ROC-AUC (Test Set, holdout 337) | **0.9938** | docs/ML_MODEL_REPORT.md |
| ROC-AUC (Latest 105K training run) | **0.999986541921889** | classifier\models\metadata__latest_20260626_114719.json |
| Isolation Forest | Yes | classifier/models/ |
| One-Class SVM | Yes | classifier/models/ |

**Model artifact checksums (SHA-256):**

- `xgb_model_latest.joblib` — `044a5ea8daf2273a…` (894,591 bytes)
- `tfidf_latest.joblib` — `b94ce1e061748120…` (1,993,691 bytes)
- `scaler_latest.joblib` — `5db8bcb65f6f7a0a…` (1,687 bytes)
- `isolation_forest_latest.joblib` — `78370364c74ee2be…` (3,816,825 bytes)
- `one_class_svm_latest.joblib` — `86973ef53f70e757…` (14,799 bytes)
- `unsupervised_metadata_from_ham.json` — `cf640c98044a1a2e…` (699 bytes)

### Dashboard + Quarantine UI — DONE

- Backend: **FastAPI** (`dashboard\app.py`)
- Frontend: **React 18 + Vite SPA** (16 pages)
- Catatan: Bukan Jinja2 — UI menggunakan React SPA (dashboard/frontend/)

### Docker Compose — DONE (11 services)

Services: `redis`, `spamassassin`, `mailpit`, `postgres`, `classifier`, `worker`, `dashboard`, `prometheus`, `grafana`, `caddy`, `node_exporter`

### Prometheus Monitoring — DONE

- prometheus.yml: True
- alerts.yml: True
- Grafana dashboard: True

### CI/CD Pipeline — DONE (GitHub Actions)

- Workflow: `.github\workflows\ci.yml`
- Jobs: push, pull_request, test, lint, build, deploy

### Tests — DONE (29 passed, 0 failed)

| Modul | Coverage |
|-------|----------|
| decision_engine/fusion.py | **100%** |
| classifier/features.py | **95%** |
| Core modules range | 93% – 100% |

> Coverage 96–100% berlaku untuk modul inti yang di-test (fusion, features, router).
> Total codebase coverage lebih rendah karena worker/dashboard tidak di-unit-test.

### SHAP Explainability — DONE

- Implementasi: `classifier/predict.py — shap.TreeExplainer`
- Referensi SHAP di predict.py: 17 baris

### Merged Dataset (105K target) — COMPLETE

| Metrik | Nilai |
|--------|-------|
| Target | 105,000 |
| .eml files on disk | **105,000** |
| metadata.csv rows | **105,000** |
| Progress | **100.0%** |

---

## Task Breakdown (Verifiable)

**Completed:** 39 | **In Progress:** 1 | **Pending:** 0

### Completed

- [T01] Structured feature engineering (28 features) (`classifier\features.py`)
- [T02] XGBoost supervised training pipeline (`classifier\train.py`)
- [T03] Supervised model artifacts deployed (`classifier\models\xgb_model_latest.joblib`)
- [T04] Isolation Forest anomaly detector (`classifier\models\isolation_forest_latest.joblib`)
- [T05] One-Class SVM anomaly detector (`classifier\models\one_class_svm_latest.joblib`)
- [T06] Dual-layer inference API (/predict-dual) (`classifier\predict.py`)
- [T07] Decision engine 3-way fusion (`decision_engine\fusion.py`)
- [T08] Email routing (CLEAN/WARN/QUARANTINE) (`decision_engine\router.py`)
- [T09] XAI explanation builder (`decision_engine\xai.py`)
- [T10] SHAP TreeExplainer integration (`classifier\predict.py`)
- [T11] Pipeline worker (Redis consumer) (`worker\pipeline_worker.py`)
- [T12] SMTP receiver (port 25 ingress) (`worker\smtp_receiver.py`)
- [T13] Email forwarder to real inbox (`worker\email_forwarder.py`)
- [T14] Multi-channel alerting (`worker\notifier.py`)
- [T15] Domain heuristics checker (`analysis\domain_checker.py`)
- [T16] Dashboard FastAPI backend (`dashboard\app.py`)
- [T17] Dashboard Quarantine UI (React SPA) (`dashboard\frontend\src\pages\InboxPage.jsx`)
- [T18] JWT auth + RBAC (`dashboard\auth.py`)
- [T19] WebSocket live feed (`dashboard\frontend\src\hooks\useWebSocket.js`)
- [T20] SQLAlchemy database models (`database\models.py`)
- [T21] Docker Compose stack (`docker-compose.yml`)
- [T22] Prometheus monitoring config (`monitoring\prometheus.yml`)
- [T23] Grafana dashboards (`monitoring\grafana\dashboards\lti_dashboard.json`)
- [T24] CI/CD GitHub Actions (`.github\workflows\ci.yml`)
- [T25] Unit test suite (`tests`)
- [T26] Architecture documentation + diagrams (`README.md`)
- [T27] Merged dataset 105K EML files (`data\dataset_merged`) — 105000 .eml files
- [T28] Dataset metadata.csv index (`data\dataset_merged\metadata.csv`) — 105000 metadata rows
- [T29] Feature extraction at 105K scale (`data\processed\train_100k.csv`) — train_100k.csv exists
- [T30] Production deployment guide (`docs\DEPLOYMENT_GUIDE.md`)
- [T31] ML model evaluation report (`docs\ML_MODEL_REPORT.md`)
- [T32] Load testing (Locust) (`tests\locustfile.py`)
- [T33] Drift monitoring script (`scripts\drift_monitor.py`)
- [T34] E2E pipeline test (`scripts\e2e_test.py`)
- [T35] Nginx/Caddy reverse proxy (`monitoring\Caddyfile`)
- [T36] SpamAssassin integration (`worker\pipeline_worker.py`)
- [T37] Feedback loop API (`database\models.py`)
- [T38] Audit trail logging (`database\models.py`)
- [T39] Automated retrain script (`scripts\retrain_now.py`)

### In Progress

- [T40] Production SSH deploy job (CI) (`.github\workflows\ci.yml`)

---

## Cara Verifikasi Ulang

```bash
python scripts/generate_sprint_evidence.py
python -m pytest tests/ -v
python -m pytest tests/ --cov=decision_engine --cov=classifier/features --cov-report=term-missing
```

*President University — LTI Anti-Phishing — Evidence generated automatically*