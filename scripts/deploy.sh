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
# Fly flags (flyctl source and docs, read 2026-11-06):
#   fly deploy -a APP --image IMAGE     -i/--image is "The Docker image to deploy"
#   fly releases -a APP --image         shows each release's image reference
#   fly ssh console -C CMD              CMD is exec'd, not passed to a shell
#   fly console -a APP --image IMAGE -C CMD
#       ephemeral machine, init /bin/sleep inf (ToConsoleMachineConfig),
#       auto-destroy, restart no. -C stdout is the SSH session, not the
#       init process. fly machine run does not stream guest stdout.
# The image probe passes no --volume and no --port, so it does not mount
# the chronicle and does not join the public proxy.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# An explicit empty FLY_APP or FLY_BIN is a mistake, not a request for the default.
APP="${FLY_APP-enfolded-beta}"
FLY_BIN="${FLY_BIN-fly}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
KEEP=5
# Stdlib module inside the wheel. Encoded and exec'd remotely so an older
# image does not need this module installed.
PROBE_FILE="$repo_root/persistence/schema_probe.py"

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

The image ref must be registry.fly.io/<FLY_APP>:<tag>
or registry.fly.io/<FLY_APP>@sha256:<64 hex>.
Find it with: fly releases -a "$FLY_APP" --image
EOF
}

die() {
    echo "error: $*" >&2
    exit 2
}

validate_image() {
    local ref="$1"
    local prefix tag
    if [[ -z "$ref" ]]; then
        die "--rollback image ref is empty"
    fi
    if [[ "$ref" == -* ]]; then
        die "image ref must not look like a flag: ${ref}"
    fi
    if [[ "$ref" == *[[:space:]]* ]]; then
        die "image ref must not contain whitespace"
    fi
    # Only this app's Fly registry. A wrong-app or external image would
    # run where this app's secrets are available, then be deployed.
    # Hyphens in the app name are literal in the regex below.
    if [[ ! "$APP" =~ ^[a-z][a-z0-9-]{0,62}$ ]]; then
        die "FLY_APP is not a Fly app name: ${APP}"
    fi
    prefix="registry.fly.io/${APP}"
    if [[ "$ref" == "${prefix}@"* ]]; then
        if [[ ! "$ref" =~ ^registry\.fly\.io/${APP}@sha256:[a-fA-F0-9]{64}$ ]]; then
            die "digest image ref must be registry.fly.io/${APP}@sha256:<64 hex digits>"
        fi
        return
    fi
    if [[ "$ref" != "${prefix}:"* ]]; then
        die "image ref must be registry.fly.io/${APP}:<tag> or registry.fly.io/${APP}@sha256:<64 hex>"
    fi
    tag="${ref#"${prefix}:"}"
    if [[ ! "$tag" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
        die "image tag contains characters that are not allowed"
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

# fly ssh console -C and fly console -C exec the command. They do not
# pass it to a shell, so a bare VAR=value prefix is not an assignment.
# The python source has no spaces, so a whitespace split keeps it as one
# -c argument. `env` is the executable that sets the variable.
probe_exec() {
    local mode="$1"
    local b64
    b64="$(probe_b64)"
    printf "env ENFOLDED_SCHEMA_PROBE=%s python3 -c exec(__import__('base64').b64decode('%s'))" \
        "$mode" "$b64"
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
    local out applied
    # python3 is the image interpreter (python:3.11-slim). The backup
    # command stays `python main.py`, which that image also provides.
    if ! out="$(fly_capture "$FLY_BIN" ssh console -a "$APP" -C \
        "$(probe_exec applied)")"; then
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
    local out known
    # fly console, not fly machine run. machine run prints launch metadata
    # and does not stream the guest process's stdout (flyctl
    # internal/command/machine/run.go). console SSHes in and copies the
    # -C command's stdout (ssh.Session.Run). Its ephemeral machine init is
    # /bin/sleep inf, restart no, auto-destroy; cleanup waits up to 15s
    # for the machine to be destroyed (internal/machine/ephemeral.go).
    # No --volume and no --port: the chronicle stays unmounted and the
    # machine does not join the public proxy. --skip-dns-registration
    # matches flyctl's console default (true) so the probe is not registered.
    if ! out="$(fly_capture "$FLY_BIN" console \
        -a "$APP" \
        --image "$image" \
        --skip-dns-registration \
        -C "$(probe_exec known)")"; then
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
