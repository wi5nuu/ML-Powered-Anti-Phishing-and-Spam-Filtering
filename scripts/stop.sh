#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-production}"
if [[ "$PROFILE" != "local" && "$PROFILE" != "production" ]]; then
  echo "Usage: ./scripts/stop.sh [local|production]" >&2
  exit 1
fi

cd "$(dirname "$0")/.."
if [[ "$PROFILE" == "production" ]]; then
  export ENV="production"
  export SMTP_PUBLIC_PORT="25"
else
  export ENV="local"
  export SMTP_PUBLIC_PORT="2525"
fi

docker compose --env-file .env --profile "$PROFILE" down
