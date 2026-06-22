# User Manual — LTI Anti-Phishing Dashboard

## Akses Dashboard

Buka browser dan akses: `http://localhost:8081` (Docker: `http://localhost:8080`)

## Halaman Karantina

Menampilkan semua email yang dikarantina atau masuk kategori WARN.
Anda bisa:

- **Lihat detail** — klik Email ID untuk melihat penjelasan lengkap
- **Lepaskan** — kirim email ke inbox jika ternyata bukan spam
- **Konfirmasi Spam** — tandai email sebagai spam yang benar
- **Laporkan False Positive** — laporkan jika sistem salah mengkarantina

## Halaman Detail

Menampilkan skor lengkap:
- Skor SpamAssassin (rule-based)
- Probabilitas ML (AI model)
- Skor akhir gabungan
- Penjelasan dalam bahasa manusia mengapa email ini dikarantina

## Halaman Metrik

Menampilkan statistik:
- Total email diproses
- Jumlah dikarantina vs peringatan
- Top 10 pengirim terblokir
- Distribusi label

## Tips

- Jika ragu, klik "Laporkan False Positive" daripada "Lepaskan"
- Data false positive otomatis dikumpulkan untuk perbaikan model
