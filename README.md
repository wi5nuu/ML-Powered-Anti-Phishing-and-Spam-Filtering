# CogniMail — ML-Powered Anti-Phishing & Spam Filtering System

A production-grade email security platform that combines machine learning, SpamAssassin rule-based scoring, and anomaly detection into a unified Fusion Decision Engine to protect against phishing, spam, and malware.

## Key Features

- **Fusion Decision Engine** — weighted combination of ML classifier, SpamAssassin, and anomaly scorer for high-accuracy threat decisions
- **Real-time Pipeline** — emails ingested via SMTP receiver, queued in Redis, processed by async worker, and pushed live via WebSocket
- **ML Classifier** — XGBoost + scikit-learn models with SHAP explainability, bilingual support (EN/ID via Sastrawi)
- **CogniMail Dashboard** — React 19 SPA with JWT-authenticated views for superadmin, admin, and user roles
- **Quarantine Management** — review, release, mark false positive, star, snooze, bulk actions
- **Audit Logging** — full trail of every admin action
- **Monitoring Stack** — Prometheus metrics, Grafana dashboards, Caddy reverse proxy with TLS
- **Google OAuth** — optional SSO login for registered users
- **Webmail / Mailbox** — per-domain mailboxes with compose, reply, and attachment support

## Architecture

```
Internet / MX
      │
      ▼
smtp_receiver  ──► Redis queue ──► pipeline_worker
                                        │
                          ┌─────────────┼──────────────┐
                          ▼             ▼               ▼
                    ML Classifier  SpamAssassin   Anomaly Scorer
                          └─────────────┼──────────────┘
                                        ▼
                              Fusion Decision Engine
                                        │
                                        ▼
                                  PostgreSQL DB
                                        │
                                        ▼
                          Dashboard API (FastAPI) ──► React SPA
                                        │
                                   Redis Pub/Sub ──► WebSocket
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, React Router 7, TanStack Query, Vite 8, Axios, Lucide React |
| Backend API | FastAPI 0.110+, Uvicorn, SQLAlchemy 2, Pydantic v2 |
| ML / NLP | scikit-learn, XGBoost, SHAP, Sastrawi, langdetect, tldextract |
| Database | PostgreSQL 16 (production), SQLAlchemy ORM, Alembic migrations |
| Queue / Cache | Redis 7.2 |
| SMTP Ingestion | aiosmtpd (inbound MX), aiosmtplib (outbound relay) |
| Spam Scoring | SpamAssassin (via Docker) |
| Auth | JWT (PyJWT), bcrypt, RBAC (superadmin / admin / user / mailbox) |
| Monitoring | Prometheus, Grafana, node_exporter, prometheus-fastapi-instrumentator |
| Reverse Proxy | Caddy (auto TLS via Let's Encrypt) |
| Containerization | Docker Compose (profiles: `local`, `production`) |

## Project Structure

```
lti-antiphishing/
├── classifier/          # ML classifier service (FastAPI on :8001)
│   └── models/          # Trained model artifacts (.joblib)
├── dashboard/           # Dashboard backend (FastAPI on :8080/:8081)
│   ├── app.py           # Main FastAPI application
│   ├── auth.py          # JWT auth helpers
│   ├── rbac.py          # Role-based access control
│   ├── admin_routes.py  # Admin API routes
│   ├── database.py      # SQLAlchemy session & schema init
│   ├── run_dev.py       # Local dev launcher
│   └── frontend/        # React SPA (Vite)
│       ├── src/         # React source code
│       └── package.json
├── worker/              # Async pipeline worker
│   ├── pipeline_worker.py   # Main email processing loop
│   ├── smtp_receiver.py     # Inbound SMTP (aiosmtpd)
│   ├── email_forwarder.py   # Outbound relay
│   └── notifier.py          # WebSocket notifier
├── database/            # Shared ORM models
│   └── models.py
├── decision_engine/     # Fusion scoring logic
├── analysis/            # Feature extraction & URL analysis
├── classifier/          # ML model training & inference
├── monitoring/          # Prometheus config, Grafana dashboards, Caddyfile
├── docker/              # Dockerfiles per service
│   ├── Dockerfile.classifier
│   ├── Dockerfile.dashboard
│   └── Dockerfile.worker
├── scripts/             # start / stop helpers (ps1, sh, cmd)
├── data/                # Training datasets
├── tests/               # Test suite
├── docker-compose.yml   # Full stack definition
├── requirements.txt     # Python dependencies
├── seed_data.py         # DB seed script
├── .env.example         # Environment template
└── SETUP.md             # Step-by-step run guide
```

## User Roles

| Role | Access |
|---|---|
| `superadmin` | Full system access, all orgs, user management |
| `admin` | Organization-scoped management, mailbox config |
| `user` | Own mailbox view only |
| `mailbox` | Webmail session (compose, inbox, sent) |

## Default Ports (local profile)

| Service | URL |
|---|---|
| Dashboard | http://localhost:8080 |
| Dashboard API docs | http://localhost:8080/docs |
| Classifier | http://localhost:8001/health |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Mailpit (test SMTP) | http://localhost:8025 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6380 |

## Quick Start

See [SETUP.md](SETUP.md) for complete step-by-step instructions covering:
- Environment configuration
- Running with Docker (recommended)
- Running the backend locally (dev mode)
- Running the frontend dev server
- Accessing and inspecting the database
- Monitoring with Grafana / Prometheus

## API Documentation

Interactive Swagger UI is available at `http://localhost:8080/docs` when the dashboard is running.

## Security Notes

- Never commit `.env` to version control
- Rotate `DASHBOARD_SECRET_KEY` before any public deployment (min 64 hex chars)
- Change all default seed passwords (`SUPERADMIN_PASSWORD`, `ADMIN_PASSWORD`, `USER_PASSWORD`)
- Port 25 must be publicly reachable for inbound MX delivery in production

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE) for details.
