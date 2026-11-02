#!/usr/bin/env bash
# Fail closed when off-host backup is required and the Fly token or the private
# bucket is missing. A typo is a configuration error, not a silent no-op.
# Nothing here prints a credential. There is no GitHub-artifact fallback.
set -euo pipefail

case "${BACKUP_REQUIRED:-false}" in
  true|false) ;;
  *) echo '::error::ENFOLDED_BACKUP_REQUIRED must be true, false, or unset.' >&2; exit 2 ;;
esac

retention="${ENFOLDED_BACKUP_RETENTION_DAYS:-}"
if [ -z "$retention" ]; then
  # Example only; Mark has not chosen a retention (ADR-034 §5).
  retention=30
elif ! [[ "$retention" =~ ^[1-9][0-9]{0,3}$ ]] || [ "$retention" -gt 3650 ]; then
  echo '::error::ENFOLDED_BACKUP_RETENTION_DAYS must be an integer from 1 to 3650, or unset.' >&2
  exit 2
fi

region="${ENFOLDED_BACKUP_S3_REGION:-auto}"
if ! [[ "$region" =~ ^[a-z0-9][a-z0-9-]{0,31}$ ]]; then
  echo '::error::ENFOLDED_BACKUP_S3_REGION must be a short lowercase name such as auto or us-east-1.' >&2
  exit 2
fi

app="${FLY_APP:-}"
if [ -n "$app" ] && ! [[ "$app" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]]; then
  echo '::error::ENFOLDED_BACKUP_APP must be the exact Fly app name.' >&2
  exit 2
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$root${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PY'
import os
import sys
from scripts.backup_store import gate_problems
problems = gate_problems(os.environ)
for problem in problems:
    print('::error::' + problem, file=sys.stderr)
sys.exit(2 if problems else 0)
PY

missing=""
add_missing() {
  if [ -z "$2" ]; then
    missing="${missing:+$missing, }$1"
  fi
}
add_missing FLY_API_TOKEN "${FLY_API_TOKEN:-}"
add_missing ENFOLDED_BACKUP_S3_ACCESS_KEY_ID "${ENFOLDED_BACKUP_S3_ACCESS_KEY_ID:-}"
add_missing ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY "${ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY:-}"
add_missing ENFOLDED_BACKUP_S3_BUCKET "${ENFOLDED_BACKUP_S3_BUCKET:-}"
add_missing ENFOLDED_BACKUP_S3_ENDPOINT "${ENFOLDED_BACKUP_S3_ENDPOINT:-}"

if [ -n "$missing" ]; then
  if [ "${BACKUP_REQUIRED:-false}" = true ]; then
    echo "::error::Off-host backup is required, but configuration is missing: ${missing}." >&2
    exit 1
  fi
  echo 'ready=no' >> "$GITHUB_OUTPUT"
  echo '::warning::Backup is inactive before deployment; this run is not recovery evidence.'
  echo "Backup inactive: missing ${missing}. No snapshot was uploaded." >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
echo 'ready=yes' >> "$GITHUB_OUTPUT"
