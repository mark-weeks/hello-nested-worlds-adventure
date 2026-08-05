#!/bin/bash
# SessionStart bootstrap for Claude Code on the web: provision the pinned
# toolchain (Python 3.11, Node 20.19+) and install the locked dependency
# graphs so ./scripts/check.sh works from the first turn. Local sessions
# are untouched — this repo's canonical bootstrap remains ./setup.sh.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

node_is_pinned() {
  "$1" -e 'const [maj, min] = process.versions.node.split(".").map(Number); process.exit(maj === 20 && min >= 19 ? 0 : 1)' 2>/dev/null
}

# setup.sh refuses anything but Node 20.19+ (.nvmrc pins the major on
# purpose — the committed-bundle freshness gate depends on reproducible
# builds). Remote containers default to a newer major but ship /opt/node20
# alongside it; select it and persist the choice into the session's PATH so
# npm test / npm run build also run under the pinned major.
if ! node_is_pinned node; then
  if [ -x /opt/node20/bin/node ] && node_is_pinned /opt/node20/bin/node; then
    export PATH="/opt/node20/bin:$PATH"
    if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
      echo 'export PATH="/opt/node20/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
    fi
    echo "Using /opt/node20 ($(/opt/node20/bin/node --version)) to satisfy the .nvmrc pin."
  else
    echo "No Node 20.19+ available (see .nvmrc); ./setup.sh will refuse to run until one is installed." >&2
    exit 1
  fi
fi

# Re-running setup.sh is safe but slow (npm ci rebuilds node_modules from
# scratch), so skip it when every pinned input is unchanged AND the
# environment still answers as installed — bare directory existence is not
# enough, since node_modules survives an interrupted npm ci and .venv
# survives a failed manual setup. The stamp lives untracked in .claude/
# (gitignored).
env_is_healthy() {
  [ -x .venv/bin/python ] \
    && .venv/bin/ruff --version >/dev/null 2>&1 \
    && .venv/bin/python -m pytest --version >/dev/null 2>&1 \
    && npm ls --prefix frontend --all >/dev/null 2>&1
}

stamp_file=".claude/.session-setup-stamp"
stamp="$(cksum pyproject.toml requirements.lock requirements-dev.lock frontend/package-lock.json .python-version .nvmrc setup.sh | cksum)"
if [ "$(cat "$stamp_file" 2>/dev/null)" = "$stamp" ] && env_is_healthy; then
  echo "Enfolded environment already bootstrapped; locked inputs unchanged and toolchain healthy."
  exit 0
fi

# Drop the stamp before (re)installing so an interrupted run can never
# leave a stale stamp behind; it is rewritten only after setup succeeds.
rm -f "$stamp_file"
./setup.sh
echo "$stamp" > "$stamp_file"
