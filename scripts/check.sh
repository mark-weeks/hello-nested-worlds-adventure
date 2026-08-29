#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if [ ! -x .venv/bin/python ]; then
  echo "Run ./setup.sh first; .venv is missing." >&2
  exit 1
fi

.venv/bin/ruff check .
.venv/bin/python -m pytest tests/ -q
npm test --prefix frontend
bundle_before="$(find static/app -type f -exec cksum {} \; | sort)"
npm run build --prefix frontend
bundle_after="$(find static/app -type f -exec cksum {} \; | sort)"
if [ "$bundle_before" != "$bundle_after" ]; then
  echo "static/app was stale; commit the freshly rebuilt bundle and rerun." >&2
  exit 1
fi
.venv/bin/python scripts/verify_wheel.py

if [ "${ENFOLDED_E2E:-0}" = "1" ]; then
  # Absolute path: Playwright launches the webServer from frontend/, where
  # a repo-relative .venv/bin/python does not resolve (exit 127) — this
  # line had never actually run before batch 2 (batch 1's containers had
  # no Chromium, and CI installs the package into its runner python).
  ENFOLDED_PYTHON="$repo_dir/.venv/bin/python" npm run test:e2e --prefix frontend
else
  echo "Browser E2E skipped locally; set ENFOLDED_E2E=1 after installing Chromium."
fi
