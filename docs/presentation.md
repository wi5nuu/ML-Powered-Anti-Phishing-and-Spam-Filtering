# ML-Powered Anti-Phishing & Spam Filtering

## Final Project — President University
### Fandi Gunawan, S.T., M.T.I., CISSP, CC, ISO 27001 LI, ISO 42001 LA

---

## 1. Masalah & Konteks

**Lodaya Technologies Indonesia (LTI)**
- FinTech, 25 karyawan, 5M+ transaksi/hari
- Staf administrasi & customer service non-IT
- **Tidak ada proteksi email sebelumnya**
- Resiko tinggi: phishing → akun tercuri → fraud nasabah

**Pertanyaan Kritis:**
Kenapa tidak pakai solusi yang sudah ada?

---

## 2. Kenapa Bukan SpamAssassin Saja?

**SpamAssassin murni rule-based:**
- Tidak bisa belajar dari pola serangan baru
- Zero-day phishing = tidak terdeteksi
- Rule perlu update manual

**Solusi kami = SpamAssassin + ML + Anomaly Detection**
SpamAssassin jadi salah satu komponen, bukan satu-satunya.

→ Tiga lapisan lebih kuat dari satu lapisan

---

## 3. Kenapa Bukan Proofpoint / Mimecast?

| Faktor | Solusi Enterprise | Sistem Kami |
|---|---|---|
| **Biaya** | $3-15/box/bulan × 25 = $75-375/bulan | **0** (open source) |
| **Data Privacy** | Email lewat server pihak ketiga | **100% on-premise** |
| **Kustomisasi** | Terbatas | **Full kontrol** — bilingual (ID+EN), domain spesifik lodaya.id, pola serangan Indonesia |
| **Zero-day detection** | Bergantung threat feed global | **Unsupervised anomaly detection** — mendeteksi yang belum pernah dilihat |

---

## 4. Arsitektur Dual Detection

**Tiga Lapisan, Satu Kesimpulan:**

```
Layer 1 — Supervised (XGBoost + TF-IDF)
  → "Apakah ini mirip spam yang pernah saya lihat?"

Layer 2 — Unsupervised (Isolation Forest + One-Class SVM)
  → "Apakah pola email ini normal untuk LTI?"
  → Dilatih HANYA dengan email bersih — 0 data spam!

Layer 3 — Rule-Based (SpamAssassin)
  → "Apakah ini cocok dengan rule spam klasik?"

↓
Decision Engine fusi 3-way
  ML 50% + SA 25% + Anomaly 25%
↓
CLEAN / WARN / QUARANTINE
```

---

## 5. Yang Paling Unik: Unsupervised Anomaly Detection

**Tidak butuh dataset spam sama sekali.**
Cukup kumpulkan email bersih dari inbox LTI sebagai "normal baseline."

**Bagaimana cara kerjanya:**
1. Latih Isolation Forest pada 1.121 email bersih (ham)
2. Model belajar: "Seperti apa email normal di LTI?"
3. Email baru yang menyimpang dari pola = **anomali** = waspada

**Kenapa ini penting untuk FinTech:**
- Phishing domain spesifik Indonesia (`bca-secure-login.xyz`)
- Social engineering dalam Bahasa Indonesia
- Pola serangan baru yang belum pernah ada di dataset global

---

## 6. Hasil Training

### Supervised Layer (XGBoost)
| Metrik | Nilai |
|---|---|
| Dataset | 2.243 sampel (SA corpus + Enron + sintetis) |
| CV ROC-AUC | **0.9891** |
| Test ROC-AUC | **0.9938** |
| Precision / Recall | 0.95 / 0.95 |
| FP / FN | 8 / 8 (dari 337 test) |

### Unsupervised Layer (Isolation Forest)
| Metrik | Nilai |
|---|---|
| Training data | **1.121 email bersih (0 spam)** |
| Model | 200 trees, contamination=0.05 |
| Deteksi anomali phishing | **0.706** (threshold >0.5 = anomali) |
| False positive rate (clean email) | Rendah — email normal skor ~0.34 |

