# CogniMail Runbook

Sistem sekarang memakai satu file environment dan satu file Docker Compose:

- `.env`
- `docker-compose.yml`

File yang sama dipakai untuk lokal Windows maupun Ubuntu VPS. Perbedaannya hanya profil Docker:

- `local` untuk laptop/PC development
- `production` untuk VPS

## Local Windows

Jalankan dari PowerShell di root project:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\start.ps1 -Profile local -Build
```

URL lokal:

```text
Dashboard   http://localhost:8080
Classifier  http://localhost:8001/health
Grafana     http://localhost:3000
Prometheus  http://localhost:9090
Mailpit     http://localhost:8025
SMTP local  localhost:2525
```

Stop:

```powershell
.\scripts\stop.ps1 -Profile local
```

## Ubuntu VPS

Sebelum production, edit `.env`:

- ganti semua domain `example.com`
- set `SMTP_PUBLIC_PORT=25`
- pilih mode SMTP outbound untuk kirim, balas, dan forward mailbox.

  Untuk mengirim langsung dari VPS ke MX penerima:

  ```dotenv
  OUTBOUND_SMTP_MODE=direct
  OUTBOUND_HELO_HOSTNAME=cognimail.zenime.my.id
  OUTBOUND_SMTP_TIMEOUT=30
  ```

  Pada mode `direct`, `FORWARDER_FROM` tidak diperlukan. Setiap compose, reply,
  dan automatic forward menggunakan alamat mailbox terkait sebagai envelope
  sender. Contoh: email yang masuk ke `bantuan@zenime.my.id` dan diteruskan ke
  Gmail tetap dikirim oleh `bantuan@zenime.my.id`, sedangkan mailbox
  `sales@zenime.my.id` memakai `sales@zenime.my.id`. Tujuan forward disimpan
  per mailbox dari halaman admin, sehingga setiap mailbox dapat mempunyai
  tujuan yang berbeda.

  Mode langsung memerlukan akses keluar TCP port 25, PTR/rDNS IP VPS yang sama
  dengan `OUTBOUND_HELO_HOSTNAME`, serta SPF yang mengizinkan IP VPS. Untuk
  automatic forward, envelope sender akan memakai alamat mailbox CogniMail.

  Verifikasi koneksi outbound dari VPS sebelum deploy:

  ```bash
  nc -vz gmail-smtp-in.l.google.com 25
  ```

  Untuk IP `167.86.112.96`, ubah PTR/rDNS melalui panel provider VPS menjadi
  `cognimail.zenime.my.id`. Pastikan record A hostname tersebut tetap kembali
  ke IP yang sama. Tanpa forward-confirmed reverse DNS, server seperti Gmail
  dapat menolak atau menandai pesan sebagai spam.

  Alternatifnya, untuk memakai relay SMTP eksternal:

  ```dotenv
  OUTBOUND_SMTP_MODE=relay
  FORWARDER_SMTP_HOST=smtp.provider.example
  FORWARDER_SMTP_PORT=587
  FORWARDER_STARTTLS=true
  FORWARDER_SMTP_USER=bantuan@zenime.my.id
  FORWARDER_SMTP_PASS=app-password-atau-password-smtp
  FORWARDER_FROM=bantuan@zenime.my.id
  ```

  Gunakan port `465` bila provider meminta implicit TLS; untuk port `465`, set
  `FORWARDER_STARTTLS=false`. Akun relay harus diizinkan mengirim menggunakan
  alamat mailbox yang dipilih di CogniMail. `FORWARDER_FROM` pada mode relay
  adalah fallback akun relay dan tidak dipakai sebagai identitas global pada
  mode `direct`.
- pastikan `DASHBOARD_DB_URL` dan `WORKER_DB_URL` memakai password yang sama dengan `DB_PASSWORD`
- ganti `ADMIN_PASSWORD`, `SUPERADMIN_PASSWORD`, `USER_PASSWORD`, dan
  `DASHBOARD_SECRET_KEY` dengan nilai acak yang kuat. Dashboard sengaja menolak
  startup production bila masih memakai nilai bawaan.
- buka firewall port `25`, `80`, dan `443`

Jika HTTPS ditangani Nginx di host VPS, proxy WebSocket `/ws` juga harus
diteruskan. Tanpa blok ini, pembaruan inbox real-time mendapat respons 404:

```nginx
location /ws {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Deploy:

```bash
chmod +x scripts/start.sh scripts/stop.sh
./scripts/start.sh production --build
```

Stop:

```bash
./scripts/stop.sh production
```

## Perintah Manual

Local:

```bash
docker compose --env-file .env --profile local up -d --build
```

Production:

```bash
docker compose --env-file .env --profile production up -d --build
```

Cek status:

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs -f dashboard
docker compose --env-file .env logs -f classifier
docker compose --env-file .env logs -f worker
```

Tes kirim/balas langsung sambil memantau hasil SMTP:

```bash
docker compose logs -f dashboard worker
```

Pesan hanya dibuat sebagai `SENT` setelah MX penerima menerima transaksi SMTP.
Automatic forward hanya berlaku untuk email baru dan mailbox yang forwarder-nya
sudah diaktifkan dari dashboard admin.

## Login

Login sementara untuk lokal:

```text
super     / super     -> superadmin
admin     / admin     -> admin
user      / user      -> user
```

Ganti password ini sebelum production.

## Catatan Deploy

Jangan upload dependency lokal ke VPS:

```text
.venv/
dashboard/frontend/node_modules/
*.db
logs/
screenshots/
```

Docker build sudah mengabaikan file tersebut lewat `.dockerignore`.
