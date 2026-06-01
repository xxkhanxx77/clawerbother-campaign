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

PROFILE_DIR="output/playwright-profile-clean"
TODAY="$(date +%d-%m-%Y)"
SEVEN_DAYS_AGO="$(date -v-30d +%d-%m-%Y)"
rm -rf "$PROFILE_DIR"

exec ./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from "$TODAY" \
  --date-to "$SEVEN_DAYS_AGO" \
  --profile-dir "$PROFILE_DIR"
