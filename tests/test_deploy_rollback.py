"""scripts/deploy.sh backup, schema guard, and same-schema rollback.

The fly binary is a stub. Nothing here contacts Fly.io. The schema probes
that the script ships are executed against a temporary database and a
temporary migration directory.
"""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DEPLOY = _ROOT / "scripts" / "deploy.sh"
_IMAGE = "registry.fly.io/enfolded-beta:deployment-01HABC"
_DIGEST = (
    "registry.fly.io/enfolded-beta@sha256:"
    + "ab" * 32
)

_STUB = r"""#!/bin/bash
set -u
log="${FLY_STUB_LOG:?}"
{
  printf 'CALL'
  for arg in "$@"; do
    printf '\t%s' "$arg"
  done
  printf '\n'
} >> "$log"

text="$*"
if [[ "${1:-}" == "ssh" ]]; then
  if [[ "$text" == *"main.py backup"* ]]; then
    if [[ "${FLY_STUB_BACKUP_FAIL:-}" == 1 ]]; then
      echo "backup failed" >&2
      exit 1
    fi
    exit 0
  fi
  if [[ "$text" == *"xargs -r rm"* ]]; then
    if [[ "${FLY_STUB_PRUNE_FAIL:-}" == 1 ]]; then
      echo "prune failed" >&2
      exit 1
    fi
    exit 0
  fi
  if [[ "$text" == *"ENFOLDED_SCHEMA_PROBE=applied"* ]]; then
    if [[ "${FLY_STUB_EXEC_PROBE:-}" == 1 ]]; then
      prev=""
      c_arg=""
      for arg in "$@"; do
        if [[ "$prev" == "-C" ]]; then
          c_arg="$arg"
        fi
        prev="$arg"
      done
      sh -c "$c_arg"
      exit $?
    fi
    if [[ -n "${FLY_STUB_APPLIED_RAW:-}" ]]; then
      printf '%s\n' "$FLY_STUB_APPLIED_RAW"
      exit "${FLY_STUB_APPLIED_STATUS:-0}"
    fi
    printf 'noise from fly\nENFOLDED_SCHEMA_APPLIED=%s\n' "${FLY_STUB_APPLIED:-29}"
    exit 0
  fi
  echo "unexpected ssh: $*" >&2
  exit 1
fi
if [[ "${1:-}" == "machine" ]]; then
  if [[ "${FLY_STUB_EXEC_PROBE:-}" == 1 ]]; then
    prev=""
    c_arg=""
    for arg in "$@"; do
      if [[ "$prev" == "-c" ]]; then
        c_arg="$arg"
      fi
      prev="$arg"
    done
    ENFOLDED_SCHEMA_PROBE=known python3 -c "$c_arg"
    exit $?
  fi
  if [[ -n "${FLY_STUB_KNOWN_RAW:-}" ]]; then
    printf '%s\n' "$FLY_STUB_KNOWN_RAW"
    exit "${FLY_STUB_KNOWN_STATUS:-0}"
  fi
  printf 'boot noise\nENFOLDED_SCHEMA_KNOWN=%s\n' "${FLY_STUB_KNOWN:-29}"
  exit 0
fi
if [[ "${1:-}" == "deploy" ]]; then
  if [[ "${FLY_STUB_DEPLOY_FAIL:-}" == 1 ]]; then
    exit 1
  fi
  exit 0
fi
echo "unexpected fly invocation: $*" >&2
exit 1
"""


