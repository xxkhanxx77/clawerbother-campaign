#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run setup first:"
  echo "  python3 -m venv .venv"
  echo "  ./.venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

exec ./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
