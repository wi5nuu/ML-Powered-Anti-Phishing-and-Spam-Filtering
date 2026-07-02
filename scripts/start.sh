#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-production}"
if [[ "$PROFILE" != "local" && "$PROFILE" != "production" ]]; then
  echo "Usage: ./scripts/start.sh [local|production] [--build]" >&2
  exit 1
fi

BUILD="false"
if [[ "${2:-}" == "--build" ]]; then
  BUILD="true"
fi

cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker belum terinstall. Install Docker Engine dan Docker Compose plugin terlebih dahulu." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  if command -v systemctl >/dev/null 2>&1; then
    echo "Starting Docker service..."
    sudo systemctl start docker
  fi
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon belum berjalan atau user belum punya akses Docker." >&2
  echo "Coba: sudo usermod -aG docker \$USER && newgrp docker" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo ".env tidak ditemukan. Buat .env terlebih dahulu sebelum menjalankan stack." >&2
  exit 1
fi

if [[ "$PROFILE" == "production" ]]; then
  if grep -q "example.com\\|CHANGE_ME" .env; then
    echo ".env masih berisi example.com atau CHANGE_ME. Ganti domain/secret sebelum deploy production." >&2
    exit 1
  fi
  export ENV="production"
  export SMTP_PUBLIC_PORT="25"
else
  export ENV="local"
  export SMTP_PUBLIC_PORT="2525"
fi

if [[ "$BUILD" == "true" ]]; then
  docker compose --env-file .env --profile "$PROFILE" build
fi

docker compose --env-file .env --profile "$PROFILE" up -d
docker compose --env-file .env --profile "$PROFILE" ps
