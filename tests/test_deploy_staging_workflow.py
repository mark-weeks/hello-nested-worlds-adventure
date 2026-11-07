"""The staging deploy workflow can reach the staging twin and nothing else.

Two halves. The first parses `.github/workflows/deploy-staging.yml` and
checks its hard guards: manual dispatch only, the staging app written into
the file, the staging-only token, the same pinned action commits as
`backup.yml`, and no production app name anywhere. The second runs the
workflow's own step scripts the way GitHub's `shell: bash` runs them
(`bash --noprofile --norc -eo pipefail`), with the step and job `env:` the
workflow declares, against the flyctl stub from `tests/test_deploy_rollback.py`
and a curl stub. Nothing here contacts Fly.io or the network.

PyYAML is not a dependency (requirements-dev.lock), so a small loader below
reads the block-style subset this workflow uses and raises on anything
outside it. An edit that leaves the subset fails here instead of being
misread.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_deploy_rollback import _STUB, _calls, _known

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github" / "workflows" / "deploy-staging.yml"
_BACKUP = _ROOT / ".github" / "workflows" / "backup.yml"
_STAGING = "enfolded-staging"
_PRODUCTION = "enfolded-beta"
_CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
_SETUP_FLYCTL = (
    "superfly/flyctl-actions/setup-flyctl@98172f70657cb3e15db199af139be99bd3e61200")
_TOKEN = "fixture-staging-token-not-a-secret"


# --- A strict loader for the workflow's YAML subset -------------------------

_KEY = re.compile(r"^([A-Za-z0-9_.-]+):(?:[ ](.*))?$")
_INT = re.compile(r"^-?[0-9]+$")


class _Subset:
    """Block mappings, block sequences, `|` scalars, plain and quoted scalars.

    Comments are full-line or after a space. Flow collections, anchors,
    aliases, tags, `>` folding, chomping indicators, tabs in indentation and
    duplicate keys all raise.
    """

    def __init__(self, text: str):
        self.lines = text.split("\n")
        self.i = 0

    def fail(self, why: str):
        raise ValueError(f"line {self.i + 1}: {why}")

    def peek(self):
        while self.i < len(self.lines):
            line = self.lines[self.i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                self.i += 1
                continue
            lead = line[:len(line) - len(line.lstrip())]
            if "\t" in lead:
                self.fail("tab in indentation")
            return len(lead), stripped
        return None

    def document(self):
        first = self.peek()
        if first is None or first[0] != 0:
            self.fail("document must start at column 0")
        value = self.node(0)
        if self.peek() is not None:
            self.fail("content after the document")
        return value

    def node(self, indent: int):
        _ind, text = self.peek()
        if text == "-" or text.startswith("- "):
            return self.sequence(indent)
        return self.mapping(indent)

    def mapping(self, indent: int) -> dict:
        result: dict = {}
        while (here := self.peek()) is not None:
            ind, text = here
            if ind < indent:
                break
            if ind > indent:
                self.fail("unexpected indentation")
            if text.startswith("-"):
                self.fail("sequence item where a key was expected")
            match = _KEY.match(text)
            if not match:
                self.fail(f"not a key: {text!r}")
            key, rest = match.group(1), match.group(2)
            if key in result:
                self.fail(f"duplicate key {key!r}")
            self.i += 1
            result[key] = self.value(rest, indent)
        return result

    def sequence(self, indent: int) -> list:
        result: list = []
        while (here := self.peek()) is not None:
            ind, text = here
            if ind < indent:
                break
            if ind > indent:
                self.fail("unexpected indentation")
            if not text.startswith("- "):
                self.fail("key where a sequence item was expected")
            content = text[2:]
            if content != content.lstrip():
                self.fail("extra space after '-'")
            if _KEY.match(content):
                # The item is a mapping whose first key sits two columns in.
                self.lines[self.i] = " " * (indent + 2) + content
                result.append(self.mapping(indent + 2))
            else:
                self.i += 1
                result.append(self.scalar(content))
        return result

    def value(self, rest, indent: int):
        if rest is None or not rest.strip() or rest.strip().startswith("#"):
            here = self.peek()
            if here is None or here[0] <= indent:
                return None
            return self.node(here[0])
        if rest.strip() == "|":
            return self.block(indent)
        return self.scalar(rest)

    def block(self, indent: int) -> str:
        body: list[str] = []
        block_indent = None
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if not line.strip():
                body.append("")
                self.i += 1
                continue
            ind = len(line) - len(line.lstrip(" "))
            if ind <= indent:
                break
            if block_indent is None:
                block_indent = ind
            if ind < block_indent:
                self.fail("block scalar line under its indentation")
            body.append(line[block_indent:])
            self.i += 1
        while body and body[-1] == "":
            body.pop()
        if not body:
            self.fail("empty block scalar")
        return "\n".join(body) + "\n"

    def scalar(self, raw: str):
        text = raw.strip()
        if text[0] in "'\"":
            quote = text[0]
            end = 1
            while True:
                end = text.find(quote, end)
                if end == -1:
                    self.fail("unterminated quoted scalar")
                if quote == "'" and text[end + 1:end + 2] == "'":
                    end += 2
                    continue
                break
            inner = text[1:end]
            if quote == '"' and "\\" in inner:
                self.fail("escape in a double-quoted scalar")
            tail = text[end + 1:].strip()
            if tail and not tail.startswith("#"):
                self.fail("text after a quoted scalar")
            return inner.replace("''", "'") if quote == "'" else inner
        cut = text.find(" #")
        if cut != -1:
            text = text[:cut].rstrip()
        if text[0] in "[]{}&*!|>%@`":
            self.fail(f"unsupported scalar {text!r}")
        if ": " in text:
            self.fail(f"': ' inside a plain scalar {text!r}")
        if text in ("true", "false"):
            return text == "true"
        if text in ("null", "~"):
            return None
        if _INT.match(text):
            return int(text)
        return text


def _load(text: str):
    return _Subset(text).document()


@pytest.fixture(scope="module")
def text() -> str:
    return _WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text):
    return _load(text)


@pytest.fixture(scope="module")
def job(workflow):
    jobs = workflow["jobs"]
    assert list(jobs) == ["deploy"]
    return jobs["deploy"]


def _step(job, name: str) -> dict:
    matches = [s for s in job["steps"] if s.get("name") == name]
    assert len(matches) == 1, f"expected one step named {name!r}"
    return matches[0]


def _index(job, name: str) -> int:
    return [s.get("name") for s in job["steps"]].index(name)


# --- The loader itself -------------------------------------------------------

def test_loader_reads_the_subset_and_refuses_what_it_does_not_know():
    doc = _load(
        "a: 1\n"
        "b: 'it''s'\n"
        "c:\n"
        "  - name: x  # trailing comment\n"
        "    run: |\n"
        "      echo one\n"
        "      # kept: a shell comment\n"
        "\n"
        "      echo two\n"
        "  - plain\n"
        "d: false\n")
    assert doc == {
        "a": 1,
        "b": "it's",
        "c": [{"name": "x", "run": "echo one\n# kept: a shell comment\n\necho two\n"},
              "plain"],
        "d": False,
    }
    for bad in ("a: [1, 2]\n", "a: {}\n", "a: &x 1\n", "a: >\n  b\n",
                "a: 1\na: 2\n", "a:\n\t- b\n", "a: b: c\n", "a: |-\n  b\n"):
        with pytest.raises(ValueError):
            _load(bad)


def test_pins_are_the_ones_backup_yml_already_uses():
    backup = _BACKUP.read_text()
    assert f"uses: {_CHECKOUT} # v4" in backup
    assert f"uses: {_SETUP_FLYCTL}" in backup
    assert "version: 0.5.1" in backup


# --- Static guards -----------------------------------------------------------

def test_manual_dispatch_is_the_only_trigger(workflow):
    assert list(workflow["on"]) == ["workflow_dispatch"]
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"ref", "first_deploy"}
    assert inputs["ref"]["type"] == "string"
    assert inputs["ref"]["default"] == "main"
    assert inputs["first_deploy"]["type"] == "boolean"
    assert inputs["first_deploy"]["default"] is False


def test_permissions_and_concurrency(workflow, job):
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in job
    concurrency = workflow["concurrency"]
    assert concurrency["group"] == "deploy-staging"
    assert concurrency["cancel-in-progress"] is False
    assert job["defaults"] == {"run": {"shell": "bash"}}
    assert job["timeout-minutes"] <= 30


def test_the_app_is_written_into_the_file_not_supplied(text, job):
    assert job["env"]["FLY_APP"] == _STAGING
    assert "FLY_APP" not in _step(job, "Deploy with scripts/deploy.sh")["env"]
    # No repository variable or input can redirect the target.
    assert "vars." not in text
    assert "inputs.app" not in text
    assert "inputs.fly_app" not in text.lower()


def test_no_production_name_or_production_secret_anywhere(text):
    assert _PRODUCTION not in text.lower()
    assert "registry.fly.io" not in text
    assert set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text)) == {"FLY_API_TOKEN_STAGING"}
    assert "github.token" not in text
    assert "GITHUB_TOKEN" not in text


def test_the_token_reaches_only_the_steps_that_need_it(job):
    holders = []
    for step in job["steps"]:
        env = step.get("env") or {}
        if "FLY_API_TOKEN" in env:
            assert env["FLY_API_TOKEN"] == "${{ secrets.FLY_API_TOKEN_STAGING }}"
            holders.append(step["name"])
        assert "FLY_API_TOKEN" not in (step.get("with") or {})
    assert holders == ["Refuse without the staging deploy token",
                       "Deploy with scripts/deploy.sh"]
    assert "FLY_API_TOKEN" not in job["env"]


def test_actions_are_pinned_to_the_backup_workflow_commits(job):
    uses = [step["uses"] for step in job["steps"] if "uses" in step]
    assert uses == [_CHECKOUT, _SETUP_FLYCTL]
    for ref in uses:
        assert re.fullmatch(r"[a-z0-9/_-]+@[0-9a-f]{40}", ref)
    checkout = _step(job, "Check out the ref to deploy")
    assert checkout["with"] == {
        "ref": "${{ inputs.ref }}", "persist-credentials": False}
    assert _step(job, "Set up flyctl")["with"] == {"version": "0.5.1"}


def test_guards_run_before_the_checkout_and_the_deploy(job):
    guard = _index(job, "Refuse any app but the staging twin")
    token = _index(job, "Refuse without the staging deploy token")
    checkout = _index(job, "Check out the ref to deploy")
    flyctl = _index(job, "Set up flyctl")
    deploy = _index(job, "Deploy with scripts/deploy.sh")
    health = _index(job, "Wait for staging /health")
    assert guard == 0
    assert guard < token < checkout < flyctl < deploy < health
    assert health == len(job["steps"]) - 1
    for step in job["steps"]:
        assert "if" not in step, "no step may be skipped by a condition"
        assert "continue-on-error" not in step


def test_scripts_take_inputs_through_env_only(job):
    # An expression inside a run script is spliced in before bash parses it.
    for step in job["steps"]:
        if "run" in step:
            assert "${{" not in step["run"], step["name"]


def test_no_invite_keys_and_no_artifacts(text, job):
    lowered = text.lower()
    assert "upload-artifact" not in lowered
    for step in job["steps"]:
        script = step.get("run", "")
        assert "invite" not in script
        assert "main.py" not in script
        assert "ssh" not in script


def test_health_check_targets_staging_and_is_bounded(job):
    env = _step(job, "Wait for staging /health")["env"]
    assert env["HEALTH_URL"] == f"https://{_STAGING}.fly.dev/health"
    attempts = int(env["HEALTH_ATTEMPTS"])
    interval = int(env["HEALTH_INTERVAL_SECONDS"])
    assert 1 <= attempts and 0 < interval
    # Each attempt is at most a 10 s curl plus the interval.
    assert attempts * (10 + interval) <= 15 * 60


# --- Running the workflow's step scripts ------------------------------------

_EXPR = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")


def _context(*, ref="main", first_deploy=False, token=_TOKEN):
    return {
        "inputs.ref": ref,
        "inputs.first_deploy": "true" if first_deploy else "false",
        "secrets.FLY_API_TOKEN_STAGING": token,
    }


def _resolve(value, context) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"

    def sub(match):
        expr = match.group(1)
        assert expr in context, f"unexpected expression: {expr}"
        return context[expr]
    return _EXPR.sub(sub, str(value))


# Logs each call. Fails like `curl -f` on a 503 until call CURL_STUB_OK_ON,
# then prints CURL_STUB_BODY (default: what /health returns).
_CURL = r"""#!/bin/bash
set -u
printf '%s\n' "$*" >> "${CURL_STUB_LOG:?}"
n=$(wc -l < "$CURL_STUB_LOG")
if [ -n "${CURL_STUB_OK_ON:-}" ] && [ "$n" -ge "$CURL_STUB_OK_ON" ]; then
  if [ -n "${CURL_STUB_BODY+set}" ]; then
    printf '%s' "$CURL_STUB_BODY"
  else
    printf '%s' '{"status": "ok"}'
  fi
  exit 0
