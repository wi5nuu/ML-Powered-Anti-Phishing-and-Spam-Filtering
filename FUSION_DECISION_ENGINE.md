# Fusion Decision Engine Documentation

## Tujuan
File ini menjelaskan mekanisme decision fusion di sistem ML-Powered Anti-Phishing-and-Spam-Filtering, bukti kode, cara menjalankan, dan contoh hasil.

## 1. Logika Fusion
Sistem Anda menggunakan keputusan `3-way fusion` dari tiga skor:

- `ML probability` dari model supervised (Layer 1)
- `SpamAssassin` yang dinormalisasi (Layer 3)
- `Anomaly score` dari detector unsupervised (Layer 2)

Formula akhir yang digunakan:

```python
fused_score = ml_probability * 0.50 + sa_normalized * 0.25 + anomaly_score * 0.25
```

## 2. Bukti kode
File utama yang mengimplementasikan fusion adalah `decision_engine/fusion.py`.

Di dalamnya, bobot default ditetapkan sebagai:

```python
ML_WEIGHT = float(os.getenv("FUSION_ML_WEIGHT", "0.50"))
SA_WEIGHT = float(os.getenv("FUSION_SA_WEIGHT", "0.25"))
ANOMALY_WEIGHT = float(os.getenv("FUSION_ANOMALY_WEIGHT", "0.25"))
```

Dan perhitungan fusion dibuat di:

```python
fused = (
    (ml_probability * ML_WEIGHT) +
    (sa_normalized * SA_WEIGHT) +
    (anomaly_score * ANOMALY_WEIGHT)
)
```

## 3. Normalisasi SpamAssassin
SpamAssassin score (`sa_score`) dinormalisasi ke rentang [0,1] dengan membagi oleh nilai maksimum 20:

```python
sa_clamped = max(0.0, min(sa_score, SA_MAX_SCORE))
sa_normalized = sa_clamped / SA_MAX_SCORE
```

## 4. Hard override rules
Sistem juga memiliki kondisi langsung `QUARANTINE` sebelum fusion jika salah satu nilai berikut terpenuhi:

- `SA >= 15.0`
- `ML >= 0.95`
- `Anomaly >= 0.90`

Bukti kode:

```python
if sa_score >= SA_HARD_LIMIT or ml_probability >= ML_HARD_LIMIT or anomaly_score >= ANOMALY_HARD_LIMIT:
    return FusionResult(... label="QUARANTINE")
```

## 5. Routing hasil fusion
Setelah `fused_score` dihitung, routing dilakukan berdasarkan threshold:

- `< 0.30` → `CLEAN`
- `0.30 - 0.70` → `WARN`
- `>= 0.70` → `QUARANTINE`

## 6. Jalur eksekusi di sistem Anda
Jalur tersebut dijalankan di `worker/pipeline_worker.py`:

1. `score_with_spamassassin(raw_email)` menghasilkan `sa_score`
2. `score_with_ml(raw_email, ...)` menghasilkan `ml_probability` dan `anomaly_score`
3. `fuse(...)` menggabungkan skor menjadi `FusionResult`
4. Hasil fusion disimpan ke DB dengan label dan `fused_score`

Contoh kode pemanggil:

```python
fusion = fuse(
    sa_score=sa_score,
    ml_probability=ml_prob,
    anomaly_score=anomaly_score,
    spf_pass=spf_pass,
    dkim_pass=dkim_pass,
    dmarc_pass=dmarc_pass,
)
```

## 7. Cara run untuk membuktikan
### A. Jalankan modul fusion langsung
Buka terminal di root repo, lalu jalankan Python interactive atau skrip:

```bash
cd "d:/ML-Powered Anti-Phishing and Spam Filtering/lti-antiphishing"
python -c "from decision_engine.fusion import fuse; print(fuse(sa_score=8.0, ml_probability=0.65, anomaly_score=0.40, spf_pass=True, dkim_pass=True, dmarc_pass=True))"
```

### B. Contoh output yang diharapkan
Dengan input:
- `ML = 0.65`
- `SA = 8.0` → `sa_normalized = 0.40`
- `Anomaly = 0.40`

Perhitungan:

```text
fused_score = 0.65*0.50 + 0.40*0.25 + 0.40*0.25 = 0.525
```

Label yang dihasilkan:
- `WARN`

## 8. Contoh testing script
Berikut skrip contoh untuk memastikan fungsi fusion bekerja:

```python
from decision_engine.fusion import fuse

result = fuse(
    sa_score=8.0,
    ml_probability=0.65,
    anomaly_score=0.40,
    spf_pass=True,
    dkim_pass=True,
    dmarc_pass=True,
)
print(result)
```

### 9. Hasil nyata di sistem
Hasil sebenarnya disimpan dalam database `QuarantineEmail` dalam `worker/pipeline_worker.py` dengan field:
- `fused_score`
- `label`
- `sa_score`
- `ml_probability`
- `anomaly_score`
- `routing_reason`

## 10. Kesimpulan
Bukti nyata dari sistem Anda:
- formula fusion di `decision_engine/fusion.py`
- eksekusi di `worker/pipeline_worker.py`
- dokumentasi dalam `README.md`
- battle-tested rule override untuk langsung karantina

File ini dibuat sebagai dokumentasi resmi untuk menjelaskan dan membuktikan logika fusion di sistem Anda.
