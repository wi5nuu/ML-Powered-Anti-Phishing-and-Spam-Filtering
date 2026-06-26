# Panduan Pengguna — Sistem Anti-Phishing & Spam Filtering LTI

**Versi:** 3.0.0 | **Tanggal:** Juni 2026 | **Klien:** Lodaya Technologies Indonesia (LTI)

---

## Daftar Isi

1. [Pengenalan Sistem](#1-pengenalan-sistem)
2. [Cara Login](#2-cara-login)
3. [Halaman Kotak Masuk (Inbox)](#3-halaman-kotak-masuk-inbox)
4. [Melihat Detail Email](#4-melihat-detail-email)
5. [Tindakan pada Email Karantina](#5-tindakan-pada-email-karantina)
6. [Halaman Metrik & Statistik](#6-halaman-metrik--statistik)
7. [Manual Email Analyzer](#7-manual-email-analyzer)
8. [Pengaturan Sistem](#8-pengaturan-sistem)
9. [Audit Log](#9-audit-log)
10. [Memahami Badge & Skor](#10-memahami-badge--skor)
11. [FAQ & Troubleshooting](#11-faq--troubleshooting)

---

## 1. Pengenalan Sistem

Sistem Anti-Phishing & Spam Filtering LTI adalah platform keamanan email berbasis AI yang melindungi **25 staf LTI** dari serangan phishing, spam, dan domain lookalike.

### Cara Kerja Sistem

```
Email Masuk
    ↓
[Layer 1: SpamAssassin]  — Rule-based scoring (regex, bayesian)
[Layer 2: XGBoost+TF-IDF] — Supervised ML (ROC-AUC: 0.9938)
[Layer 3: Anomaly Detection] — Isolation Forest + One-Class SVM
    ↓
[Decision Fusion Engine]
ML (50%) + SpamAssassin (25%) + Anomaly (25%)
    ↓
┌─────────────────────────────────────┐
│ CLEAN      → Email dikirim normal  │
│ WARN       → Header peringatan     │
│ QUARANTINE → Ditahan di dashboard  │
└─────────────────────────────────────┘
```

### Hak Akses per Peran

| Peran | Deskripsi | Akses |
|---|---|---|
| **Superadmin** | IT Manager LTI | Semua fitur + manajemen user |
| **Security Admin** | Tim IT Security | Quarantine, settings, audit log |
| **Mail Reviewer** | Admin/CS | Lihat & tindak email karantina |
| **User** | Staf umum | Hanya lihat email milik sendiri |

---

## 2. Cara Login

1. Buka browser dan akses: `http://localhost:8081` (atau URL yang diberikan IT)
2. Masukkan **username** dan **password** yang diberikan oleh IT Security
3. Klik tombol **Masuk**

> ⚠️ **Jangan bagikan password Anda kepada siapapun, termasuk rekan kerja!**

### Akun Default (untuk Testing)

| Username | Password | Peran |
|---|---|---|
| `superadmin` | `SuperAdminPassword123!` | Superadmin |
| `admin` | `AdminPassword123!` | Security Admin |
| `reviewer` | `ReviewerPassword123!` | Mail Reviewer |
| `user` | `UserPassword123!` | User biasa |

> 🔴 **Wajib ganti semua password default sebelum production!**

---

## 3. Halaman Kotak Masuk (Inbox)

Setelah login, Anda akan melihat halaman **Kotak Masuk** yang menampilkan semua email yang telah diproses sistem.

### Tab Kategori

Di bagian atas daftar email terdapat tab filter:

| Tab | Deskripsi |
|---|---|
| **Semua** | Semua email termasuk karantina & peringatan |
| **Karantina** | Email yang ditahan — perlu tindakan |
| **Peringatan** | Email mencurigakan yang tetap dikirim tapi diberi header |
| **Bersih** | Email yang lolos semua filter (aman) |

### Warna Badge Label

- 🔴 **QUARANTINE** — Email berbahaya, ditahan sistem
- 🟡 **WARN** — Email mencurigakan, sudah dikirim dengan peringatan
- 🟢 **CLEAN** — Email aman

### Pencarian & Filter

- Gunakan **kotak pencarian** di bagian atas untuk mencari berdasarkan subjek atau pengirim
- Klik ikon **filter (≡)** untuk memfilter berdasarkan tanggal, label, atau status
- Tekan **Enter** setelah mengetik kata kunci untuk mencari

### Statistik di Atas Daftar

Panel **StatsRibbon** di atas inbox menampilkan:
- Total email diproses hari ini
- Jumlah email dikarantina
- Jumlah peringatan aktif
- Jumlah email bersih

---

## 4. Melihat Detail Email

Klik baris email mana pun untuk membuka halaman **Detail Email**.

### Informasi yang Ditampilkan

**Informasi Pengirim:**
- Nama pengirim & alamat email
- Domain asal pengirim
- Status SPF / DKIM / DMARC (tanda tangan email)

**Skor Deteksi:**
| Skor | Keterangan |
|---|---|
| **Skor AI (ML)** | Probabilitas spam dari model XGBoost (0–100%) |
| **Skor SpamAssassin** | Skor rule-based SpamAssassin |
| **Skor Anomali** | Tingkat keanehan pola email (Isolation Forest) |
| **Skor Gabungan** | Skor akhir = ML×50% + SA×25% + Anomali×25% |

**Penjelasan Bahasa Manusia (XAI):**

Sistem secara otomatis memberikan penjelasan mengapa email ini dianggap berbahaya, misalnya:
- _"Email mengandung link yang mengarah ke domain mirip lodaya.id"_
- _"Kata-kata mendesak terdeteksi (URGENT, VERIFY NOW)"_
- _"Verifikasi identitas pengirim (SPF) gagal"_

**Header Email Mentah:**
Klik **"Tampilkan Header Mentah"** untuk melihat header teknis email lengkap (untuk investigasi IT).

---

## 5. Tindakan pada Email Karantina

### Tombol Tindakan Tersedia

| Tombol | Siapa | Apa yang Terjadi |
|---|---|---|
| **Lepaskan Email** | Mail Reviewer+ | Email dikirim ke inbox penerima |
| **Konfirmasi Spam** | Mail Reviewer+ | Email ditandai spam, data dikirim untuk pelatihan ulang |
| **Laporkan False Positive** | Mail Reviewer+ | Tandai bahwa sistem salah (FP), kirim ke tim ML |
| **Hapus Permanen** | Security Admin+ | Email dihapus dari database |

### Kapan Mengklik Apa?

**Lepaskan email jika:**
- Anda mengenal pengirimnya dan tahu email itu sah
- Email adalah notifikasi sistem internal yang sah

**Konfirmasi Spam jika:**
- Email jelas merupakan spam atau penipuan
- Ada tawaran uang, hadiah, atau ancaman tidak masuk akal

**Laporkan False Positive jika:**
- Email dari vendor/mitra resmi LTI tapi dikarantina
- Email internal perusahaan tapi terblokir

> 💡 **Tips:** Jika ragu antara "Lepaskan" dan "Laporkan False Positive", pilih **Laporkan False Positive** — ini membantu sistem belajar!

---

## 6. Halaman Metrik & Statistik

Akses via menu **Metrik** di sidebar atau klik ikon di topbar.

### Grafik yang Tersedia

- **Distribusi Label** — Persentase QUARANTINE / WARN / CLEAN
- **Tren Harian (14 hari)** — Total email & karantina per hari
- **Top 10 Pengirim Terblokir** — Pengirim paling sering dikarantina
- **Feedback Count** — Jumlah laporan false positive dari staf

### Export Data

Dari halaman Metrik, klik **Export CSV** untuk mengunduh data email ke spreadsheet.

---

## 7. Manual Email Analyzer

Fitur **Analyzer** memungkinkan Anda menganalisis email secara manual — cocok untuk email yang masuk ke inbox normal tapi Anda ragu keamanannya.

**Cara menggunakan:**

1. Buka menu **Manual Analyzer** di sidebar (ikon 🛡️)
2. **Tempel raw email** (copy seluruh isi email termasuk header) ke kotak teks
3. Klik **Analisis Sekarang**
4. Sistem akan menampilkan:
   - **Risk Level** (HIGH / MEDIUM / LOW)
   - **Skor Deteksi** (ML, SpamAssassin, Anomali)
   - **Alasan** mengapa email dianggap berbahaya
   - **Analisis URL** — apakah ada link mencurigakan
   - **Header Email** yang penting

**Cara mendapatkan raw email:**
- **Gmail:** Buka email → ⋮ (tiga titik) → "Show original" → Copy semua
- **Outlook:** Buka email → File → Properties → Internet headers → Copy
- **Thunderbird:** Ctrl+U untuk melihat source email

---

## 8. Pengaturan Sistem

**Hanya tersedia untuk Security Admin dan Superadmin.**

Akses via menu **Pengaturan** di sidebar (ikon ⚙️).

### Pengaturan yang Tersedia

**Threshold Deteksi:**
| Setting | Default | Keterangan |
|---|---|---|
| Ambang Karantina | 70% | Skor ≥ 70% → Email dikarantina |
| Ambang Peringatan | 30% | Skor ≥ 30% → Header peringatan disisipkan |

**Bobot Fusion (harus total = 100%):**
- Bobot ML Model: 50%
- Bobot SpamAssassin: 25%
- Bobot Anomaly Detection: 25%

**Konfigurasi IMAP:**
Isi Host, Port, dan Username IMAP untuk mengaktifkan polling otomatis.
Klik **Test Koneksi** untuk memverifikasi sebelum menyimpan.

**Domain Terlindungi:**
Kelola daftar domain LTI yang dijaga dari lookalike attack (misal: `lodaya.id`).

**Whitelist Pengirim:**
Tambahkan alamat email yang selalu dipercaya (tidak akan pernah dikarantina).

Klik **Simpan Pengaturan** setelah selesai. Klik **Reset ke Default** untuk kembali ke nilai awal.

---

## 9. Audit Log

**Hanya tersedia untuk Security Admin dan Superadmin.**

Akses via menu **Audit Log** di sidebar (ikon 📋).

Audit Log mencatat **semua tindakan yang dilakukan** di sistem:
- Login / Logout pengguna
- Pelepasan / konfirmasi email karantina
- Laporan false positive
- Perubahan pengaturan sistem
- Analisis email manual

### Fitur Audit Log

- **Filter** berdasarkan tipe aksi atau nama pengguna
- **Pagination** — 50 entri per halaman
- **Export CSV** — Unduh seluruh log ke spreadsheet

---

## 10. Memahami Badge & Skor

### Label Email

| Badge | Warna | Arti |
|---|---|---|
| QUARANTINE | 🔴 Merah | Email sangat berbahaya, ditahan |
| WARN | 🟡 Kuning | Email mencurigakan, diberi peringatan |
| CLEAN | 🟢 Hijau | Email aman |

### Status Email di Karantina

| Status | Arti |
|---|---|
| **Pending** | Menunggu tindakan reviewer |
| **Released** | Sudah dilepaskan ke inbox |
| **Confirmed Spam** | Dikonfirmasi sebagai spam |

### Cara Membaca Skor

- **Skor > 70%** → Hampir pasti spam/phishing
- **Skor 30-70%** → Mencurigakan, perlu diperiksa
- **Skor < 30%** → Kemungkinan besar aman

### Indikator SPF/DKIM/DMARC

| Indikator | Arti |
|---|---|
| ✅ SPF Pass | Pengirim diverifikasi sah dari domain-nya |
| ❌ SPF Fail | Pengirim mungkin memalsukan domain |
| ✅ DKIM Pass | Tanda tangan digital email valid |
| ❌ DKIM Fail | Email mungkin dimodifikasi dalam perjalanan |

---

## 11. FAQ & Troubleshooting

### Q: Email penting dari vendor saya dikarantina, apa yang harus saya lakukan?

**A:** Klik email tersebut → klik **Laporkan False Positive** (bukan sekadar Lepaskan). Ini akan memastikan sistem belajar bahwa pengirim tersebut aman, dan email akan otomatis dilepaskan.

Jika kejadian ini berulang, minta IT Security untuk menambahkan domain pengirim ke **Whitelist** di halaman Pengaturan.

---

### Q: Kenapa ada email bersih di tab Karantina?

**A:** Model AI tidak sempurna. False Positive (email sah yang dikarantina) bisa terjadi dengan tingkat sekitar 4.76%. Inilah tujuan fitur **Laporkan False Positive** — untuk terus meningkatkan akurasi sistem.

---

### Q: Apakah email yang dikarantina sudah dikirim ke penerima?

**A:** **Tidak.** Email dengan label QUARANTINE ditahan sepenuhnya di sistem dan tidak dikirimkan ke inbox penerima sampai direview dan dilepaskan oleh Mail Reviewer atau Security Admin.

Email dengan label WARN sudah dikirim ke penerima, namun dengan header peringatan yang disisipkan.

---

### Q: Berapa lama email disimpan di karantina?

**A:** Default adalah **30 hari**. Setelah itu, email dihapus otomatis. Setting ini bisa diubah oleh Security Admin di halaman Pengaturan.

---

### Q: Saya tidak bisa login, apa yang harus dilakukan?

**A:** Hubungi IT Security di `it-security@lodaya.id` atau Ext. 101. Jangan mencoba reset password sendiri.

---

### Q: Bagaimana cara memastikan email yang saya terima aman?

**A:** Gunakan fitur **Manual Analyzer** — paste raw email dan sistem akan menganalisis secara mendalam dalam hitungan detik.

---

*Dokumen ini dibuat untuk Final Project President University — Section 5.4*  
*© 2026 Lodaya Technologies Indonesia. Internal Use Only.*
