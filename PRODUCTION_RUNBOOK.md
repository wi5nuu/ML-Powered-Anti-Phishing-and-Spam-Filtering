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
- pastikan `DASHBOARD_DB_URL` dan `WORKER_DB_URL` memakai password yang sama dengan `DB_PASSWORD`
- buka firewall port `25`, `80`, dan `443`

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
