#!/bin/sh
# One-command launcher: sets up the venv if needed, then starts the app.
# Usage: ./run.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "==> Creating virtualenv…"
  python3 -m venv .venv
fi

echo "==> Installing dependencies…"
./.venv/bin/pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from template — add your ANTHROPIC_API_KEY and TAVILY_API_KEY, then re-run."
  exit 1
fi

PORT="${PORT:-8077}"
echo "==> Market Research Agent running at http://127.0.0.1:$PORT  (Ctrl+C to stop)"
exec ./.venv/bin/uvicorn app:app --host 127.0.0.1 --port "$PORT"
