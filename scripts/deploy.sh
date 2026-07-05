#!/usr/bin/env bash
# Deploy Enfolded to Fly.io with the continuity policy built in:
# an online backup of the world chronicle is ALWAYS the first step, so a
# bad migration is a restore, not a lost epoch.
# See docs/roadmap/phase-2-scale.md (continuity policy) and
# docs/infrastructure/fly-deployment.md (runbook).
#
# Usage:
#   scripts/deploy.sh                 # backup, prune old backups, deploy
#   scripts/deploy.sh --first-deploy  # skip backup (no machine running yet)
#   FLY_APP=my-app scripts/deploy.sh  # target a differently named app
set -euo pipefail

APP="${FLY_APP:-nested-worlds-beta}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
KEEP=5

if [[ "${1:-}" == "--first-deploy" ]]; then
    echo "==> First deploy: no machine to back up, going straight to fly deploy"
else
    echo "==> [1/3] Online backup of the chronicle (continuity policy)"
    if ! fly ssh console -a "$APP" -C \
        "python main.py backup --to /data/backups/worlds-${STAMP}.db"; then
        echo "!! Backup failed — refusing to deploy over an unbacked chronicle." >&2
        echo "!! If this is the very first deploy, rerun with --first-deploy." >&2
        exit 1
    fi

    echo "==> [2/3] Pruning machine-local backups (keeping newest ${KEEP})"
    # Best-effort: a failed prune must never block the deploy.
    fly ssh console -a "$APP" -C \
        "sh -c 'ls -t /data/backups/*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm'" \
        || echo "   (prune skipped)"
fi

echo "==> [3/3] fly deploy"
fly deploy -a "$APP"

echo
echo "Deployed. To stream today's backup off-host:"
echo "  fly ssh sftp get /data/backups/worlds-${STAMP}.db ./local-backups/"