def _probe():
    spec = importlib.util.spec_from_file_location(
        "schema_probe", _ROOT / "scripts" / "schema_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _known() -> int:
    return _probe().known_version(_ROOT / "persistence" / "migrations")


def _calls(log: str) -> list[list[str]]:
    rows = []
    for line in log.splitlines():
        if not line.startswith("CALL"):
            continue
        parts = line.split("\t")
        rows.append(parts[1:])
    return rows


def _run(tmp_path, args, *, stub=None, env=None):
    log = tmp_path / "fly.log"
    log.unlink(missing_ok=True)
    fly = tmp_path / "fly"
    fly.write_text(_STUB)
    fly.chmod(0o755)
    run_env = os.environ.copy()
    run_env.pop("FLY_APP", None)
    run_env["FLY_BIN"] = str(fly)
    run_env["FLY_STUB_LOG"] = str(log)
    run_env["FLY_STUB_APPLIED"] = str(_known())
    run_env["FLY_STUB_KNOWN"] = str(_known())
    if stub:
        run_env.update(stub)
    if env:
        run_env.update(env)
    proc = subprocess.run(
        ["bash", str(_DEPLOY), *args],
        cwd=tmp_path,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )
    logged = log.read_text() if log.exists() else ""
    return proc, _calls(logged)


def _deploy_calls(calls):
    return [c for c in calls if c and c[0] == "deploy"]


def _has(calls, first):
    return any(c and c[0] == first for c in calls)


def test_help_does_not_call_fly(tmp_path):
    proc, calls = _run(tmp_path, ["--help"])
    assert proc.returncode == 0
    assert "--rollback <image-ref>" in proc.stdout
    assert "FLY_BIN" in proc.stdout
    assert calls == []


def test_help_with_another_flag_is_refused(tmp_path):
    proc, calls = _run(tmp_path, ["--help", "--first-deploy"])
    assert proc.returncode == 2
    assert "no other arguments" in proc.stderr
    assert calls == []


@pytest.mark.parametrize("args", [
    ["--nope"],
    ["--rollback"],
    ["--rollback", ""],
    ["--rollback", "--help"],
    ["--rollback", "--image"],
    ["--rollback", "registry.fly.io/app:tag;rm"],
    ["--rollback", "registry.fly.io/app:tag && true"],
    ["--rollback", "registry.fly.io/app:has space"],
    ["--rollback", "registry.fly.io/../app:tag"],
    ["--rollback", "nginx:latest"],
    ["--rollback", "registry.fly.io/app@sha256:abcd"],
    ["--rollback", _IMAGE, "extra"],
    ["--first-deploy", "--rollback", _IMAGE],
    ["--rollback", _IMAGE, "--first-deploy"],
    ["--first-deploy", "extra"],
    ["--rollback", _IMAGE, "--rollback", _IMAGE],
])
def test_bad_flags_and_image_refs_never_call_fly(tmp_path, args):
    proc, calls = _run(tmp_path, args)
    assert proc.returncode == 2
    assert proc.stderr.startswith("error:")
    assert calls == []


def test_digest_image_ref_is_accepted_on_rollback(tmp_path):
    proc, calls = _run(tmp_path, ["--rollback", _DIGEST])
    assert proc.returncode == 0, proc.stderr
    deploys = _deploy_calls(calls)
    assert deploys == [["deploy", "-a", "enfolded-beta", "--image", _DIGEST]]


def test_normal_deploy_backs_up_checks_schema_prunes_and_deploys(tmp_path):
    proc, calls = _run(tmp_path, [])
    assert proc.returncode == 0, proc.stderr
    assert _has(calls, "ssh")
    kinds = []
    for call in calls:
        text = " ".join(call)
        if call[0] == "ssh" and "main.py backup" in text:
            kinds.append("backup")
            assert "/data/backups/worlds-" in text
            assert " -a " not in text or call[call.index("-a") + 1] == "enfolded-beta"
        elif call[0] == "ssh" and "ENFOLDED_SCHEMA_PROBE=applied" in text:
            kinds.append("applied")
        elif call[0] == "ssh" and "xargs -r rm" in text:
            kinds.append("prune")
        elif call[0] == "deploy":
            kinds.append("deploy")
    assert kinds == ["backup", "applied", "prune", "deploy"]
    assert calls[-1] == ["deploy", "-a", "enfolded-beta"]
    assert "--image" not in calls[-1]
    assert "Deployed." in proc.stdout


def test_normal_deploy_allows_a_forward_migration(tmp_path):
    proc, calls = _run(tmp_path, [], stub={"FLY_STUB_APPLIED": str(_known() - 1)})
    assert proc.returncode == 0, proc.stderr
    assert _deploy_calls(calls) == [["deploy", "-a", "enfolded-beta"]]


def test_normal_deploy_refuses_an_older_checkout(tmp_path):
    proc, calls = _run(tmp_path, [], stub={"FLY_STUB_APPLIED": str(_known() + 1)})
    assert proc.returncode == 1
    assert "older than the live chronicle" in proc.stderr
    assert "disaster restore" in proc.stderr
    assert "no in-place downgrade" in proc.stderr
    assert "worlds-" in proc.stderr
    assert _deploy_calls(calls) == []
    assert not any("xargs -r rm" in " ".join(c) for c in calls)


def test_first_deploy_skips_backup_and_schema(tmp_path):
    proc, calls = _run(tmp_path, ["--first-deploy"], env={"FLY_APP": "enfolded-staging"})
    assert proc.returncode == 0, proc.stderr
    assert calls == [["deploy", "-a", "enfolded-staging"]]
    assert "no chronicle backup" in proc.stdout
    assert "ssh" not in proc.stdout


def test_backup_failure_refuses_normal_deploy_and_rollback(tmp_path):
    for args in ([], ["--rollback", _IMAGE]):
        proc, calls = _run(
            tmp_path, args, stub={"FLY_STUB_BACKUP_FAIL": "1"})
        assert proc.returncode == 1
        assert "unbacked chronicle" in proc.stderr
        assert _deploy_calls(calls) == []
        assert not _has(calls, "machine")
        assert len(calls) == 1
        assert "main.py backup" in " ".join(calls[0])


def test_rollback_same_schema_deploys_the_pinned_image(tmp_path):
    proc, calls = _run(tmp_path, ["--rollback", _IMAGE], env={"FLY_APP": "enfolded-staging"})
    assert proc.returncode == 0, proc.stderr
    machine = next(c for c in calls if c[0] == "machine")
    assert machine[:3] == ["machine", "run", _IMAGE]
    assert "--rm" in machine
    assert "--restart" in machine and machine[machine.index("--restart") + 1] == "no"
    assert "--volume" not in machine
    assert "--port" not in machine
    assert "--entrypoint" in machine
    assert machine[machine.index("--entrypoint") + 1] == "python3"
    assert "-e" in machine
    assert "ENFOLDED_SCHEMA_PROBE=known" in machine
    assert "--image" not in machine
    assert _deploy_calls(calls) == [
        ["deploy", "-a", "enfolded-staging", "--image", _IMAGE]]
    assert "curl https://enfolded-staging.fly.dev/health" in proc.stdout
    joined = " ".join(" ".join(c) for c in calls)
    assert joined.index("main.py backup") < joined.index("machine run")
    assert joined.index("machine run") < joined.index("deploy")


def test_rollback_refuses_an_older_image(tmp_path):
    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={"FLY_STUB_KNOWN": str(_known() - 1)})
    assert proc.returncode == 1
    assert "image schema" in proc.stderr
    assert "disaster restore" in proc.stderr
    assert _deploy_calls(calls) == []
    assert not any("xargs -r rm" in " ".join(c) for c in calls)


