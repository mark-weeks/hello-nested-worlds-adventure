#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

python_bin="${ENFOLDED_PYTHON:-python3.11}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "Enfolded requires Python 3.11 (set ENFOLDED_PYTHON if it is not named python3.11)." >&2
  exit 1
fi
python_version="$($python_bin -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$python_version" != "3.11" ]; then
  echo "Enfolded requires Python 3.11; found $python_version via $python_bin." >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Enfolded requires Node 20.19+ (see .nvmrc)." >&2
  exit 1
fi
node_version="$(node -p 'process.versions.node')"
if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major === 20 && minor >= 19 ? 0 : 1)'; then
  echo "Enfolded requires Node 20.19+; found $node_version. Run 'nvm use' and retry." >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  "$python_bin" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade "pip==26.0.1" "setuptools==82.0.0"
.venv/bin/python -m pip install --no-build-isolation -c requirements-dev.lock -e ".[dev]"
npm ci --prefix frontend

echo "Enfolded environment ready: Python $python_version, Node $node_version, locked dependencies installed."
