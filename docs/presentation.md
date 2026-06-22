# ML-Powered Anti-Phishing and Spam Filtering

## Final Project — President University
### Fandi Gunawan, S.T., M.T.I., CISSP, CC, ISO 27001 LI, ISO 42001 LA

---

## 1. Latar Belakang

**Lodaya Technologies Indonesia (LTI)**
- FinTech company, 25 employees
- 5M+ daily financial transactions
- Non-technical staff rentan terhadap phishing
- Tidak ada sistem filtering email sebelumnya

**Masalah:**
Administrasi & customer service dari non-IT background. Spam filtering mandatory untuk mengurangi risiko.

---

## 2. Arsitektur Sistem

```
Email (SMTP) → Mailpit → API Fetcher → Redis Queue
                                              |
                    ┌─────────────────────────┘
                    │                         │
            SpamAssassin              ML Classifier
            (rule-based)              (XGBoost + TF-IDF)
                    │                         │
                    └──────────┬──────────────┘
                               │
                        Decision Engine
                        (weighted fusion 65/35)
                               │
                    ┌──────────┴──────────┐
                    │                     │
                  WARN              QUARANTINE
              (+header)               (DB)
                                        │
                                  Admin Dashboard
```

---

## 3. Tech Stack

| Komponen | Teknologi |
|---|---|
| Ingestion | Mailpit REST API / SMTP |
| Rule Engine | Apache SpamAssassin |
| ML Framework | XGBoost + TF-IDF (50.000 fitur) |
| Inference API | Python FastAPI (port 8001) |
| Queue | Redis (asinkron) |
| Database | SQLite / PostgreSQL |
| Dashboard | FastAPI + Jinja2 (port 8081) |
| Container | Docker Compose |
| Monitoring | Prometheus |

---

## 4. Machine Learning Model

**Dataset:**
- SpamAssassin public corpus: 3.899 files
- Enron spam dataset: 11.029 emails
- Synthetic phishing: 35 samples
- **Total: 2.243 sampel training** (seimbang 50/50)

**Pipeline:**
- TF-IDF vectorizer (50.000 fitur)
- 20 structured features (urgency, URL count, dll)
- XGBoost dengan RandomizedSearchCV (10 iter × 3 fold)

**Hasil:**
- Best CV ROC-AUC: **0.9891**
- Test ROC-AUC: **0.9938**
- Precision: **0.95** | Recall: **0.95**
- FP: 8 | FN: 8 (dari 337 test samples)

**Hyperparameters:**
- 300 trees, max_depth=6, learning_rate=0.05
- colsample_bytree=0.6, subsample=0.7

---

## 5. Structured Features (20 Fitur)

| Kategori | Fitur |
|---|---|
| **Urgency** | urgency_score, num_exclamations, num_caps_words |
| **URL Analysis** | num_urls, num_unique_domains, has_url_shortener, has_lookalike_domain, url_entropy |
| **Content** | num_forms, javascript_present, word_count, html_text_ratio |
| **Authentication** | spf_pass, dkim_pass, dmarc_pass |
| **Header** | display_name_mismatch, reply_to_mismatch, has_attachments |
| **Engagement** | num_recipients, suspicious_attachments |

---

## 6. Decision Engine

**Weighted Fusion:**
```
fused_score = 0.65 × ml_probability + 0.35 × (sa_score / 10)
```

**Thresholds:**
| Skor | Label | Aksi |
|---|---|---|
| < 0.30 | CLEAN | Kirim ke inbox |
| 0.30 - 0.70 | WARN | Tambah X-Spam-Reason header |
| >= 0.70 | QUARANTINE | Isolasi di database |

**Hard Overrides:**
- SA score >= 15 → langsung QUARANTINE
- ML probability >= 0.95 → langsung QUARANTINE
- SPF/DKIM/DMARC semua pass → turunkan risiko

---

## 7. Extra Credit

### ① Domain Inconsistency Checking
- Levenshtein distance untuk lookalike domain
- dnstwist integration (2.448 domain permutasi)
- Mendeteksi: `bca-secure-login.xyz` → meniru BCA

### ② Explainable AI (XAI)
- SHAP values untuk setiap prediksi
- `X-Spam-Reason` header:
  ```
  X-Spam-Reason: [High Urgency Score: 0.89, 
                  Lookalike Link Detected, 
                  URL Shortener Detected]
  ```
- Melatih staf non-teknis mengenali phishing

---

## 8. Pipeline Demo

**End-to-End Flow:**
1. Email dikirim via SMTP ke Mailpit (port 1025)
2. Mailpit API menyediakan raw email
3. Fetcher mengambil email baru (setiap 30 detik)
4. Push ke Redis queue `email_pipeline`
5. Worker consume: parallel SA + ML scoring
6. Decision Engine fusion → QUARANTINE/WARN/CLEAN
7. Simpan ke database
8. Admin review via Dashboard

**Contoh Hasil:**
| Email | ML | SA | Fused | Label |
|---|---|---|---|---|
| "URGENT: Verify Account" (bit.ly) | 0.961 | 9.5 | 1.000 | QUARANTINE |
| "Your Invoice Attached" | 0.851 | 5.5 | 0.650 | WARN |
| "Meeting Tomorrow" | 0.642 | 0.0 | 0.642 | WARN |

---

## 9. Testing

**22 unit tests** — semuanya PASS ✅

| Module | Tests | Coverage |
|---|---|---|
| features.py | 7 tests | 96% |
| fusion.py | 6 tests | 100% |
| router.py | 2 tests | 93% |
| parser.py | 4 tests | 100% |
| classifier | 3 tests | — |
| **Total** | **22 tests** | **34%** (core modules 96-100%) |

---

## 10. Evidence

**12 Screenshots:**
1. Dashboard quarantine list
2. Email detail with XAI explanation
3. Mailpit web UI
4. Classifier API health
5. Training metadata (SHAP, ROC-AUC)
6. Test results (22/22 passed)
7. Directory tree
8. Pipeline worker logs
9. Model info (XGBoost params)
10. Domain monitor output
11. Live prediction result
12. Database quarantine summary

---

## 11. Hosting

**GitHub:** https://github.com/wi5nuu/ML-Powered-Anti-Phishing-and-Spam-Filtering

**License:** MIT License

**Dokumentasi:**
- `docs/user_manual.md` — Panduan staf non-teknis
- `docs/admin_manual.md` — Panduan DevOps
- `docs/architecture.md` — Dokumentasi arsitektur
- `AI_USAGE.md` — AI Usage Disclosure

---

## 12. Kesimpulan

**Sistem telah memenuhi semua mandatory requirements:**
1. ✅ Inbound Email Parsing (Mailpit API)
2. ✅ ML Classifier (XGBoost + TF-IDF, ROC-AUC 0.994)
3. ✅ Quarantine Mechanism (DB + Dashboard)
4. ✅ SpamAssassin Integration
5. ✅ FastAPI Inference API
6. ✅ Redis Async Queue
7. ✅ Docker Containerization

**Extra Credit:**
1. ✅ Domain Inconsistency (Levenshtein + dnstwist)
2. ✅ Explainable AI (SHAP + X-Spam-Reason header)

---

*Terima Kasih — Fandi Gunawan, S.T., M.T.I.*
*President University — June 2026*
