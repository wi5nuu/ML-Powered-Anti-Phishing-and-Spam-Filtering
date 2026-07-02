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
Sistem menggunakan SQLAlchemy ORM dengan beberapa entitas utama yang mendukung alur email, deteksi, pengguna, audit, dan feedback.

#### Entitas utama
- `Organization`: organisasi pengguna atau tenant.
- `User`: akun aplikasi dengan peran `user`, `admin`, atau `superadmin`.
- `AdminMailbox`: kotak surat admin yang dikelola untuk forwarding dan otentikasi.
- `QuarantineEmail`: email yang diproses dan diberi label `CLEAN`, `WARN`, atau `QUARANTINE`.
- `Feedback`: catatan umpan balik terhadap email atau keputusan klasifikasi.
- `PipelineMetrics`: metrik harian pipeline untuk monitoring dan evaluasi.
- `Report`: laporan atau tiket dari pengguna.
- `ApiKey`: kunci API untuk akses terdaftar.
- `ModelVersion`: versi model yang digunakan dan metadata evaluasi.
- `AuditTrail`: jejak tindakan sistem dan operator.
- `AuditLog`: log audit yang ditampilkan di dashboard.

### Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ USERS : has
    ORGANIZATIONS ||--o{ QUARANTINE_EMAILS : owns
    ORGANIZATIONS ||--o{ API_KEYS : issues
    USERS ||--o{ AUDIT_LOGS : performs
    USERS ||--o{ REPORTS : creates

    QUARANTINE_EMAILS {
        int id PK
        string email_id
        string received_at
        string label
        float fused_score
        float sa_score
        float ml_probability
        float anomaly_score
        string routing_reason
        string status
        string category
        string subject
        string sender
        string recipient_list
        int organization_id FK
    }

    USERS {
        int id PK
        string username
        string email
        string hashed_password
        string role
        int organization_id FK
        bool is_active
    }

    ORGANIZATIONS {
        int id PK
        string name
        json config
    }

    API_KEYS {
        int id PK
        string name
        string key_hash
        int organization_id FK
        bool is_active
    }

    REPORTS {
        int id PK
        string username
        string subject
        string message
        string category
        string status
    }

    FEEDBACK {
        int id PK
        string email_id
        string feedback_type
        string notes
    }

    PIPELINE_METRICS {
        int id PK
        string date
        int total_processed
        int total_clean
        int total_warn
        int total_quarantine
    }

    MODEL_VERSIONS {
        int id PK
        string version
        string model_type
        json metrics
        bool is_active
    }

    AUDIT_TRAIL {
        int id PK
        datetime timestamp
        string actor
        string action
        string target_type
        string target_id
        string status
    }

    AUDIT_LOGS {
        int id PK
        string user
        string action
        string email_id
        string ip_address
        string details
    }
```

### Relational Notes
- `User.organization_id` menunjuk ke `Organization.id`.
- `QuarantineEmail.organization_id` menunjuk ke `Organization.id`.
- `ApiKey.organization_id` menunjuk ke `Organization.id`.
- `Report.username` dan `AuditLog.user` menyimpan informasi pengguna terkait operasi.
- `QuarantineEmail.email_id` digunakan sebagai referensi utama untuk `Feedback.email_id`.

## Data Flow Diagram (DFD)

### DFD Level 0 (Context Diagram)

```mermaid
flowchart LR
    ExternalSender[External Sender] -->|Email masuk via SMTP| System[Anti-Phishing System]
    System -->|Status notifikasi| Dashboard[Dashboard / Admin]
    System -->|Forward / Hold| Recipient[Employee Inbox]
    System -->|Alerts / Reports| SecurityTeam[Security Team]
    System -->|Metrics| Monitoring[Monitoring / Grafana]
```

### DFD Level 1

```mermaid
flowchart TD
    subgraph Inbound[Inbound Email Processing]
        ES[External Sender] --> SMTP[SMTP Receiver]
        SMTP --> REDIS[Redis Queue]
        REDIS --> WORKER[Pipeline Worker]
        WORKER --> SA[SpamAssassin]
        WORKER --> ML[ML Classifier + Anomaly]
        WORKER --> DE[Decision Engine]
        DE --> DB[QuarantineEmail Store]
        DE --> FORWARDER[Email Forwarder]
        FORWARDER --> INBOX[Employee Inbox]
    end

    subgraph Admin[Dashboard / Feedback]
        User[Admin / Reviewer] --> UI[Dashboard App]
        UI --> DB
        UI --> FEEDBACK[Feedback / Reports]
        UI --> AUDIT[AuditLog / AuditTrail]
    end

    SA --> DE
    ML --> DE
    INBOX -->|Delivered or blocked| Recipient
```

### DFD Level 2

```mermaid
flowchart TD
    subgraph ScoreAndRoute[Scoring and Routing]
        RAW[Raw Email] --> PARSER[Email Parser]
        PARSER --> SA[SpamAssassin Engine]
        PARSER --> FEATURE[Feature Extraction]
        FEATURE --> ML[Supervised ML + Anomaly Detector]
        SA --> DE[Decision Engine]
        ML --> DE
        DE --> ROUTE[Routing Decision]
        ROUTE --> CLEAN[Forward to Inbox]
        ROUTE --> WARN[Forward with Header]
        ROUTE --> QUAR[Quarantine Store]
    end

    subgraph Storage[Database]
        QUAR --> DBQ[QuarantineEmail]
        DBQ --> DASH[Dashboard]
        DBQ --> METRICS[PipelineMetrics]
    end

    FEATURE --> DBM[ModelVersion]
    DBM --> ML
```

### DFD untuk Fitur Feedback dan Monitoring

```mermaid
flowchart TD
    User[Admin / Analyst] -->|Review email| Dashboard[Dashboard UI]
    Dashboard -->|Request data| DB[QuarantineEmail Store]
    Dashboard -->|Submit feedback| Feedback[Feedback Table]
    Feedback --> DB
    User -->|Create report| Report[Report Table]
    Report --> DB
    System -->|Publish metrics| Monitoring[Grafana / Prometheus]
    DB -->|Metrics data| Monitoring
```

## Cara menggunakan dokumentasi ini
- ERD merinci struktur database dan relasi utama.
- DFD Level 0/1/2 menggambarkan aliran data dari email masuk sampai keputusan dan penyimpanan.
- Diagram mermaid dapat dirender langsung di GitHub atau di editor Markdown yang mendukung mermaid.

---

## Catatan tambahan
Dokumentasi ini dibuat berdasarkan struktur kode dan model SQLAlchemy yang ada pada file `database/models.py`.
