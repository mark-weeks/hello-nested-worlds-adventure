#!/usr/bin/env bash
# Deploy Enfolded to Fly.io with the continuity policy built in:
# an online backup of the world chronicle is ALWAYS the first step, so a
# bad migration is a restore, not a lost epoch. A same-schema rollback
# redeploys a pinned image only when that image ships the live chronicle's
# schema. A newer chronicle is never booted with an older binary.
# See docs/roadmap/phase-2-scale.md (continuity policy),
# docs/infrastructure/fly-deployment.md (runbook), and
# docs/infrastructure/delivery-recovery.md (upgrade and rollback).
#
# Usage:
#   scripts/deploy.sh                     # backup, schema check, prune, deploy
#   scripts/deploy.sh --first-deploy      # skip backup (no machine running yet)
#   scripts/deploy.sh --rollback <image>  # same-schema redeploy of a pinned image
#   scripts/deploy.sh --help
#   FLY_APP=my-app scripts/deploy.sh      # target a differently named app
#   FLY_BIN=/path/to/fly scripts/deploy.sh
#
# Fly flags (docs.fly.io flyctl, read 2026-11-06):
#   fly deploy -a APP --image IMAGE     -i/--image is "The Docker image to deploy"
#   fly releases -a APP --image         shows each release's image reference
#   fly machine run IMAGE --rm          one-off; --rm sets restart to never
# The schema probe passes no --volume and no --port, so it does not mount
# the chronicle and does not join the public proxy.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# An explicit empty FLY_APP is a mistake, not a request for the default.
APP="${FLY_APP-enfolded-beta}"
FLY_BIN="${FLY_BIN:-fly}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
KEEP=5
PROBE_FILE="$repo_root/scripts/schema_probe.py"

usage() {
    cat <<'EOF'
Usage:
  scripts/deploy.sh
  scripts/deploy.sh --first-deploy
  scripts/deploy.sh --rollback <image-ref>
  scripts/deploy.sh --help

Environment:
  FLY_APP   Fly app name (default: enfolded-beta)
  FLY_BIN   flyctl binary (default: fly). A test may point this at a stub.

--first-deploy skips the chronicle backup. Use it only when no machine
is running yet.

--rollback redeploys an already-built image on the SAME schema. It backs
up the chronicle first and refuses to continue if that backup fails. It
then refuses when the image's shipped schema differs from the live
schema_version. A cross-schema downgrade is a disaster restore: stop and
restore the matching pre-upgrade backup (docs/infrastructure/fly-deployment.md).
That restore abandons history written after the backup. There is no
in-place binary downgrade.

Find the image ref with: fly releases -a "$FLY_APP" --image
EOF
}

die() {
    echo "error: $*" >&2
    exit 2
}

