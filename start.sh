#!/usr/bin/env bash
# ── K — Voice Assistant startup script ────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
ENV_FILE="$ROOT/.env"

# ── Check .env ─────────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo ""
  echo "  .env not found."
  echo "  Copy the template and fill in your keys:"
  echo ""
  echo "    cp .env.example .env"
  echo "    open .env"
  echo ""
  exit 1
fi

# ── Create venv if missing ─────────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
  echo "→ Creating virtual environment…"
  python3 -m venv "$VENV"
fi

# ── Install / sync dependencies ────────────────────────────────────────────
echo "→ Installing dependencies…"
"$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"

# ── Harden tokens directory ────────────────────────────────────────────────
mkdir -p "$ROOT/tokens"
chmod 700 "$ROOT/tokens"

# ── Launch server ──────────────────────────────────────────────────────────
PORT="${PORT:-8000}"
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  K — Voice Assistant                 ║"
echo "  ║  http://localhost:${PORT}              ║"
echo "  ║  Open in Chrome or Edge              ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

PYTHONPATH="$ROOT" \
  exec "$VENV/bin/uvicorn" backend.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --reload \
    --log-level info
