# LTI Anti-Phishing System — Dokumentasi

## Daftar Isi
1. [Cara Email Masuk ke Sistem (Email Ingestion)](#1-cara-email-masuk-ke-sistem-email-ingestion)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Dashboard Guide](#3-dashboard-guide)
4. [Alur Klasifikasi](#4-alur-klasifikasi)
5. [Integrasi dengan Google / Office 365](#5-integrasi-dengan-google--office-365)

---

## 1. Cara Email Masuk ke Sistem (Email Ingestion)

Sistem kami **tidak aktif menarik (pull) email dari penyedia email**. Kami menggunakan pendekatan **push-based** — email dikirimkan ke sistem kami, bukan kami yang mengambil.

### Opsi A: SMTP Forwarding (Rekomendasi)

Konfigurasikan server email klien (Google Workspace, Microsoft 365, atau mail server sendiri) untuk **meneruskan (forward)** email ke sistem kami:

```
Email masuk ke klien → Forward ke SMTP server kami → Diproses
```

Cara setting di penyedia populer:

| Penyedia | Cara |
|---|---|
| **Google Workspace** | Seting → Forwarding → Add forwarding address → `smtp://mail.lodaya.id:25` |
| **Microsoft 365** | Admin → Mail flow → Connector → Forward to `mail.lodaya.id` |
| **cPanel / DirectAdmin** | Forwarders → Add forwarder → `alamat@lodaya.id` |

Sistem kami menerima email via **Mailpit** pada port **1025 (SMTP)**. Setiap email yang masuk langsung di-enqueue ke Redis pipeline untuk diproses.

### Opsi B: IMAP Polling (Untuk Testing / Skala Kecil)

Sistem dapat polling mailbox IMAP secara periodik:

```
Kami jadwalkan fetch tiap 30 detik → IMAP ke Gmail/Outlook → Download email baru → Enqueue
```

Ini sudah ada implementasinya di `fetcher/` tetapi untuk produksi disarankan Opsi A karena lebih real-time dan tidak bergantung pada credential IMAP.

### Opsi C: REST API (Manual / Integrasi Kustom)

Kirim email langsung ke endpoint API kami:

```http
POST https://api.lodaya.id/ingest
Content-Type: application/json
X-API-Key: your-api-key

{
  "raw_email": "From: ...\r\nSubject: ...\r\n\r\nBody...",
  "received_at": "2026-06-25T08:00:00Z"
}
```

Response:
```json
{
  "email_id": "abc123def456",
  "status": "queued",
  "queue_position": 42
}
```

### Ringkasan Perbandingan

| Metode | Latency | Kompleksitas | Cocok Untuk |
|---|---|---|---|
| **SMTP Forwarding** | Real-time (<1s) | Rendah | Produksi |
| **IMAP Polling** | ~30s delay | Sedang | Testing / skala kecil |
| **REST API** | Real-time | Rendah | Integrasi kustom |
| **Gmail API Push** | Real-time | Sedang | Google Workspace |
| **Microsoft Graph API** | Real-time | Sedang | Office 365 |

---

## 2. Arsitektur Sistem

```
                     ┌──────────────────┐
                     │   EMAIL SUMBER   │
                     │ (Gmail / Outlook │
                     │  / Mail Server)  │
                     └────────┬─────────┘
                              │ SMTP / API / IMAP
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                          │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │  Mailpit │  │  REST API    │  │  IMAP Fetcher         │ │
│  │ (SMTP)   │  │  /ingest     │  │  (periodik)           │ │
│  └────┬─────┘  └──────┬───────┘  └───────────┬───────────┘ │
│       └───────────────┼──────────────────────┘             │
│                       ▼                                    │
│            Redis Queue: email_pipeline                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    WORKER PIPELINE                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ SpamAssassin │  │ ML Classifier    │  │   Anomaly    │  │
│  │ Rule-based   │  │ XGBoost + TF-IDF │  │  Detection   │  │
│  │ Skor 0-20+   │  │ Prob 0.0-1.0     │  │ IForest+OCSVM│  │
│  └──────┬───────┘  └────────┬─────────┘  └──────┬───────┘  │
│         └───────────────────┼────────────────────┘          │
│                             ▼                               │
│                  Decision Engine (3-way fusion)              │
│                     ┌───────────────┐                       │
│                     │  FUSION SCORE │                       │
│                     │  ML × 0.50    │                       │
│                     │  SA × 0.25    │                       │
│                     │  Anomali × 0.25                       │
│                     └───────┬───────┘                       │
│                             │                               │
│              ┌──────────────┼──────────────┐                │
│              ▼              ▼              ▼                │
│          CLEAN            WARN        QUARANTINE            │
│        (Terusan)    (Header + Terusan)  (Karantina)         │
│                                                             │
│  Database ──► quarantine_emails (WARN & QUARANTINE)         │
│  Redis Pub/Sub ──► WebSocket broadcast ke Dashboard         │
│  Alert Manager ──► Slack / Telegram / Email (jika QUAR)    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD LAYER                           │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Karantina   │  │  Detail Email    │  │  Panel Metrik│  │
│  │  Tabel       │  │  SHAP Chart + XAI│  │  Grafik +    │  │
│  │  + Aksi      │  │  + Routing Info  │  │  Statistik   │  │
│  └──────────────┘  └──────────────────┘  └──────────────┘  │
│                                                             │
│  WebSocket ──► Live notification (toast)                    │
│  Auth ──► JWT + RBAC (admin / analyst / viewer)            │
│  Prometheus ──► Metrics endpoint /metrics                   │
└─────────────────────────────────────────────────────────────┘
```

### Komponen Utama

| Komponen | Port | Bahasa/Framework | Fungsi |
|---|---|---|---|
| **Mailpit** | 1025 (SMTP), 8025 (UI) | Go | SMTP server testing |
| **Redis** | 6379 | C | Queue + Pub/Sub broker |
| **Classifier API** | 8006 | Python / FastAPI | ML inference + XAI |
| **Worker** | — | Python / asyncio | Pipeline processing |
| **Dashboard** | 8082 | Python / FastAPI + Jinja2 | Web UI |
| **Database** | — | SQLite / PostgreSQL | Data storage |
| **SpamAssassin** | 783 | Perl | Rule-based scoring |

### 3-Layer Detection Architecture

```
Layer 1 — Supervised (XGBoost + TF-IDF)
  - Deteksi spam/phishing known patterns
  - 28 structured features + 50k TF-IDF vocabulary
  - Akurasi: 100% (pada testing 105k dataset)

Layer 2 — Unsupervised (Isolation Forest + One-CLass SVM)
  - Deteksi zero-day / unknown threats
  - Hanya dilatih dengan email bersih
  - Menangkap anomali yang tidak pernah dilihat sebelumnya

Layer 3 — Rule-based (SpamAssassin)
  - Pattern matching klasik
  - Skor berdasarkan rules seperti URIBL, DKIM, dll
```

---

## 3. Dashboard Guide

Dashboard tersedia di **http://localhost:8082**.

### Login

| Username | Password | Role |
|---|---|---|
| `admin` | `changeme` | Admin (full access) |
| `analyst` | `changeme` | Analis (release & confirm) |
| `viewer` | `changeme` | Viewer (read-only) |

### Halaman — Karantina (Quarantine Table)

**Path:** `/`

Menampilkan semua email yang masuk dengan label selain CLEAN.

**Fitur:**
- **Stats bar** (4 kartu): Total diproses, Dikarantina, Peringatan, False Positives
- **Tabel email**: Subjek (klik untuk detail), Label (badge warna), Deteksi (Dual/Single), Skor fused, Skor anomali, Status, Waktu, Aksi
- **Warna baris**: Merah = QUARANTINE, Kuning = WARN, Hijau = CLEAN
- **Aksi**: Lepaskan (release ke inbox) / Spam (konfirmasi spam) / False Positive
- **Preview**: Klik "Preview" untuk lihat cuplikan inline

### Halaman — Detail Email

**Path:** `/email/{email_id}`

Informasi lengkap satu email:

- **Kartu metadata**: Email ID, subjek, pengirim, label, skor akhir, SA score, ML prob, anomaly score, model version, status, waktu, alasan routing
- **SHAP Force Plot**: Horizontal bar chart — fitur apa yang paling berkontribusi ke keputusan (merah = spam, hijau = ham)
- **XAI Explanations**: Penjelasan bahasa Indonesia — e.g. "Probabilitas spam tinggi (87%), SPF tidak lulus, Domain mencurigakan"
- **Detail teknis**: Tabel key-value semua komponen deteksi
- **Action bar**: Lepaskan ke Inbox, Konfirmasi Spam, Laporkan False Positive (dengan catatan)

### Halaman — Panel Metrik

**Path:** `/metrics-panel`

Visualisasi data agregat:

- **Stats bar**: Total, Bersih, Dikarantina, Peringatan, False Positives
- **Distribusi Label**: Bar horizontal % Clean / WARN / QUARANTINE
- **Tren Harian 14 Hari**: Bar chart per hari (merah = karantina, hijau = bersih/warn)
- **Top 10 Pengirim Terblokir**: Siapa yang paling banyak mengirim email berbahaya

### WebSocket Live Feed

Ketika login, dashboard otomatis:
1. Connect WebSocket ke `/ws`
2. Mendengarkan event `email:processed`
3. Menampilkan toast notification untuk setiap email baru yang diproses
4. Halaman akan otomatis ter-update

### Autentikasi & RBAC

| Role | Lihat Data | Lepaskan | Konfirmasi Spam | False Positive Report |
|---|---|---|---|---|
| admin | ✅ | ✅ | ✅ | ✅ |
| analyst | ✅ | ✅ | ✅ | ✅ |
| viewer | ✅ | ❌ | ❌ | ❌ |

### Dark Mode

Toggle ☀️/🌙 di pojok kanan navbar. Persisten via cookie.

---

## 4. Alur Klasifikasi

### Step-by-step untuk 1 email

```
1. Email masuk (via Mailpit / API / IMAP)
   ↓
2. Dienqueue ke Redis "email_pipeline" (list)
   ↓
3. Worker BLPOP dari queue (timeout 5 detik)
   ↓
4. Parallel scoring:
   ├── SpamAssassin: socket ke port 783 → skor raw (0-20+)
   └── ML Classifier: HTTP POST /predict-dual → ml_prob + anomaly_score + XAI
   ↓
5. Decision Engine:
   ├── Normalisasi SA ke [0,1]
   ├── Weighted average: ml×0.50 + sa×0.25 + anomaly×0.25
   ├── Hard override jika salah satu skor sangat tinggi
   └── Label routing: CLEAN / WARN / QUARANTINE
   ↓
6. Simpan ke DB (jika WARN atau QUARANTINE)
   ↓
7. Broadcast via Redis Pub/Sub → WebSocket → Dashboard
   ↓
8. Alert (jika QUARANTINE):
   └── Slack / Telegram / Email (konfigurabel)
```

### Thresholds

| Label | Fused Score | Aksi |
|---|---|---|
| **CLEAN** | < 0.30 | Teruskan ke inbox, tidak disimpan |
| **WARN** | 0.30 – 0.70 | Teruskan + inject header `X-Spam-Reason` |
| **QUARANTINE** | ≥ 0.70 | Tahan di karantina, kirim alert |

### Fitur yang Digunakan ML

**28 fitur terstruktur:**
- URL analysis (num_urls, has_url_shortener, lookalike domain, dll)
- Attachment analysis (executable, jumlah)
- HTML analysis (text ratio, images, forms, javascript)
- Email authentication (SPF, DKIM, DMARC)
- Sender analysis (display name mismatch, bulk sender)
- Urgency detection (urgency_score, urgency_level)
- Business context (BEC score, CEO impersonation, transfer request, sender reputation)

**TF-IDF text:** 50,000 kata dari subject + body

---

## 5. Integrasi dengan Google / Office 365

### Google Workspace (Gmail)

Ada 2 cara:

#### A. SMTP Forwarding (Mudah)

1. Buka **Google Admin Console** → Apps → Gmail → Advanced settings
2. Add forwarding address → `smtp://mail.lodaya.id:25`
3. Atau setiap user bisa set forwarding di Gmail Settings → Forwarding

#### B. Google Cloud Pub/Sub API (Real-time, Lebih Complex)

Menggunakan **Gmail API** dengan push notification:

```
1. Setup Google Cloud Project + enable Gmail API
2. Buat service account dengan domain-wide delegation
3. Watch mailbox: POST https://gmail.googleapis.com/gmail/v1/users/me/watch
4. Google kirim POST ke webhook kita saat ada email baru
5. Webhook trigger fetch email via Gmail API → masuk pipeline
```

Implementasi webhook handler:

```python
@app.post("/webhook/gmail")
async def gmail_webhook(notification: dict):
    email_data = await gmail_service.users().messages().get(
        userId="me", id=notification["messageId"]
    ).execute()
    raw_email = base64.urlsafe_b64decode(email_data["raw"])
    await queue_pusher.push(raw_email)
    return {"status": "ok"}
```

### Microsoft 365 (Outlook)

#### A. Mail Flow Connector (Rekomendasi)

1. **Microsoft 365 Admin Center** → Exchange Admin → Mail flow
2. Create new connector → "Your organization's email server"
3. Set destination to `mail.lodaya.id:25`
4. Pilih "All accepted domains"

#### B. Microsoft Graph API

```
1. Register app di Azure AD
2. Beri permission Mail.Read
3. Setup webhook: POST /v1.0/subscriptions
4. Microsoft kirim notifikasi saat email baru
```

### Implementasi yang Sudah Ada di Sistem

Kode untuk IMAP fetching sudah ada di folder `worker/` tetapi belum aktif secara default. Untuk mengaktifkan:

```bash
# Set environment variable penyedia email
export IMAP_HOST="imap.gmail.com"
export IMAP_USER="monitor@lodaya.id"
export IMAP_PASS="app-password"

# Jalankan fetcher (jika ada)
python -m worker.fetcher
```

> **Catatan**: Untuk Gmail, Anda perlu **App Password** (jika 2FA aktif) atau **OAuth 2.0** untuk kredensial IMAP.

---

## Referensi Cepat

| Perintah | Keterangan |
|---|---|
| `http://localhost:8082` | Dashboard UI |
| `http://localhost:8006/docs` | Swagger API documentation |
| `http://localhost:8006/health` | Health check API |
| `redis-cli MONITOR` | Lihat semua aktivitas Redis |
| `sqlite3 lti_antiphishing.db` | Query database langsung |

---
*LTI Anti-Phishing System v2.0 — Dual-Layer Detection (Supervised + Unsupervised)*
