# API Reference — LTI Anti-Phishing Dashboard

**Base URL:** `http://localhost:8081` (development) | `https://api.lodaya.id` (production)  
**API Version:** v3.0.0  
**Authentication:** JWT Cookie (`access_token`) — set via `/api/auth/login`

---

## Authentication

### POST /api/auth/login

Login dan dapatkan JWT token.

**Request Body (form-data):**
```
username=admin&password=AdminPassword123!
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Cookies:**  
Response juga menyetel cookie `access_token` (httpOnly, SameSite=Lax) secara otomatis.

**Rate Limit:** 20 request/menit per IP.

---

### GET /api/auth/me

Cek status autentikasi saat ini.

**Response (200):**
```json
{
  "authenticated": true,
  "user": {
    "username": "admin",
    "role": "security_admin"
  }
}
```

---

### POST /api/auth/logout

Hapus cookie JWT dan logout.

**Response (200):**
```json
{"ok": true}
```

---

## Email Management

### GET /api/emails

Ambil daftar email yang diproses (maks 100 per request).

**Query Parameters:**

| Parameter | Type | Keterangan |
|---|---|---|
| `label` | string | Filter: `QUARANTINE`, `WARN`, `CLEAN` |
| `q` | string | Pencarian berdasarkan subjek atau pengirim |

**Response (200):**
```json
{
  "emails": [
    {
      "email_id": "abc123def456",
      "sender": "phisher@fake-domain.id",
      "subject": "URGENT: Verify your account",
      "label": "QUARANTINE",
      "status": "pending",
      "fused_score": 0.92,
      "ml_probability": 0.97,
      "sa_score": 8.5,
      "anomaly_score": 0.76,
      "received_at": "2026-06-26T10:00:00"
    }
  ],
  "total": 47
}
```

**Authorization:** Semua role. User biasa hanya melihat email yang ditujukan kepada mereka.

---

### GET /api/emails/{email_id}

Ambil detail lengkap satu email.

**Path Parameter:** `email_id` — ID unik email

**Response (200):**
```json
{
  "email_id": "abc123def456",
  "sender": "phisher@fake-domain.id",
  "subject": "URGENT: Verify your account",
  "label": "QUARANTINE",
  "status": "pending",
  "fused_score": 0.92,
  "ml_probability": 0.97,
  "sa_score": 8.5,
  "anomaly_score": 0.76,
  "model_version": "20260622_201332",
  "routing_reason": "ML score 0.97 exceeds quarantine threshold",
  "received_at": "2026-06-26T10:00:00",
  "reasons": [
    {"key": "SpamProb", "value": "0.97"},
    {"key": "Lookalike-Domain", "value": "1"}
  ],
  "human_reasons": [
    "Probabilitas spam dari model supervised AI",
    "Link mengarah ke domain yang mirip lodaya.id"
  ],
  "shap_data": {"click here": 0.289, "guaranteed": 0.445},
  "raw_content": "From: phisher@fake-domain.id\r\n...",
  "recipient_list": "staff@lodaya.id"
}
```

**Notes:** User biasa tidak mendapatkan `ml_probability`, `sa_score`, `anomaly_score`, `reasons`, `human_reasons`, dan `shap_data`.

---

### POST /api/emails/{email_id}/release

Lepaskan email dari karantina ke inbox.

**Authorization:** `mail_reviewer`, `security_admin`, `superadmin`

**Response (200):**
```json
{"ok": true, "status": "released"}
```

---

### POST /api/emails/{email_id}/confirm-spam

Konfirmasi email sebagai spam.

**Authorization:** `mail_reviewer`, `security_admin`, `superadmin`

**Response (200):**
```json
{"ok": true, "status": "confirmed_spam"}
```

---

### POST /api/emails/{email_id}/report-false-positive

Laporkan email sebagai false positive (sistem salah karantina).

**Authorization:** `mail_reviewer`, `security_admin`, `superadmin`

**Request Body (JSON):**
```json
{
  "notes": "Email dari vendor resmi PT Maju Bersama"
}
```

**Response (200):**
```json
{"ok": true, "status": "released"}
```

---

### DELETE /api/emails/{email_id}

Hapus email dari database secara permanen.

**Authorization:** `security_admin`, `superadmin`

**Response (200):**
```json
{"ok": true, "status": "deleted"}
```

---

### GET /api/emails/export-csv

Export daftar email sebagai file CSV.

**Query Parameters:**

| Parameter | Type | Keterangan |
|---|---|---|
| `label` | string | Filter opsional: `QUARANTINE`, `WARN`, `CLEAN` |

**Authorization:** `mail_reviewer`, `security_admin`, `superadmin`

**Response:** File CSV dengan header:
```
email_id, sender, subject, label, status, fused_score, ml_probability, sa_score, anomaly_score, model_version, routing_reason, received_at, created_at
```

---

## Statistics & Metrics

### GET /api/stats

Ambil ringkasan statistik cepat (untuk dashboard header).

**Authorization:** Publik (tidak butuh login)

**Response (200):**
```json
{
  "total": 1243,
  "quarantine": 87,
  "warn": 212,
  "clean": 944,
  "avg_anomaly_score": 0.2341,
  "avg_fused_score": 0.1876
}
```

---

### GET /api/metrics

Ambil data metrik lengkap untuk halaman Metrik.

**Authorization:** `mail_reviewer`, `security_admin`, `superadmin`

**Response (200):**
```json
{
  "total": 1243,
  "quarantine_count": 87,
  "warn_count": 212,
  "clean_count": 944,
  "top_senders": [
    {"sender": "spammer@bulk-mail.net", "count": 23}
  ],
  "feedback_count": 15,
  "daily_stats": [
    {"day": "2026-06-25", "total": 89, "quarantines": 7}
  ]
}
```

---

## Manual Analysis

### POST /api/analyze

Analisis manual satu email mentah secara on-demand.

**Authorization:** Semua role yang sudah login.

**Request Body (JSON):**
```json
{
  "raw_email": "From: attacker@fake.id\r\nSubject: URGENT\r\n\r\nClick here to verify..."
}
```

**Response (200):**
```json
{
  "email_id": "manual-20260626103000",
  "classification": "QUARANTINE",
  "confidence": 0.94,
  "spam_score": 9.2,
  "risk_level": "HIGH",
  "reasons": [
    "Urgency words detected",
    "Domain lookalike: fake.id → lodaya.id"
  ],
  "url_analysis": [
    {
      "url": "http://l0daya.id/verify",
      "is_suspicious": true,
      "attack_type": "typosquatting"
    }
  ],
  "recommended_action": "quarantine",
  "processing_time_ms": 145,
  "subject": "URGENT",
  "sender": "attacker@fake.id",
  "ml_probability": 0.97,
  "sa_score": 9.2,
  "anomaly_score": 0.81,
  "fused_score": 0.94,
  "label": "QUARANTINE"
}
```

**Notes:** Jika classifier service tidak berjalan, sistem menggunakan fallback mode lokal.

---

## Audit Log

### GET /api/audit-log

Ambil riwayat audit log dengan pagination.

**Authorization:** `security_admin`, `superadmin`

**Query Parameters:**

| Parameter | Type | Default | Keterangan |
|---|---|---|---|
| `page` | int | 1 | Nomor halaman |
| `page_size` | int | 50 | Jumlah entri per halaman (maks 200) |
| `event_type` | string | — | Filter berdasarkan tipe aksi |
| `username` | string | — | Filter berdasarkan nama pengguna |

**Response (200):**
```json
{
  "total": 342,
  "page": 1,
  "page_size": 50,
  "pages": 7,
  "items": [
    {
      "id": "123",
      "username": "admin",
      "action": "release",
      "email_id": "abc123def456",
      "ip_address": "192.168.1.10",
      "notes": "",
      "created_at": "2026-06-26T10:05:00"
    }
  ]
}
```

**Tipe Aksi yang Dicatat:**
- `login`, `logout`
- `release`, `confirm_spam`, `report_false_positive`, `delete`
- `manual_analyze`
- `update_settings`

---

## System Settings

### GET /api/settings

Ambil pengaturan sistem saat ini.

**Authorization:** `security_admin`, `superadmin`

**Response (200):**
```json
{
  "threshold_quarantine": 0.70,
  "threshold_warn": 0.30,
  "fusion_ml_weight": 0.50,
  "fusion_sa_weight": 0.25,
  "fusion_anomaly_weight": 0.25,
  "imap_host": "imap.lodaya.id",
  "imap_port": 993,
  "imap_user": "security@lodaya.id",
  "poll_interval_seconds": 30,
  "protected_domains": ["lodaya.id", "lodayatech.id", "lodaya.co.id"],
  "whitelist_senders": ["ceo@trusted-partner.com"],
  "admin_alert_email": "it-security@lodaya.id",
  "max_quarantine_days": 30
}
```

---

### POST /api/settings

Update pengaturan sistem.

**Authorization:** `security_admin`, `superadmin`

**Request Body (JSON):**
```json
{
  "threshold_quarantine": 0.75,
  "protected_domains": ["lodaya.id", "lodayatech.id", "lodaya.co.id", "lodaya.net"]
}
```

Hanya field yang disertakan yang akan diupdate (partial update).

**Response (200):**
```json
{
  "ok": true,
  "updated": ["threshold_quarantine", "protected_domains"],
  "settings": { "...updated settings..." }
}
```

---

### POST /api/settings/test-imap

Uji koneksi IMAP dengan konfigurasi saat ini.

**Authorization:** `security_admin`, `superadmin`

**Response (200):**
```json
{"ok": true, "message": "Connection to imap.lodaya.id:993 successful"}
```

---

## System & Health

### GET /api/health

Cek status layanan.

**Authorization:** Tidak diperlukan.

**Response (200):**
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "database": "connected",
  "websocket_connections": 3,
  "uptime": "N/A"
}
```

---

### GET /metrics

Prometheus metrics endpoint untuk monitoring.

---

## WebSocket

### WS /ws

Real-time live feed untuk email baru yang masuk.

**Connection:** `ws://localhost:8081/ws?token=<JWT_TOKEN>`

**Message format:**
```json
{
  "type": "new_email",
  "email_id": "xyz789",
  "label": "QUARANTINE",
  "sender": "attacker@phish.id",
  "subject": "Verify your account",
  "fused_score": 0.93
}
```

---

## Error Codes

| HTTP Code | Keterangan |
|---|---|
| `200` | OK |
| `400` | Bad Request — parameter tidak valid |
| `401` | Unauthorized — belum login atau token expired |
| `403` | Forbidden — role tidak cukup |
| `404` | Not Found — email tidak ditemukan |
| `429` | Too Many Requests — rate limit exceeded |
| `500` | Internal Server Error |
| `503` | Service Unavailable — classifier sedang tidak aktif |

---

*API Reference ini dibuat untuk Final Project President University — Section 5.4*  
*© 2026 Lodaya Technologies Indonesia*
