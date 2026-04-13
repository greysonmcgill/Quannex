#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

alembic upgrade head

uvicorn quan.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

cd dashboard
npm run dev
