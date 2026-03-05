#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"
HYP_DIR="$ROOT_DIR/services/hypothesis-room"

if [[ ! -d "$WEB_DIR" ]]; then
  echo "Missing web app at $WEB_DIR"
  exit 1
fi

if [[ ! -d "$HYP_DIR" ]]; then
  echo "Missing hypothesis service at $HYP_DIR"
  exit 1
fi

if [[ ! -d "$HYP_DIR/.venv" ]]; then
  echo "Python venv not found at $HYP_DIR/.venv"
  echo "Create it with: cd services/hypothesis-room && python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
  exit 1
fi

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$HYP_DIR"
  source .venv/bin/activate
  HOST=127.0.0.1 PORT=8000 python -m vreda_hypothesis.server
) &

(
  cd "$WEB_DIR"
  HOST=127.0.0.1 PORT=3000 npm run dev
) &

wait