fi
echo 'curl: (22) The requested URL returned error: 503' >&2
exit 22
"""


def _write_curl(bin_dir: Path) -> None:
    curl = bin_dir / "curl"
    curl.write_text(_CURL)
    curl.chmod(0o755)


def _run_step(tmp_path, job, name, *, context=None, env=None):
    """Run one step's script as GitHub's `shell: bash` does."""
    step = _step(job, name)
    context = context or _context()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fly = bin_dir / "fly-stub"
    fly.write_text(_STUB)
    fly.chmod(0o755)
    _write_curl(bin_dir)
    fly_log = tmp_path / "fly.log"
    curl_log = tmp_path / "curl.log"
    summary = tmp_path / "summary.md"
    for path in (fly_log, curl_log, summary):
        path.unlink(missing_ok=True)
    script = tmp_path / "step.sh"
    script.write_text(step["run"])

    run_env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(summary),
        "FLY_STUB_LOG": str(fly_log),
        "FLY_STUB_APPLIED": str(_known()),
        "FLY_STUB_KNOWN": str(_known()),
        "CURL_STUB_LOG": str(curl_log),
    }
    for key, value in job["env"].items():
        run_env[key] = _resolve(value, context)
    for key, value in (step.get("env") or {}).items():
        run_env[key] = _resolve(value, context)
    # The workflow installs flyctl; the test points FLY_BIN at the stub.
    assert run_env["FLY_BIN"] == "flyctl"
    run_env["FLY_BIN"] = str(fly)
    if env:
        run_env.update(env)
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
        cwd=_ROOT, env=run_env, text=True, capture_output=True, check=False)
    calls = _calls(fly_log.read_text()) if fly_log.exists() else []
    curls = curl_log.read_text().splitlines() if curl_log.exists() else []
    written = summary.read_text() if summary.exists() else ""
    return proc, calls, curls, written


def _assert_only_staging(calls):
    assert calls, "deploy.sh made no fly calls"
    for call in calls:
        assert "-a" in call, call
        assert call[call.index("-a") + 1] == _STAGING
        assert not any(_PRODUCTION in arg for arg in call), call


def test_guard_step_accepts_the_staging_app(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, "Refuse any app but the staging twin")
    assert proc.returncode == 0, proc.stderr
    assert "Target app: enfolded-staging" in proc.stdout
    assert calls == []


@pytest.mark.parametrize("app", [
    _PRODUCTION, "", "Enfolded-Staging", "enfolded-staging ", " enfolded-staging",
    "enfolded-staging-2", "enfolded-stagin", "enfolded-staging\n",
])
def test_guard_step_refuses_any_other_app(tmp_path, job, app):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, "Refuse any app but the staging twin", env={"FLY_APP": app})
    assert proc.returncode == 1
    assert "::error::This workflow deploys only enfolded-staging" in proc.stdout
    assert "Target app" not in proc.stdout
    assert calls == []


def test_guard_step_refuses_an_unset_app(job):
    script = _step(job, "Refuse any app but the staging twin")["run"]
    unset = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "REF_INPUT": "main", "FIRST_DEPLOY": "false"},
        text=True, capture_output=True, check=False)
    assert unset.returncode == 1
    assert "deploys only enfolded-staging" in unset.stdout


@pytest.mark.parametrize("ref", [
    "main", "claude/staging-deploy-workflow", "v0.1.1-qa.2",
    "3200eeda7cb992a9081217f96731a472ebcffca5",
])
def test_guard_step_accepts_ordinary_refs(tmp_path, job, ref):
    proc, *_ = _run_step(tmp_path, job, "Refuse any app but the staging twin",
                         context=_context(ref=ref))
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("ref", [
    "", "-main", "--upload-pack=x", "main;true", "main && true", "has space",
    "a/../b", "main\nmain", "::set-env name=X::y", "$(id)", "x" * 256,
])
def test_guard_step_refuses_odd_refs(tmp_path, job, ref):
    proc, *_ = _run_step(tmp_path, job, "Refuse any app but the staging twin",
                         context=_context(ref=ref))
    assert proc.returncode == 1
    assert "::error::ref must be a branch, tag or commit" in proc.stdout
    assert "Target app" not in proc.stdout


def test_guard_step_refuses_a_non_boolean_first_deploy(tmp_path, job):
    proc, *_ = _run_step(tmp_path, job, "Refuse any app but the staging twin",
                         env={"FIRST_DEPLOY": "yes"})
    assert proc.returncode == 1
    assert "first_deploy must be true or false" in proc.stdout


def test_token_step_refuses_cleanly_when_the_secret_is_unset(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, "Refuse without the staging deploy token",
        context=_context(token=""))
    assert proc.returncode == 1
    assert "::error::The repository secret FLY_API_TOKEN_STAGING is not set" in proc.stdout
    assert "fly tokens create deploy -a enfolded-staging" in proc.stdout
    assert proc.stderr == ""
    assert calls == []


def test_token_step_never_prints_the_token(tmp_path, job):
    proc, *_ = _run_step(tmp_path, job, "Refuse without the staging deploy token")
    assert proc.returncode == 0, proc.stderr
    assert "FLY_API_TOKEN_STAGING is set." in proc.stdout
    assert _TOKEN not in proc.stdout + proc.stderr


def test_deploy_step_backs_up_then_deploys_only_staging(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, "Deploy with scripts/deploy.sh")
    assert proc.returncode == 0, proc.stderr
    _assert_only_staging(calls)
    kinds = []
    for call in calls:
        joined = " ".join(call)
        if call[0] == "ssh" and "main.py backup" in joined:
            kinds.append("backup")
        elif call[0] == "ssh" and "ENFOLDED_SCHEMA_PROBE=applied" in joined:
            kinds.append("schema")
        elif call[0] == "ssh" and "xargs -r rm" in joined:
            kinds.append("prune")
        elif call[0] == "deploy":
            kinds.append("deploy")
        else:
            kinds.append(joined)
    assert kinds == ["backup", "schema", "prune", "deploy"]
    assert calls[-1] == ["deploy", "-a", _STAGING]
    assert "--first-deploy" not in " ".join(" ".join(c) for c in calls)
    assert "Deployed." in proc.stdout
    assert _TOKEN not in proc.stdout + proc.stderr


def test_first_deploy_maps_to_the_first_deploy_flag(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, "Deploy with scripts/deploy.sh",
        context=_context(first_deploy=True))
    assert proc.returncode == 0, proc.stderr
    assert calls == [["deploy", "-a", _STAGING]]
    assert "First deploy: no machine to back up" in proc.stdout
    assert "no chronicle backup" in proc.stdout


def test_deploy_step_refuses_over_a_failed_backup(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, "Deploy with scripts/deploy.sh",
        env={"FLY_STUB_BACKUP_FAIL": "1"})
    assert proc.returncode == 1
    assert "unbacked chronicle" in proc.stderr
    assert [c[0] for c in calls] == ["ssh"]
    _assert_only_staging(calls)


@pytest.mark.parametrize("app", [_PRODUCTION, "", "enfolded-staging-2"])
def test_deploy_step_refuses_another_app_before_deploy_sh(tmp_path, job, app):
    for first_deploy in (False, True):
        proc, calls, _curls, _summary = _run_step(
            tmp_path, job, "Deploy with scripts/deploy.sh",
            context=_context(first_deploy=first_deploy), env={"FLY_APP": app})
        assert proc.returncode == 1
        assert "::error::FLY_APP is not enfolded-staging" in proc.stdout
        assert calls == []


def test_deploy_step_passes_the_app_explicitly(job):
    # Even if the job env were changed after the guard, deploy.sh is told
    # the staging app by name.
    script = _step(job, "Deploy with scripts/deploy.sh")["run"]
    lines = [line.strip() for line in script.splitlines()
             if "scripts/deploy.sh" in line and not line.strip().startswith("#")]
    assert lines == ['FLY_APP=enfolded-staging bash scripts/deploy.sh "${args[@]}"']


def test_health_step_passes_on_status_ok(tmp_path, job):
    proc, calls, curls, summary = _run_step(
        tmp_path, job, "Wait for staging /health",
        env={"HEALTH_ATTEMPTS": "5", "HEALTH_INTERVAL_SECONDS": "0",
             "CURL_STUB_OK_ON": "3"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(curls) == 3
    for line in curls:
        assert line.endswith("https://enfolded-staging.fly.dev/health")
        assert "--max-time 10" in line
    assert "status ok on attempt 3" in proc.stdout
    assert "- Health: ok on attempt 3" in summary
    assert calls == []


@pytest.mark.parametrize("body", [
    '{"status": "starting"}', '{"status": "OK"}', '["ok"]', "ok", "", '{"status":',
])
def test_health_step_fails_after_bounded_attempts_without_status_ok(tmp_path, job, body):
    proc, _calls_, curls, summary = _run_step(
        tmp_path, job, "Wait for staging /health",
        env={"HEALTH_ATTEMPTS": "4", "HEALTH_INTERVAL_SECONDS": "0",
             "CURL_STUB_OK_ON": "1", "CURL_STUB_BODY": body})
    assert proc.returncode == 1
    assert len(curls) == 4
    assert "::error::Staging /health did not answer status ok in 4 attempts." in proc.stdout
    assert "- Health: not ok after 4 attempts" in summary


def test_health_step_accepts_compact_json(tmp_path, job):
    proc, _calls_, curls, _summary = _run_step(
        tmp_path, job, "Wait for staging /health",
        env={"HEALTH_ATTEMPTS": "2", "HEALTH_INTERVAL_SECONDS": "0",
             "CURL_STUB_OK_ON": "1", "CURL_STUB_BODY": '{"status":"ok"}'})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(curls) == 1


def test_health_step_fails_when_staging_never_answers(tmp_path, job):
    proc, _calls_, curls, _summary = _run_step(
        tmp_path, job, "Wait for staging /health",
        env={"HEALTH_ATTEMPTS": "3", "HEALTH_INTERVAL_SECONDS": "0"})
    assert proc.returncode == 1
    assert len(curls) == 3


def test_record_step_writes_the_target_to_the_summary(tmp_path, job):
    proc, calls, _curls, summary = _run_step(
        tmp_path, job, "Record what is being deployed",
        context=_context(ref="main", first_deploy=True))
    assert proc.returncode == 0, proc.stderr
    assert "- App: `enfolded-staging` (disposable staging twin)" in summary
    assert "- Ref: `main`" in summary
    assert re.search(r"- Commit: `[0-9a-f]{40}`", summary)
    assert "- First deploy: true" in summary
    assert _TOKEN not in proc.stdout + summary
    assert calls == []
