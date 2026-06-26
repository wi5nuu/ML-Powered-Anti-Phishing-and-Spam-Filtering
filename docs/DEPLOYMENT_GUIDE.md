# Panduan Deployment — LTI Anti-Phishing System

**Versi:** 3.0.0 | **Target:** Production (On-Premise / Cloud VM)

---

## Daftar Isi

1. [Prerequisites](#1-prerequisites)
2. [Arsitektur Production](#2-arsitektur-production)
3. [Persiapan Server](#3-persiapan-server)
4. [Setup Environment Variables](#4-setup-environment-variables)
5. [Build & Deploy dengan Docker](#5-build--deploy-dengan-docker)
6. [Setup Nginx Reverse Proxy](#6-setup-nginx-reverse-proxy)
7. [Training Model ML](#7-training-model-ml)
8. [Setup IMAP / Email Ingestion](#8-setup-imap--email-ingestion)
9. [Verifikasi Deployment](#9-verifikasi-deployment)
10. [Monitoring & Alerting](#10-monitoring--alerting)
11. [Backup & Recovery](#11-backup--recovery)
12. [Operasional Harian](#12-operasional-harian)

---

## 1. Prerequisites

### Hardware Minimum (Production LTI — 25 users)

| Komponen | Minimum | Recommended |
|---|---|---|
| CPU | 4 vCPU | 8 vCPU |
| RAM | 8 GB | 16 GB |
| Storage | 50 GB SSD | 100 GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Software

| Software | Versi | Keterangan |
|---|---|---|
| Ubuntu | 22.04 LTS | OS production |
| Docker | 24.x | Container engine |
| Docker Compose | v2.x | Orchestration |
| Python | 3.11+ | ML training & scripts |
| Nginx | 1.24+ | Reverse proxy + SSL |
| Certbot | Latest | SSL/TLS certificates |

---

## 2. Arsitektur Production

```
Internet → [Nginx + SSL] → [FastAPI Dashboard :8081]
                         → [Classifier API :8001]
                         
[IMAP/SMTP Server] → [Ingestion Worker] → [Redis Queue :6379]
                                             ↓
                                    [Pipeline Worker]
                                             ↓
                                    [PostgreSQL :5432]
                                             ↓
                                    [SpamAssassin :783]

[Prometheus :9090] ← [Grafana :3000] ← metrics
```

---

## 3. Persiapan Server

### 3.1 Install Dependencies (Ubuntu 22.04)

```bash
# Update sistem
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-v2 -y

# Install Python 3.11
sudo apt install python3.11 python3.11-pip python3.11-venv -y

# Install Nginx & Certbot
sudo apt install nginx certbot python3-certbot-nginx -y

# Install Git
sudo apt install git -y
```

### 3.2 Clone Repository

```bash
cd /opt
sudo git clone https://github.com/your-org/lti-antiphishing.git
sudo chown -R $USER:$USER lti-antiphishing
cd lti-antiphishing
```

### 3.3 Setup Python Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Setup Environment Variables

```bash
# Salin template
cp .env.example .env

# Edit .env
nano .env
```

### Konfigurasi .env Wajib (Production)

```env
# ── Security (WAJIB DIUBAH) ──────────────────────────────────
DASHBOARD_SECRET_KEY=<generate-dengan-openssl-rand-hex-64>
JWT_SECRET_KEY=<generate-berbeda-dari-dashboard-secret>

# ── Passwords (WAJIB DIUBAH) ────────────────────────────────
SUPERADMIN_PASSWORD=<password-kuat-minimal-16-karakter>
ADMIN_PASSWORD=<password-kuat-minimal-16-karakter>
REVIEWER_PASSWORD=<password-kuat-minimal-16-karakter>

# ── Database ─────────────────────────────────────────────────
DATABASE_URL=postgresql://ltiuser:<password>@postgres:5432/lti_antiphishing
POSTGRES_USER=ltiuser
POSTGRES_PASSWORD=<db-password>
POSTGRES_DB=lti_antiphishing

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── Classifier ───────────────────────────────────────────────
CLASSIFIER_URL=http://classifier:8001

# ── IMAP (Email Ingestion) ───────────────────────────────────
IMAP_HOST=imap.lodaya.id
IMAP_PORT=993
IMAP_USER=security-scan@lodaya.id
IMAP_PASSWORD=<email-password>
POLL_INTERVAL=30

# ── Domain Protection ────────────────────────────────────────
PROTECTED_DOMAINS=lodaya.id,lodayatech.id,lodaya.co.id

# ── Notification ─────────────────────────────────────────────
ADMIN_ALERT_EMAIL=it-security@lodaya.id

# ── Environment ──────────────────────────────────────────────
ENV=production
ALLOWED_HOSTS=dashboard.lodaya.id,localhost
CORS_ORIGINS=https://dashboard.lodaya.id
```

**Generate secret keys:**
```bash
openssl rand -hex 64  # untuk DASHBOARD_SECRET_KEY
openssl rand -hex 64  # untuk JWT_SECRET_KEY
```

---

## 5. Build & Deploy dengan Docker

### 5.1 Build Images

```bash
docker compose build
```

### 5.2 Start Services

```bash
# Start semua services (background)
docker compose up -d

# Cek status
docker compose ps
```

**Expected output:**
```
NAME                    STATUS    PORTS
lti-fastapi             running   0.0.0.0:8081->8081/tcp
lti-classifier          running   0.0.0.0:8001->8001/tcp
lti-worker              running
lti-redis               running   0.0.0.0:6379->6379/tcp
lti-postgres            running   0.0.0.0:5432->5432/tcp
lti-spamassassin        running   0.0.0.0:783->783/tcp
```

### 5.3 Inisialisasi Database

```bash
# Database otomatis diinisialisasi saat FastAPI startup
# Cek log untuk konfirmasi:
docker compose logs fastapi | grep "Super admin"
```

---

## 6. Setup Nginx Reverse Proxy

### 6.1 Konfigurasi Nginx

```bash
sudo nano /etc/nginx/sites-available/lti-antiphishing
```

```nginx
server {
    listen 80;
    server_name dashboard.lodaya.id;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dashboard.lodaya.id;

    ssl_certificate /etc/letsencrypt/live/dashboard.lodaya.id/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dashboard.lodaya.id/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    # Main application
    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 6.2 Aktifkan & SSL

```bash
sudo ln -s /etc/nginx/sites-available/lti-antiphishing /etc/nginx/sites-enabled/
sudo certbot --nginx -d dashboard.lodaya.id
sudo nginx -t && sudo systemctl restart nginx
```

---

## 7. Training Model ML

### 7.1 Supervised Model (XGBoost + TF-IDF)

```bash
source venv/bin/activate

# Training (gunakan dataset berlabel)
python -m classifier.train data/processed/train.csv

# Evaluasi (generate HTML report di docs/evidence/)
python -m classifier.evaluate data/processed/test.csv

# Cek hasil
cat docs/evidence/evaluation_metrics.json
# Buka: docs/evidence/evaluation_report.html
```

### 7.2 Unsupervised Model (Isolation Forest + One-Class SVM)

```bash
# HANYA butuh email bersih — tidak perlu data spam!
python scripts/train_unsupervised.py data/processed/train.csv
```

### 7.3 Verifikasi Model Terload

```bash
curl http://localhost:8001/health
# {"status":"ok","supervised_loaded":true,"unsupervised_loaded":true}
```

---

## 8. Setup IMAP / Email Ingestion

### Opsi A: IMAP Polling (Default)

Sistem secara otomatis polling mailbox IMAP setiap 30 detik (sesuai `POLL_INTERVAL`). Pastikan konfigurasi di `.env`:
```
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=security-scan@lodaya.id
IMAP_PASSWORD=xxxx
```

### Opsi B: SMTP Forward ke Mailpit

Forward semua email ke Mailpit (port 1025):
```bash
# Google Workspace: Admin → Routing → Add route
# Microsoft 365: Admin → Mail flow → Connectors
```

### Opsi C: REST API Injection

```bash
curl -X POST https://api.lodaya.id/ingest \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"raw_email": "From: ...\r\nSubject: ...\r\n\r\nBody"}'
```

---

## 9. Verifikasi Deployment

```bash
# 1. Health check
curl https://dashboard.lodaya.id/api/health

# 2. Login test
curl -X POST https://dashboard.lodaya.id/api/auth/login \
  -d "username=admin&password=AdminPassword123!"

# 3. Test domain checker
python -c "
from analysis.domain_checker import DomainChecker
checker = DomainChecker()
result = checker.check('http://l0daya.id/login')
print(result.is_suspicious, result.attack_type, result.risk_level)
"

# 4. Inject test email
python scripts/push_to_redis.py --test

# 5. Cek WebSocket
wscat -c ws://localhost:8081/ws?token=<jwt>
```

---

## 10. Monitoring & Alerting

### Prometheus + Grafana

```bash
# Grafana tersedia di
http://localhost:3000
# Default: admin / admin (ganti segera!)

# Prometheus
http://localhost:9090
```

Dashboard Grafana tersedia di `monitoring/grafana/dashboards/lti_dashboard.json`.

### Alert Rules

File `monitoring/alerts.yml` berisi alert untuk:
- Quarantine spike (>10 email dalam 5 menit)
- High false positive rate (>10%)
- Service down
- Redis queue > 100 items

---

## 11. Backup & Recovery

### Backup Database

```bash
# Manual backup
docker exec lti-antiphishing-postgres-1 \
  pg_dump -U ltiuser lti_antiphishing > backup_$(date +%Y%m%d).sql

# Scheduled backup (crontab)
0 2 * * * docker exec lti-antiphishing-postgres-1 pg_dump -U ltiuser lti_antiphishing > /backup/lti_$(date +\%Y\%m\%d).sql
```

### Backup Model Files

```bash
tar -czf models_backup_$(date +%Y%m%d).tar.gz classifier/models/
```

### Recovery

```bash
# Restore database
docker exec -i lti-antiphishing-postgres-1 \
  psql -U ltiuser lti_antiphishing < backup_20260622.sql

# Restart services after recovery
docker compose restart
```

---

## 12. Operasional Harian

### Checklist Harian (IT Security)

```bash
# 1. Cek health semua service
curl http://localhost:8081/api/health

# 2. Lihat quarantine baru
curl http://localhost:8081/api/stats

# 3. Cek Redis queue
python scripts/check_queue.py

# 4. Monitor logs
docker compose logs --tail=100 worker

# 5. Cek alert Grafana
http://localhost:3000/alerting
```

### Retrain Model (Setiap Bulan)

```bash
# 1. Export false positive dataset
curl http://localhost:8081/api/feedback-export > new_fp_data.json

# 2. Tambah ke dataset training
python scripts/add_casual_ham.py

# 3. Retrain
python -m classifier.train data/processed/train.csv

# 4. Evaluate
python -m classifier.evaluate data/processed/test.csv

# 5. Update model di production
docker compose restart classifier worker
```

---

*Panduan ini dibuat untuk Final Project President University — Section 5.4*  
*© 2026 Lodaya Technologies Indonesia. Internal Use Only.*
