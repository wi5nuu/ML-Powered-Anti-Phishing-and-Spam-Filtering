# LTI Anti-Phishing — Panduan Deployment Produksi

## Arsitektur Produksi

```
                    INTERNET
                       │
              DNS MX Record: mail.lodaya.id
                       │
              ┌────────▼────────┐
              │   SMTP Receiver │  port 25
              │  (smtp_receiver)│
              └────────┬────────┘
                       │ Push ke Redis
              ┌────────▼────────┐
              │  Redis Queue    │  email_pipeline
              └────────┬────────┘
                       │ BLPOP
              ┌────────▼────────┐
              │ Pipeline Worker │  scan + klasifikasi
              │                 │
              │  ┌───────────┐  │
              │  │ Classifier│  │  Layer 1: XGBoost (supervised)
              │  │  API :8006│  │  Layer 2: IForest + OCSVM (unsupervised)
              │  └───────────┘  │
              │  ┌───────────┐  │
              │  │SpamAssasin│  │  Layer 3: Rule-based
              │  │  :783     │  │
              │  └───────────┘  │
              └────────┬────────┘
                       │ Hasil klasifikasi
            ┌──────────┼──────────┐
            ▼          ▼          ▼
         CLEAN       WARN    QUARANTINE
            │          │          │
            ▼          ▼          ▼
     Forward ke   Forward +   Simpan di DB
     Gmail/Outlook X-Header   + Dashboard
     (inbox asli)  (inbox)    (tidak diteruskan)
```

## Prasyarat

| Komponen | Spesifikasi |
|---|---|
| **Server** | VPS minimal 2 CPU, 4GB RAM, 40GB SSD |
| **OS** | Ubuntu 22.04 LTS atau Debian 12 |
| **Domain** | `lodaya.id` (atau domain Anda) dengan akses DNS |
| **Email** | Akun Gmail/Outlook untuk forward (app password) |
| **Docker** | Docker Engine 24+ & Docker Compose v2 |

## Instalasi

### 1. Clone & Setup

```bash
git clone https://github.com/your-org/lti-antiphishing.git
cd lti-antiphishing
cp .env.example .env
```

### 2. Konfigurasi Environment

Edit `.env`:

```bash
# ── Database ──
DB_URL=postgresql+asyncpg://lti:password@postgres:5432/lti_antiphishing

# ── Redis ──
REDIS_URL=redis://redis:6379/0

# ── Classifier ──
CLASSIFIER_URL=http://classifier:8001

# ── SMTP Receiver (port 25) ──
SMTP_HOST=0.0.0.0
SMTP_PORT=25
SMTP_DOMAIN=mail.lodaya.id

# ── Email Forwarder (kirim ke inbox asli) ──
FORWARDER_SMTP_HOST=smtp.gmail.com
FORWARDER_SMTP_PORT=587
FORWARDER_SMTP_USER=antiphishing@lodaya.id
FORWARDER_SMTP_PASS=your-app-password  # Gmail App Password
FORWARDER_FROM=antiphishing@lodaya.id

# ── SpamAssassin ──
SPAMASSASSIN_HOST=spamassassin
SPAMASSASSIN_PORT=783

# ── Alert ──
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SMTP_ALERT_HOST=smtp.gmail.com
SMTP_ALERT_USER=...

# ── Dashboard ──
DASHBOARD_SECRET_KEY=generate-a-random-secret-key
ADMIN_PASSWORD=strong-password-here
ALLOWED_HOSTS=localhost,mail.lodaya.id
CORS_ORIGINS=https://mail.lodaya.id
```

### 3. DNS Configuration

Arahkan MX record domain Anda ke server:

```
Record Type  Name                Value                    Priority
────────────  ──────────         ───────────────────────  ────────
A             mail.lodaya.id     103.x.x.x (IP server)    ─
MX            lodaya.id          mail.lodaya.id           10
TXT           lodaya.id          v=spf1 mx ~all           ─
```

### 4. Gmail App Password

Buat App Password untuk akun pengirim:

1. Google Account → Security → 2-Step Verification (aktifkan)
2. App passwords → Pilih "Mail" + "Other" → Generate
3. Copy password (16 karakter) → paste ke `FORWARDER_SMTP_PASS`

### 5. Deploy dengan Docker Compose

```bash
# Production
docker compose -f docker-compose.prod.yml up -d

# Cek status
docker compose ps
```

## Memantau Sistem

| URL | Deskripsi |
|---|---|
| `https://mail.lodaya.id` | Dashboard karantina |
| `https://mail.lodaya.id/help` | Dokumentasi |
| `https://mail.lodaya.id:9090` | Prometheus metrics |
| `https://mail.lodaya.id:3000` | Grafana dashboard |

## Testing End-to-End

Kirim email test ke alamat di domain Anda:

```bash
# Email spam test
swaks --to user@lodaya.id \
      --from attacker@evil.com \
      --subject "URGENT: Your account suspended" \
      --body "Click here to verify: http://phishing.com"

# Email normal test
swaks --to user@lodaya.id \
      --from friend@gmail.com \
      --subject "Meeting tomorrow" \
      --body "Hi, let's discuss project update."
```

Cek dashboard: https://mail.lodaya.id

## Skalabilitas

| Beban | Worker Concurrency | Server |
|---|---|---|
| 1.000 email/hari | 3 | 2 CPU, 4GB |
| 10.000 email/hari | 10 | 4 CPU, 8GB |
| 100.000 email/hari | 25 + Redis Cluster | 8 CPU, 16GB + PostgreSQL |

## Troubleshooting

**Email tidak masuk ke sistem:**
- Cek `docker logs lti-smtp-receiver`
- Verifikasi MX record: `dig mx lodaya.id`
- Test koneksi port 25: `telnet mail.lodaya.id 25`

**Email tidak diteruskan ke Gmail:**
- Cek `docker logs lti-worker`
- Verifikasi App Password masih valid
- Cek log SMTP: `docker logs lti-worker | grep "Forwarded"`

**Dashboard error:**
- Cek koneksi DB: `docker logs lti-dashboard`
- Restart: `docker compose restart dashboard`
