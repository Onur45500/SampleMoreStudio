#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Creating Python venv"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

echo "==> Generating task suites"
python scripts/cli.py generate-tasks

echo "==> Installing frontend deps"
(cd frontend && npm install)

echo ""
echo "Setup complete."
echo "  Terminal 1: source .venv/bin/activate && uvicorn backend.main:app --reload --port 8000"
echo "  Terminal 2: cd frontend && npm run dev"
echo "  Phase 0:    source .venv/bin/activate && python scripts/cli.py phase0"
echo ""
echo "Ensure Ollama is running with: ollama pull qwen2.5:7b"
