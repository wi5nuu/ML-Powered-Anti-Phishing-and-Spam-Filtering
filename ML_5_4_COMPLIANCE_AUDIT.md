# Audit Kepatuhan 5.4 — ML-Powered Anti-Phishing and Spam Filtering

Tanggal audit: 25 Juli 2026

Dokumen acuan: `Final Projects for President University.pdf`, bagian 5.4.

## Kesimpulan

Alur aplikasi sudah memiliki fondasi teknis yang sesuai: SMTP ingestion, parsing email, SpamAssassin, classifier FastAPI lokal, TF-IDF + XGBoost, Redis queue, worker asinkron, quarantine, URL/domain heuristics, dan header alasan deteksi.

Namun kepatuhan **belum dapat dinyatakan 100%** untuk requirement “TF-IDF vectorization trained on public datasets (Enron or SpamAssassin corpora)”. Dataset yang tersedia di `D:\tools\cyber-project\Data` belum menjadi artefak yang dipakai container classifier saat ini. Jangan menuliskan angka akurasi atau menyatakan model production dilatih dari dataset tersebut sebelum pipeline training dan checksum artefaknya direproduksi.

## Pemetaan requirement

| Requirement 5.4 | Status | Bukti / catatan |
|---|---|---|
| Inbound email parsing melalui relay lokal | Terpenuhi | `worker/smtp_receiver.py` menerima SMTP, memvalidasi recipient/mailbox dari database, lalu meneruskan raw email ke Redis. |
| Model lokal yang mengevaluasi teks, metadata, dan link | Terpenuhi | `classifier/predict.py` memuat XGBoost lokal; `classifier/features.py` mengekstrak TF-IDF, attachment, URL, header autentikasi, HTML, recipient, dan fitur metadata lain. |
| Quarantine untuk skor tinggi | Terpenuhi | `worker/pipeline_worker.py` menyimpan hasil non-clean ke `QuarantineEmail`; forwarding hanya dilakukan untuk hasil CLEAN. |
| Warning header untuk pesan borderline | Terpenuhi | `worker/email_forwarder.py` menambahkan header hasil scan/alasan sebelum pesan diteruskan. |
| SpamAssassin + custom Python FastAPI classifier | Terpenuhi | Worker memanggil SpamAssassin melalui protokol spamd dan classifier melalui endpoint `/predict-dual`. |
| Scikit-learn/XGBoost + TF-IDF | Terpenuhi | Artefak runtime: XGBoost, `tfidf_latest.joblib`, scaler, serta FastAPI inference service. |
| Dilatih dari Enron/SpamAssassin corpus | **Belum terbukti / sebagian** | Dataset eksternal berisi corpus SpamAssassin dan artefak 3 kelas, tetapi artefak runtime berbeda dimensi dan label (lihat bagian dataset). |
| Inference asinkron dalam Docker melalui Redis | Terpenuhi | Service `worker`, `classifier`, `redis`, dan `smtp_receiver` didefinisikan di Compose; worker menjalankan SpamAssassin dan classifier secara async. |
| Heuristic domain inconsistency / typosquatting | Terpenuhi setelah perbaikan | Levenshtein dan URL parsing aktif. Domain organisasi tidak lagi hard-code `lodaya.id`; sekarang berbasis `PROTECTED_DOMAINS` atau `VITE_MAIL_DOMAIN`. |
| XAI `X-Spam-Reason` | Terpenuhi | Classifier menghasilkan alasan SHAP/heuristic dan forwarding menyertakan hasil scan pada header. |

## Temuan dataset dan artefak

Dataset pada `D:\tools\cyber-project\Data` berisi:

- `dataset-1`: 4.153 ham dan 1.899 spam pada folder corpus, serta `emails.csv`.
- Feature matrix: train `(50.321, 50.004)` dan test `(12.581, 50.004)`.
- Label: 3 kelas — ham `0`, spam `1`, phishing `2`.
- TF-IDF: 50.000 fitur + 4 metadata.
- Split: stratified, test 20%, random state 42.
- Dataset summary mencatat 70.384 baris dan 2.035 duplicate content keep-first.

Artefak yang dipakai classifier runtime:

- XGBoost binary `n_features_in_ = 50.020`, classes `[0, 1]`.
- TF-IDF vocabulary 50.000.
- Scaler dengan 20 fitur terstruktur.
- Dua model anomaly detector juga dimuat.

Perbedaan 50.004 vs 50.020 dan 3 kelas vs binary membuktikan bahwa dataset eksternal belum bisa dianggap sebagai sumber langsung artefak runtime. Mengganti artefak tanpa retraining/evaluasi akan berisiko membuat inference gagal atau mengubah arti label.

## Validasi yang telah dilakukan

- `docker compose --env-file .env --profile production config --quiet` berhasil.
- `docker compose --env-file .env --profile local config --quiet` berhasil.
- Classifier image berhasil dibangun ulang setelah perbaikan domain.
- `GET /health` classifier: supervised dan unsupervised loaded.
- `GET /model-info`: XGBoost 500 estimator, TF-IDF 50.000 vocabulary, 20 structured features.
- `POSTGRES_PORT=5432` tetap dipertahankan di `.env`; port override lokal tidak mengubah konfigurasi produksi.

## Tindakan wajib sebelum klaim final

1. Simpan skrip training reproducible yang membaca corpus pada `D:\tools\cyber-project\Data` (atau path dataset di VPS).
2. Tetapkan label contract: binary spam/ham atau multiclass ham/spam/phishing. Jangan mencampur keduanya.
3. Training ulang dengan pipeline inference yang sama persis (20 structured features bila memakai artefak runtime saat ini), lalu simpan metrics: precision, recall, F1 per kelas, confusion matrix, dataset hash, dan model version.
4. Jalankan evaluasi hold-out dan uji adversarial URL sebelum mempromosikan artefak ke `classifier/models`.
5. Mount artefak/model directory melalui deployment yang terversi; jangan mengandalkan file lokal developer.
6. Lengkapi bukti requirement umum proyek: screenshot alur, video penggunaan, user/admin manual, dan dokumentasi deployment.