### Dual Detection — Contoh Skenario

| Email | ML (Sup) | Anomali (Unsup) | SA | Fused | Label |
|---|---|---|---|---|---|
| Phishing urgensi tinggi (bit.ly) | 0.960 | **0.706** ⚠️ | 9.5 | 1.000 | **KARANTINA** |
| Meeting internal biasa | 0.389 | **0.337** ✅ | 0.0 | 0.323 | WARN |
| Invoice dari vendor | 0.155 | **0.376** ✅ | 2.0 | 0.203 | CLEAN |

---

## 7. XAI — Explainable AI untuk Staf Non-Teknis

Setiap email yang ditandai menyertakan header `X-Spam-Reason`:

```
X-Spam-Reason: [Urgency Score: 0.50, 
                SPF Verification: FAILED, 
                URL Shortener Detected]
```

**Kenapa ini penting:**
- Staf non-teknis belajar **mengapa** email itu berbahaya
- Passive training setiap kali email dikarantina
- Mengubah staf dari titik terlemah → garis pertahanan pertama

---

## 8. Perbandingan: Sistem Kami vs Alternatif

| Kriteria | SpamAssassin Only | Proofpoint | Mimecast | **Sistem Kami** |
|---|---|---|---|---|
| Rule-based | ✅ | ✅ | ✅ | ✅ |
| Supervised ML | ❌ | ✅ | ✅ | ✅ |
| Unsupervised Anomaly | ❌ | ❌ | ❌ | **✅** |
| Bilingual ID-EN | ❌ | ❌ | ❌ | **✅** |
| XAI untuk staf | ❌ | ❌ | ❌ | **✅** |
| On-premise / Data privacy | ✅ | ❌ | ❌ | **✅** |
| Biaya berlangganan | 0 | $$$ | $$$ | **0** |
| Kustomisasi domain | Terbatas | ❌ | ❌ | **✅ Full** |

---

## 9. Testing

**23 unit tests** — semuanya PASS

| Module | Tests | Coverage |
|---|---|---|
| features.py | 7 tests | 96% |
| fusion.py | 9 tests | 100% |
| router.py | 2 tests | 93% |
| parser.py | 4 tests | 100% |
| classifier | 3 tests | — |
| **Total** | **23 tests** | Core modules 96-100% |

---

## 10. Extra Credit Terlaksana

1. ✅ **Domain Inconsistency** — Levenshtein + dnstwist (2.448 domain permutasi)
   → "1odaya.id" terdeteksi sebagai lookalike lodaya.id
2. ✅ **Explainable AI** — SHAP values + `X-Spam-Reason` header
   → Staf belajar dari setiap email yang dikarantina
3. ✅ **Unsupervised Anomaly Detection** — Isolation Forest + One-Class SVM
   → Deteksi zero-day tanpa data spam
4. ✅ **One-Class Classification** — Alternatif masa depan
   → Sistem bisa berjalan dengan 0 dataset spam

---

## 11. Demo Pipeline

```
SMTP → Mailpit → REST API → Redis → Worker → DB → Dashboard
  (1025)    (8025)         (6379)   (parallel  (SQLite)  (8081)
                                     SA + ML +
                                     Anomaly)
```

**End-to-end:** 3 email → pipeline → dashboard dalam < 30 detik

---

## 12. Kesimpulan

**Sistem ini unik karena:**
1. Tiga lapisan deteksi (bukan satu)
2. Unsupervised anomaly detection untuk zero-day
3. XAI yang mendidik staf secara pasif
4. Bilingual + kustomisasi domain Indonesia
5. 100% on-premise, 0 biaya lisensi
6. Data privacy terjaga — email finansial tidak keluar server

**"Bukan sekadar spam filter — ini sistem keamanan yang tumbuh bersama LTI"**

---

*Terima Kasih — Fandi Gunawan, S.T., M.T.I.*
*President University — June 2026*
