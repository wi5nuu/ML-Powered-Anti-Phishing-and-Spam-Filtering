# Setup Gmail untuk Kirim/Reply/Forward Email

## Masalah yang Diperbaiki

Sebelumnya, tombol kirim/reply/forward di page user hanya menyimpan email ke database tanpa benar-benar mengirim ke Gmail. Sekarang sudah diperbaiki dengan integrasi SMTP Gmail yang sebenarnya.

## Langkah Setup Gmail

### 1. Aktifkan 2-Step Verification di Gmail

1. Buka https://myaccount.google.com/security
2. Scroll ke bagian **"How you sign in to Google"**
3. Klik **"2-Step Verification"** → **"Get Started"**
4. Ikuti instruksi untuk mengaktifkan verifikasi 2 langkah

### 2. Generate App Password untuk SMTP

1. Buka https://myaccount.google.com/apppasswords
2. Di dropdown **"Select app"**, pilih **"Mail"**
3. Di dropdown **"Select device"**, pilih **"Other (Custom name)"**
4. Ketik nama: `CogniMail SMTP`
5. Klik **"Generate"**
6. **COPY** password 16-digit yang muncul (format: `xxxx xxxx xxxx xxxx`)
7. Simpan password ini, Anda tidak bisa melihatnya lagi

### 3. Isi Konfigurasi di File .env

Buka file `.env` di folder root project, lalu isi bagian **Gmail SMTP Configuration**:

```env
# ── Gmail SMTP Configuration (untuk kirim/reply/forward email) ──────────────────
FORWARDER_SMTP_HOST=smtp.gmail.com
FORWARDER_SMTP_PORT=587
FORWARDER_SMTP_USER=emailanda@gmail.com
FORWARDER_SMTP_PASS=xxxx xxxx xxxx xxxx
FORWARDER_FROM=emailanda@gmail.com
FORWARDER_STARTTLS=true
OUTBOUND_SMTP_MODE=relay
```

**Ganti:**
- `emailanda@gmail.com` → email Gmail Anda yang sebenarnya
- `xxxx xxxx xxxx xxxx` → App Password 16-digit dari langkah 2 (hapus spasi atau biarkan ada spasi, keduanya work)

### 4. Restart Dashboard Server

Setelah mengisi `.env`, restart server dashboard:

```bash
# Jika menggunakan Docker
docker-compose restart dashboard

# Jika menjalankan langsung
cd dashboard
python run_dev.py
```

## Testing

1. Login ke dashboard user page
2. Buka email apapun
3. Klik tombol **"Reply"** atau **"Forward"**
4. Tulis pesan dan klik **"Send"**
5. Cek inbox Gmail Anda di HP → **email seharusnya sudah terkirim**

## Fitur yang Sekarang Berfungsi

✅ **Kirim Email Baru** - Compose dan kirim email ke alamat manapun
✅ **Reply Email** - Balas email dengan quoted text dan thread tracking
✅ **Reply All** - Balas ke semua penerima di thread
✅ **Forward Email** - Teruskan email ke orang lain dengan attachment
✅ **Attachment Support** - Kirim file attachment hingga 20 file
✅ **HTML Email** - Otomatis detect dan kirim sebagai HTML jika body mengandung formatting
✅ **Error Handling** - Jika gagal kirim, notifikasi masuk ke inbox dengan alasan error

## Troubleshooting

### Error: "Authentication failed"
- Pastikan App Password benar (bukan password Gmail biasa)
- Pastikan 2-Step Verification sudah aktif
- Coba generate ulang App Password baru

### Error: "Connection timed out"
- Pastikan internet stabil
- Pastikan firewall tidak memblokir port 587
- Coba ganti `FORWARDER_SMTP_PORT=587` ke `465` dan set `use_tls=True`

### Email tidak terkirim tapi tidak ada error
- Cek Gmail Sent folder
- Cek log server: `docker-compose logs dashboard`
- Pastikan `FORWARDER_SMTP_HOST` tidak kosong

### Email masuk ke Spam
- Tambahkan SPF record di DNS domain Anda
- Gunakan email pengirim yang sama dengan SMTP user

## Security Notes

⚠️ **JANGAN COMMIT** file `.env` ke Git repository
⚠️ **JANGAN SHARE** App Password ke siapapun
⚠️ App Password hanya untuk aplikasi ini, bukan untuk login manual
⚠️ Jika App Password leaked, revoke di https://myaccount.google.com/apppasswords

## Kode yang Diperbaiki

File yang dimodifikasi:
1. `.env` - Ditambah konfigurasi Gmail SMTP
2. `dashboard/app.py:2165-2177` - Ditambah support HTML email body

Kode pengiriman SMTP sudah ada di `dashboard/app.py:2155-2188` dan berfungsi dengan baik.
