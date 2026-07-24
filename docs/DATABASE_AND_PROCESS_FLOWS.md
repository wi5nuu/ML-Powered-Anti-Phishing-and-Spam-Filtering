# ML-Powered Anti-Phishing and Spam Filtering

## Name of the Project
**ML-Powered Anti-Phishing and Spam Filtering**

## Database Design

### Group
- **Wisnu Alfian Nur Ashar** — ML Engineer
- **Muhammad Ilham Maulana** — Backend & Pipeline
- **Muhammad Ahda Briliantama** — Dashboard & API
- **Christofer** — Dataset & Validation
- **Risly** — Infrastructure & Monitoring

### Database Overview
Sistem menggunakan SQLAlchemy ORM untuk menyimpan status email, hasil deteksi, pengguna, audit, umpan balik, dan versi model.

#### Entitas utama
- `Organization`: tenant atau organisasi yang mengelompokkan user, email, dan API key.
- `User`: akun aplikasi dengan role `user`, `admin`, atau `superadmin`.
- `AdminMailbox`: konfigurasi mailbox admin untuk forwarding internal dan domain.
- `QuarantineEmail`: hasil pemrosesan setiap email, termasuk skor fusion dan label routing.
- `Feedback`: catatan review atau laporan terhadap email terdeteksi.
- `PipelineMetrics`: metrik pipeline harian untuk monitoring.
- `Report`: tiket/permintaan dukungan dari pengguna.
- `ApiKey`: kredensial API untuk integrasi terdaftar.
- `ModelVersion`: riwayat versi model ML dengan metadata evaluasi.
- `AuditTrail`: jejak tindakan sistem dan operator.
- `AuditLog`: log aktivitas pengguna yang dapat dilihat di dashboard.

### Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ USERS : "contains"
    ORGANIZATIONS ||--o{ QUARANTINE_EMAILS : "owns"
    ORGANIZATIONS ||--o{ API_KEYS : "issues"
    USERS ||--o{ AUDIT_LOGS : "creates"
    QUARANTINE_EMAILS ||--o{ FEEDBACK : "references"

    ORGANIZATIONS {
        int id PK
        string name
        json config
        datetime created_at
    }

    USERS {
        int id PK
        string username
        string email
        string hashed_password
        string role
        int organization_id FK
        bool is_active
        datetime created_at
    }

    ADMIN_MAILBOXES {
        int id PK
        string email
        string domain
        string password_hash
        string sender_name
        string created_by
        bool is_active
        datetime created_at
    }

    QUARANTINE_EMAILS {
        int id PK
        string email_id
        string received_at
        string label
        float fused_score
        float sa_score
        float ml_probability
        float anomaly_score
        string shap_json
        string xai_summary
        string routing_reason
        string raw_content_hash
        string raw_content
        string attachments_json
        string spf_result
        string dkim_result
        string dmarc_result
        string status
        string category
        string subject
        string sender
        string recipient_list
        int organization_id FK
        string model_version
        datetime created_at
    }

    FEEDBACK {
        int id PK
        string email_id
        string feedback_type
        string notes
        datetime created_at
    }

    PIPELINE_METRICS {
        int id PK
        string date
        int total_processed
        int total_clean
        int total_warn
        int total_quarantine
        int false_positive_count
        float avg_latency_ms
        string model_version
        datetime created_at
    }

    REPORTS {
        int id PK
        string username
        string subject
        string message
        string category
        string priority
        string status
        string admin_reply
        datetime created_at
        datetime resolved_at
    }

    API_KEYS {
        int id PK
        string key_hash
        string name
        int organization_id FK
        bool is_active
        int rate_limit
        datetime created_at
    }

    MODEL_VERSIONS {
        int id PK
        string version
        string model_type
        string filepath
        json metrics
        bool is_active
        string created_by
        datetime created_at
    }

    AUDIT_TRAIL {
        int id PK
        datetime timestamp
        string actor
        string action
        string target_type
        string target_id
        string status
        json changes
        string ip_address
        string description
    }

    AUDIT_LOGS {
        int id PK
        string user
        string action
        string email_id
        string ip_address
        string details
        datetime created_at
    }
```

### Relational Notes
- `User.organization_id` menunjuk ke `Organization.id`.
- `QuarantineEmail.organization_id` menunjuk ke `Organization.id`.
- `ApiKey.organization_id` menunjuk ke `Organization.id`.
- `QuarantineEmail.email_id` digunakan sebagai referensi untuk `Feedback.email_id`.
- `Report.username` dan `AuditLog.user` menyimpan nilai string username sebagai referensi operasional.

## Data Flow Diagram (DFD)

### DFD Level 0 (Context Diagram)

```mermaid
flowchart LR
    ExternalSender[External Sender] -->|Send email| SMTPSystem[Anti-Phishing System]
    SMTPSystem -->|Forward / Quarantine decision| EmployeeInbox[Employee Inbox]
    SMTPSystem -->|Alerts & Reports| SecurityTeam[Security / Review]
    SMTPSystem -->|Metrics| Monitoring[Grafana / Prometheus]
    SMTPSystem -->|Dashboard access| Admin[Dashboard / Admin]
```

### DFD Level 1

```mermaid
flowchart LR
    ES[External Sender] --> SMTP[SMTP Receiver]
    SMTP --> REDIS[Redis Queue]
    REDIS --> WORKER[Pipeline Worker]

    WORKER --> SA[SpamAssassin]
    WORKER --> ML[Classifier API]
    WORKER --> ANOMALY[Anomaly Detector]
    WORKER --> DE[Decision Engine]

    DE --> DB[QuarantineEmail Store]
    DE --> FORWARDER[Email Forwarder]
    FORWARDER --> INBOX[Employee Inbox]
    DE --> ALERT[Alert / Notification]

    USER[Admin / Reviewer] --> DASH[Dashboard UI]
    DASH --> DB
    DASH --> FEEDBACK[Feedback / Reports]
    DASH --> AUDIT[AuditLog / AuditTrail]
```

### DFD Level 2

```mermaid
flowchart TD
    RAW[Raw Email] --> PARSER[Email Parser]
    PARSER --> SA[SpamAssassin Engine]
    PARSER --> FEATURE[Feature Extraction]
    FEATURE --> ML[Supervised ML Model]
    FEATURE --> UNSUPER[Unsupervised Anomaly Detector]
    SA --> DE[Decision Engine]
    ML --> DE
    UNSUPER --> DE
    DE --> ROUTE[Routing Decision]

    ROUTE --> CLEAN[Forward to Inbox]
    ROUTE --> WARN[Forward with X-Spam-Reason Header]
    ROUTE --> QUAR[Quarantine Store]

    QUAR --> DBQ[QuarantineEmail Table]
    DBQ --> DASH[Dashboard]
    DBQ --> METRICS[PipelineMetrics Table]

    FEATURE --> MODEL[ModelVersion]
    MODEL --> ML
```

### DFD Level 2 - Feedback and Monitoring

```mermaid
flowchart TD
    Admin[Admin / Analyst] -->|Review email| Dashboard[Dashboard UI]
    Dashboard -->|Read quarantine data| DB[QuarantineEmail Store]
    Dashboard -->|Submit review| Feedback[Feedback Table]
    Dashboard -->|Open issue| Report[Report Table]
    Dashboard -->|Record audit| AuditLog[AuditLog Table]
    System -->|Write metrics| PipelineMetrics[Metrics Table]
    PipelineMetrics --> Monitoring[Grafana / Prometheus]
```

## How to use this documentation
- ERD mendeskripsikan struktur tabel dan relasi utama.
- DFD Level 0/1/2 menunjukkan aliran email dari penerimaan sampai keputusan dan penyimpanan.
- DFD khusus Feedback & Monitoring menunjukkan jalur review, laporan, dan audit.
- Diagram mermaid dapat dirender langsung di GitHub atau editor Markdown yang mendukung Mermaid.

---

## Catatan tambahan
Dokumentasi ini dibuat berdasarkan struktur kode dan model SQLAlchemy yang ada pada `database/models.py`.