def test_rollback_refuses_a_newer_image(tmp_path):
    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={"FLY_STUB_KNOWN": str(_known() + 4)})
    assert proc.returncode == 1
    assert "newer than the live chronicle" in proc.stderr
    assert "--rollback only redeploys a same-schema release" in proc.stderr
    assert _deploy_calls(calls) == []


def test_schema_probe_failure_refuses_before_deploy(tmp_path):
    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={"FLY_STUB_APPLIED_RAW": "no sentinel here"})
    assert proc.returncode == 1
    assert "did not report one schema version" in proc.stderr
    assert not _has(calls, "machine")
    assert _deploy_calls(calls) == []


def test_two_schema_sentinels_are_a_refusal(tmp_path):
    proc, calls = _run(
        tmp_path, [],
        stub={"FLY_STUB_APPLIED_RAW":
               "ENFOLDED_SCHEMA_APPLIED=1\nENFOLDED_SCHEMA_APPLIED=2\n"})
    assert proc.returncode == 1
    assert "one schema version" in proc.stderr
    assert _deploy_calls(calls) == []


def test_repeated_same_sentinel_is_accepted(tmp_path):
    version = _known()
    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={
            "FLY_STUB_APPLIED_RAW":
                f"ENFOLDED_SCHEMA_APPLIED={version}\nENFOLDED_SCHEMA_APPLIED={version}\n",
            "FLY_STUB_KNOWN_RAW":
                f"noise ENFOLDED_SCHEMA_KNOWN={version} tail\n",
        })
    assert proc.returncode == 0, proc.stderr
    assert _deploy_calls(calls)


def test_prune_failure_still_deploys(tmp_path):
    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={"FLY_STUB_PRUNE_FAIL": "1"})
    assert proc.returncode == 0, proc.stderr
    assert "prune skipped" in proc.stdout
    assert _deploy_calls(calls) == [["deploy", "-a", "enfolded-beta", "--image", _IMAGE]]


def test_rollback_probe_reads_a_real_database_and_image(tmp_path):
    migrations = tmp_path / "image-migrations"
    migrations.mkdir()
    (migrations / "README.md").write_text("skip")
    (migrations / "0001_a.sql").write_text("SELECT 1;")
    (migrations / "0004_b.sql").write_text("SELECT 4;")
    db = tmp_path / "chronicle dir" / "worlds.db"
    db.parent.mkdir()
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    conn.execute("INSERT INTO schema_version (version) VALUES (4)")
    conn.commit()
    conn.close()

    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={"FLY_STUB_EXEC_PROBE": "1"},
        env={
            "ENFOLDED_SCHEMA_DB": str(db),
            "ENFOLDED_MIGRATIONS_DIR": str(migrations),
        })
    assert proc.returncode == 0, proc.stderr
    assert "live schema 4; image schema 4" in proc.stdout
    assert _deploy_calls(calls) == [["deploy", "-a", "enfolded-beta", "--image", _IMAGE]]

    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO schema_version (version) VALUES (5)")
    conn.commit()
    conn.close()
    proc, calls = _run(
        tmp_path, ["--rollback", _IMAGE],
        stub={"FLY_STUB_EXEC_PROBE": "1"},
        env={
            "ENFOLDED_SCHEMA_DB": str(db),
            "ENFOLDED_MIGRATIONS_DIR": str(migrations),
        })
    assert proc.returncode == 1
    assert "image schema 4 is older than the live chronicle schema 5" in proc.stderr
    assert _deploy_calls(calls) == []


def test_empty_fly_app_is_refused(tmp_path):
    proc, calls = _run(tmp_path, [], env={"FLY_APP": ""})
    assert proc.returncode == 2
    assert "FLY_APP is empty" in proc.stderr
    assert calls == []
