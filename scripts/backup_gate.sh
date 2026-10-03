#!/usr/bin/env bash
set -euo pipefail

case "${BACKUP_REQUIRED:-false}" in
  true|false) ;;
  *) echo '::error::ENFOLDED_BACKUP_REQUIRED must be true, false, or unset.'; exit 2 ;;
esac
if [ -n "${FLY_API_TOKEN:-}" ]; then
  echo 'ready=yes' >> "$GITHUB_OUTPUT"
elif [ "${BACKUP_REQUIRED:-false}" = true ]; then
  echo '::error::Off-host backup is required, but FLY_API_TOKEN is unavailable.'
  exit 1
else
  echo 'ready=no' >> "$GITHUB_OUTPUT"
  echo '::warning::Backup is inactive before deployment; this run is not recovery evidence.'
  echo 'Backup inactive: no snapshot or off-host artifact was produced.' >> "$GITHUB_STEP_SUMMARY"
fi