validate_image() {
    local ref="$1"
    if [[ -z "$ref" ]]; then
        die "--rollback image ref is empty"
    fi
    if [[ "$ref" == -* ]]; then
        die "image ref must not look like a flag: ${ref}"
    fi
    if [[ "$ref" == *[[:space:]]* ]]; then
        die "image ref must not contain whitespace"
    fi
    # Registry path only. Reject shell metacharacters and flag injection.
    # A Fly release image looks like registry.fly.io/<app>:<tag>
    # or registry.fly.io/<app>@sha256:<64 hex>.
    if [[ ! "$ref" =~ ^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,254}$ ]]; then
        die "image ref contains characters that are not allowed"
    fi
    if [[ "$ref" == *".."* ]]; then
        die "image ref must not contain .."
    fi
    if [[ "$ref" != */* ]]; then
        die "image ref must be a registry path (registry/name[:tag])"
    fi
    if [[ "$ref" == *@* ]]; then
        if [[ ! "$ref" =~ ^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[a-fA-F0-9]{64}$ ]]; then
            die "digest image ref must end in @sha256:<64 hex digits>"
        fi
    fi
}

choose_python() {
    if [[ -n "${PY:-}" ]]; then
        return
    fi
    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        echo "error: python3 is required to read schema versions" >&2
        exit 1
    fi
}

probe_b64() {
    choose_python
    "$PY" -c 'import base64, pathlib, sys; print(base64.b64encode(pathlib.Path(sys.argv[1]).read_bytes()).decode("ascii"))' \
        "$PROBE_FILE"
}

# One distinct integer from a fly command's mixed output. Repeated copies
# of the same sentinel are accepted. Two different values are a refusal.
sentinel_value() {
    local name="$1"
    local text="$2"
    local line rest token seen=""
    local -a values=()
    while IFS= read -r line || [[ -n "$line" ]]; do
        rest="$line"
        while [[ "$rest" =~ ${name}=([0-9]+) ]]; do
            token="${BASH_REMATCH[1]}"
            if [[ " ${seen} " != *" ${token} "* ]]; then
                seen+=" ${token}"
                values+=("$token")
            fi
            rest="${rest#*"${name}=${token}"}"
        done
    done <<< "$text"
    if [[ "${#values[@]}" -ne 1 ]]; then
        return 1
    fi
    printf '%s\n' "$((10#${values[0]}))"
}

fly_capture() {
    local out
    if ! out="$("$@" 2>&1)"; then
        printf '%s\n' "$out"
        return 1
    fi
    printf '%s\n' "$out"
}

read_applied_schema() {
    local b64 out applied
    b64="$(probe_b64)"
    # python3 is the image interpreter (python:3.11-slim). The backup
    # command stays `python main.py`, which that image also provides.
    if ! out="$(fly_capture "$FLY_BIN" ssh console -a "$APP" -C \
        "ENFOLDED_SCHEMA_PROBE=applied python3 -c \"exec(__import__('base64').b64decode('${b64}'))\"")"; then
        echo "!! Could not read the live chronicle schema; refusing to continue." >&2
        printf '%s\n' "$out" >&2
        return 1
    fi
    if ! applied="$(sentinel_value ENFOLDED_SCHEMA_APPLIED "$out")"; then
        echo "!! Live schema probe did not report one schema version; refusing to continue." >&2
        printf '%s\n' "$out" >&2
        return 1
    fi
    printf '%s\n' "$applied"
}

read_image_schema() {
    local image="$1"
    local b64 out known py_exec
    b64="$(probe_b64)"
    py_exec="exec(__import__('base64').b64decode('${b64}'))"
    # --entrypoint python3 so the image CMD (enfolded serve) cannot run.
    # No --volume and no --port: the probe does not mount /data and does
    # not join the app's HTTP service. --rm destroys the machine on exit.
    if ! out="$(fly_capture "$FLY_BIN" machine run "$image" \
        --app "$APP" \
        --rm \
        --restart no \
        --skip-dns-registration \
        --entrypoint python3 \
        -e ENFOLDED_SCHEMA_PROBE=known \
        -- \
        -c "$py_exec")"; then
        echo "!! Could not read the image schema; refusing to roll back." >&2
        printf '%s\n' "$out" >&2
        return 1
    fi
    if ! known="$(sentinel_value ENFOLDED_SCHEMA_KNOWN "$out")"; then
        echo "!! Image schema probe did not report one schema version; refusing to roll back." >&2
        printf '%s\n' "$out" >&2
        return 1
    fi
    printf '%s\n' "$known"
}

read_checkout_schema() {
    local out known
    choose_python
    if ! out="$(ENFOLDED_SCHEMA_PROBE=known \
        ENFOLDED_MIGRATIONS_DIR="$repo_root/persistence/migrations" \
        "$PY" "$PROBE_FILE" 2>&1)"; then
        echo "!! Could not read this checkout's schema version; refusing to deploy." >&2
        printf '%s\n' "$out" >&2
        return 1
    fi
    if ! known="$(sentinel_value ENFOLDED_SCHEMA_KNOWN "$out")"; then
        echo "!! Checkout schema probe did not report one schema version; refusing to deploy." >&2
        printf '%s\n' "$out" >&2
        return 1
    fi
    printf '%s\n' "$known"
}

refuse_older_binary() {
    local what="$1" known="$2" applied="$3"
    echo "!! Refusing: ${what} schema ${known} is older than the live chronicle schema ${applied}." >&2
    echo "!! Migrations are forward-only. An older binary must not boot against this database." >&2
    echo "!! Stop. A cross-schema downgrade is a disaster restore, not a release rollback." >&2
    echo "!! Restore the backup taken before the upgrade (docs/infrastructure/fly-deployment.md, \"Restoring from a backup\")." >&2
    echo "!! That restore abandons history written after the backup. There is no in-place downgrade." >&2
    echo "!! The chronicle backup was kept on the machine at /data/backups/worlds-${STAMP}.db." >&2
    exit 1
}

backup_chronicle() {
    echo "==> Online backup of the chronicle (continuity policy)"
    if ! "$FLY_BIN" ssh console -a "$APP" -C \
        "python main.py backup --to /data/backups/worlds-${STAMP}.db"; then
        echo "!! Backup failed — refusing to continue over an unbacked chronicle." >&2
        echo "!! If this is the very first deploy, rerun with --first-deploy." >&2
        exit 1
    fi
}

prune_backups() {
    echo "==> Pruning machine-local backups (keeping newest ${KEEP})"
    # Best-effort: a failed prune must never block the deploy.
    "$FLY_BIN" ssh console -a "$APP" -C \
        "sh -c 'ls -t /data/backups/*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm'" \
        || echo "   (prune skipped)"
}

mode="deploy"
image=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            if [[ $# -ne 1 || -n "$image" || "$mode" != "deploy" ]]; then
                die "--help takes no other arguments"
            fi
            usage
            exit 0
            ;;
        --first-deploy)
            if [[ "$mode" == "rollback" ]]; then
                die "--first-deploy cannot be combined with --rollback"
            fi
            if [[ "$mode" == "first" ]]; then
                die "--first-deploy given more than once"
            fi
            mode="first"
            shift
            ;;
        --rollback)
            if [[ "$mode" == "first" ]]; then
                die "--first-deploy cannot be combined with --rollback"
            fi
            if [[ "$mode" == "rollback" ]]; then
                die "--rollback given more than once"
            fi
            if [[ $# -lt 2 ]]; then
                die "--rollback requires an image ref"
            fi
            mode="rollback"
            image="$2"
            shift 2
            ;;
        --)
            die "unexpected argument"
            ;;
        -*)
            die "unknown flag: $1"
            ;;
        *)
            die "unexpected argument: $1"
            ;;
    esac
done

if [[ -z "$APP" ]]; then
    die "FLY_APP is empty"
fi
if [[ -z "$FLY_BIN" ]]; then
    die "FLY_BIN is empty"
fi
if [[ "$mode" == "rollback" ]]; then
    validate_image "$image"
fi

if [[ "$mode" == "first" ]]; then
    echo "==> First deploy: no machine to back up, going straight to fly deploy"
    echo "==> fly deploy"
    "$FLY_BIN" deploy -a "$APP"
    echo
    echo "Deployed (first deploy, no chronicle backup)."
    exit 0
fi

backup_chronicle

if [[ "$mode" == "rollback" ]]; then
    echo "==> Schema check: image must ship the live chronicle schema"
    if ! applied="$(read_applied_schema)"; then
        echo "!! The chronicle backup was kept on the machine at /data/backups/worlds-${STAMP}.db." >&2
        exit 1
    fi
    if ! known="$(read_image_schema "$image")"; then
        echo "!! The chronicle backup was kept on the machine at /data/backups/worlds-${STAMP}.db." >&2
        exit 1
    fi
    if (( known < applied )); then
        refuse_older_binary "image" "$known" "$applied"
    fi
    if (( known > applied )); then
        echo "!! Refusing rollback: image schema ${known} is newer than the live chronicle schema ${applied}." >&2
        echo "!! --rollback only redeploys a same-schema release. This image would migrate forward on boot." >&2
        echo "!! Ship that change with scripts/deploy.sh, not --rollback." >&2
        echo "!! The chronicle backup was kept on the machine at /data/backups/worlds-${STAMP}.db." >&2
        exit 1
    fi
    echo "    live schema ${applied}; image schema ${known}"
else
    echo "==> Schema check: this checkout must not be older than the live chronicle"
    if ! applied="$(read_applied_schema)"; then
        echo "!! The chronicle backup was kept on the machine at /data/backups/worlds-${STAMP}.db." >&2
        exit 1
    fi
    if ! known="$(read_checkout_schema)"; then
        echo "!! The chronicle backup was kept on the machine at /data/backups/worlds-${STAMP}.db." >&2
        exit 1
    fi
    if (( known < applied )); then
        refuse_older_binary "checkout" "$known" "$applied"
    fi
    echo "    live schema ${applied}; checkout schema ${known}"
fi

prune_backups

if [[ "$mode" == "rollback" ]]; then
    echo "==> fly deploy --image (same schema ${applied})"
    "$FLY_BIN" deploy -a "$APP" --image "$image"
    echo
    echo "Rolled back to ${image}."
    echo "Verify before calling it done:"
    echo "  curl https://${APP}.fly.dev/health"
    echo "  ${FLY_BIN} logs -a ${APP}"
    echo "A schema_version refusal in the logs means stop. Do not retry past it."
    echo "Put back the image that matches the live chronicle, or restore the"
    echo "pre-upgrade backup from a binary that can still open it."
else
    echo "==> fly deploy"
    "$FLY_BIN" deploy -a "$APP"
    echo
    echo "Deployed."
fi

echo "To stream today's backup off-host:"
echo "  fly ssh sftp get /data/backups/worlds-${STAMP}.db ./local-backups/"
