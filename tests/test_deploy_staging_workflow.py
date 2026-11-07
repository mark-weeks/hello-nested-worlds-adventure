"""The staging deploy workflow can reach the staging twin and nothing else.

Two halves. The first parses `.github/workflows/deploy-staging.yml` and
checks its hard guards: manual dispatch only, main only, the staging app
written into the file, the staging-only token held by the `staging`
environment, every expression in the file, the exact step list, the same
pinned action commits as `backup.yml`, and no production app name anywhere.
The second runs the workflow's own step scripts the way GitHub's
`shell: bash` runs them (`bash --noprofile --norc -eo pipefail`), with the
step and job `env:` the workflow declares, against the flyctl stub from
`tests/test_deploy_rollback.py` and a curl stub. The schema-check step runs
against small git repositories built here and, where the local history has
them, against this repository's own commits and tags. Nothing here contacts
Fly.io or the network.

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
# #152: the first commit whose scripts/deploy.sh checks the schema
# (read_checkout_schema) and whose binary refuses a newer chronicle.
_SCHEMA_GUARD = "f3ead7474e4556c2d5eaec12ccde6b57dff8c8c1"
_MAIN = "refs/heads/main"

_GUARD = "Refuse any app but staging and any ref but main"
_TOKEN_STEP = "Refuse without the staging deploy token"
_CHECKOUT_STEP = "Check out main"
_SCHEMA_STEP = "Refuse a commit without the schema check"
_RECORD = "Record what is being deployed"
_FLYCTL = "Set up flyctl"
_DEPLOY = "Deploy with scripts/deploy.sh"
_HEALTH = "Wait for staging /health"
_STEPS = [_GUARD, _TOKEN_STEP, _CHECKOUT_STEP, _SCHEMA_STEP, _RECORD,
          _FLYCTL, _DEPLOY, _HEALTH]


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

_EXPR = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
_ALLOWED_EXPRESSIONS = {"secrets.FLY_API_TOKEN_STAGING"}


def test_top_level_and_job_keys_are_exactly_these(workflow, job):
    # No workflow-level env or defaults: nothing can reach every step
    # without appearing in the job or step blocks checked below.
    assert list(workflow) == ["name", "on", "permissions", "concurrency", "jobs"]
    assert set(job) == {"name", "runs-on", "timeout-minutes", "environment",
                        "defaults", "env", "steps"}
    assert job["env"] == {"FLY_APP": _STAGING, "FLY_BIN": "flyctl"}


def test_the_job_runs_in_the_staging_environment(job):
    # The owner stores FLY_API_TOKEN_STAGING as a secret of this environment
    # and limits its deployment branches to main (runbook 3a).
    assert job["environment"] == "staging"


def test_manual_dispatch_is_the_only_trigger_and_it_takes_no_inputs(workflow, text):
    # No ref input: the run deploys the main commit it was dispatched at.
    # No first-deploy input: that skips the backup, so it stays a terminal step.
    assert workflow["on"] == {"workflow_dispatch": None}
    assert "inputs" not in text
    assert "--first-deploy" not in text.replace("No --first-deploy:", "")


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
    for step in job["steps"]:
        assert "FLY_APP" not in (step.get("env") or {}), step["name"]
        assert "FLY_BIN" not in (step.get("env") or {}), step["name"]
    # No repository variable or input can redirect the target.
    assert "vars." not in text
    assert "inputs.app" not in text
    assert "inputs.fly_app" not in text.lower()


def test_the_only_expression_in_the_file_is_the_staging_token(text):
    found = _EXPR.findall(text)
    # Every `${{` opens an expression the pattern read, on one line.
    assert text.count("${{") == len(found)
    assert set(found) == _ALLOWED_EXPRESSIONS


def test_no_production_name_or_production_secret_anywhere(text):
    assert _PRODUCTION not in text.lower()
    assert "registry.fly.io" not in text
    # Any spelling of a secrets lookup, dotted or bracketed, any case.
    rest = text.lower().replace("secrets.fly_api_token_staging", "")
    assert "secrets" not in rest
    assert "github.token" not in text
    assert "GITHUB_TOKEN" not in text


def test_steps_are_exactly_these_in_this_order(job):
    assert [step.get("name") for step in job["steps"]] == _STEPS
    for step in job["steps"]:
        assert set(step) <= {"name", "env", "run", "uses", "with"}, step["name"]
        assert ("run" in step) != ("uses" in step), step["name"]
        assert "if" not in step, "no step may be skipped by a condition"
        assert "continue-on-error" not in step
    assert "if" not in job


def test_each_step_has_exactly_its_env(job):
    expected = {
        _GUARD: set(),
        _TOKEN_STEP: {"FLY_API_TOKEN"},
        _CHECKOUT_STEP: set(),
        _SCHEMA_STEP: {"SCHEMA_GUARD_COMMIT"},
        _RECORD: set(),
        _FLYCTL: set(),
        _DEPLOY: {"FLY_API_TOKEN"},
        _HEALTH: {"HEALTH_URL", "HEALTH_ATTEMPTS", "HEALTH_INTERVAL_SECONDS"},
    }
    assert {step["name"]: set(step.get("env") or {})
            for step in job["steps"]} == expected


def test_no_step_can_change_later_steps_environment(text):
    # A step that wrote FLY_BIN or a token to these files would reach every
    # step after it.
    for name in ("GITHUB_ENV", "GITHUB_PATH", "GITHUB_OUTPUT"):
        assert name not in text


def test_the_token_reaches_only_the_steps_that_need_it(job):
    holders = []
    for step in job["steps"]:
        env = step.get("env") or {}
        if "FLY_API_TOKEN" in env:
            assert env["FLY_API_TOKEN"] == "${{ secrets.FLY_API_TOKEN_STAGING }}"
            holders.append(step["name"])
        assert "FLY_API_TOKEN" not in (step.get("with") or {})
    assert holders == [_TOKEN_STEP, _DEPLOY]
    assert "FLY_API_TOKEN" not in job["env"]


def test_actions_are_pinned_to_the_backup_workflow_commits(job):
    uses = [step["uses"] for step in job["steps"] if "uses" in step]
    assert uses == [_CHECKOUT, _SETUP_FLYCTL]
    for ref in uses:
        assert re.fullmatch(r"[a-z0-9/_-]+@[0-9a-f]{40}", ref)
    # No ref: the checkout is the dispatched commit. Full history, so the
    # schema-check step can see #152.
    assert _step(job, _CHECKOUT_STEP)["with"] == {
        "persist-credentials": False, "fetch-depth": 0}
    assert _step(job, _FLYCTL)["with"] == {"version": "0.5.1"}


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
    env = _step(job, _HEALTH)["env"]
    assert env["HEALTH_URL"] == f"https://{_STAGING}.fly.dev/health"
    attempts = int(env["HEALTH_ATTEMPTS"])
    interval = int(env["HEALTH_INTERVAL_SECONDS"])
    assert 1 <= attempts and 0 < interval
    # Each attempt is at most a 10 s curl plus the interval.
    assert attempts * (10 + interval) <= 15 * 60


def _git(cwd, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


def _has_commit(cwd, sha) -> bool:
    return _git(cwd, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0


def test_the_schema_guard_commit_is_152(job):
    assert _step(job, _SCHEMA_STEP)["env"]["SCHEMA_GUARD_COMMIT"] == _SCHEMA_GUARD
    if not _has_commit(_ROOT, _SCHEMA_GUARD):
        pytest.skip("this checkout's history does not reach #152")
    # The pinned commit is the one that brought in the schema check and the
    # newer-chronicle refusal: present in it, absent from its parent.
    for needle, path in (("read_checkout_schema", "scripts/deploy.sh"),
                         ("SchemaTooNewError", "persistence/__init__.py")):
        after = _git(_ROOT, "show", f"{_SCHEMA_GUARD}:{path}", check=False)
        before = _git(_ROOT, "show", f"{_SCHEMA_GUARD}^:{path}", check=False)
        if after.returncode or before.returncode:
            pytest.skip(f"{path} at #152 or its parent is not readable here")
        assert needle in after.stdout, (needle, path)
        assert needle not in before.stdout, (needle, path)


# --- Running the workflow's step scripts ------------------------------------

def _context(*, token=_TOKEN):
    return {"secrets.FLY_API_TOKEN_STAGING": token}


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


@pytest.fixture(scope="module")
def head_sha() -> str:
    return _git(_ROOT, "rev-parse", "HEAD").stdout.strip()


def _run_step(tmp_path, job, name, *, context=None, env=None, cwd=None,
              head=None):
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
        "GITHUB_REF": _MAIN,
        "FLY_STUB_LOG": str(fly_log),
        "FLY_STUB_APPLIED": str(_known()),
        "FLY_STUB_KNOWN": str(_known()),
        "CURL_STUB_LOG": str(curl_log),
    }
    if head is not None:
        run_env["GITHUB_SHA"] = head
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
        cwd=cwd or _ROOT, env=run_env, text=True, capture_output=True,
        check=False)
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


def test_guard_step_accepts_the_staging_app_from_main(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(tmp_path, job, _GUARD)
    assert proc.returncode == 0, proc.stderr
    assert "Target app: enfolded-staging" in proc.stdout
    assert "Ref: refs/heads/main" in proc.stdout
    assert calls == []


@pytest.mark.parametrize("app", [
    _PRODUCTION, "", "Enfolded-Staging", "enfolded-staging ", " enfolded-staging",
    "enfolded-staging-2", "enfolded-stagin", "enfolded-staging\n",
])
def test_guard_step_refuses_any_other_app(tmp_path, job, app):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _GUARD, env={"FLY_APP": app})
    assert proc.returncode == 1
    assert "::error::This workflow deploys only enfolded-staging" in proc.stdout
    assert "Target app" not in proc.stdout
    assert calls == []


def test_guard_step_refuses_an_unset_app(job):
    script = _step(job, _GUARD)["run"]
    unset = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "GITHUB_REF": _MAIN},
        text=True, capture_output=True, check=False)
    assert unset.returncode == 1
    assert "deploys only enfolded-staging" in unset.stdout


@pytest.mark.parametrize("ref", [
    # Fork pull request code, an unmerged branch, a pre-#152 tag, a tag that
    # shadows the branch name, and near misses.
    "refs/pull/1/head", "refs/pull/1/merge", "refs/heads/claude/staging-deploy-workflow",
    "refs/tags/v0.1.1-qa.2", "refs/tags/main", "refs/heads/main2",
    "refs/heads/mai", "main", "", " refs/heads/main", "refs/heads/main\n",
    "refs/heads/Main",
])
def test_guard_step_refuses_any_ref_but_main(tmp_path, job, ref):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _GUARD, env={"GITHUB_REF": ref})
    assert proc.returncode == 1
    assert "::error::This workflow deploys only main" in proc.stdout
    assert "Target app" not in proc.stdout
    assert calls == []


def test_guard_step_refuses_an_unset_ref(job):
    script = _step(job, _GUARD)["run"]
    unset = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "FLY_APP": _STAGING},
        text=True, capture_output=True, check=False)
    assert unset.returncode == 1
    assert "deploys only main" in unset.stdout


def test_token_step_refuses_cleanly_when_the_secret_is_unset(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _TOKEN_STEP, context=_context(token=""))
    assert proc.returncode == 1
    assert "::error::FLY_API_TOKEN_STAGING is not set" in proc.stdout
    assert "fly tokens create deploy -a enfolded-staging" in proc.stdout
    assert "staging environment" in proc.stdout
    assert proc.stderr == ""
    assert calls == []


def test_token_step_never_prints_the_token(tmp_path, job):
    proc, *_ = _run_step(tmp_path, job, _TOKEN_STEP)
    assert proc.returncode == 0, proc.stderr
    assert "FLY_API_TOKEN_STAGING is set." in proc.stdout
    assert _TOKEN not in proc.stdout + proc.stderr


# --- The schema-check step ---------------------------------------------------

def _commit(repo: Path, message: str) -> str:
    _git(repo, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture()
def history(tmp_path):
    """root -> guard -> after, and root -> before (a line without the guard)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "-c", "init.defaultBranch=main", "init", "-q")
    shas = {"root": _commit(repo, "root")}
    shas["guard"] = _commit(repo, "guard")
    shas["after"] = _commit(repo, "after")
    _git(repo, "checkout", "-q", "-b", "old", shas["root"])
    shas["before"] = _commit(repo, "before")
    return repo, shas


def _at(repo: Path, sha: str) -> None:
    _git(repo, "checkout", "-q", "--detach", sha)


def _schema_step(tmp_path, job, repo, guard, *, head=None):
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _SCHEMA_STEP, cwd=repo,
        head=sha if head is None else head,
        env={"SCHEMA_GUARD_COMMIT": guard})
    assert calls == []
    return proc


@pytest.mark.parametrize("at", ["guard", "after"])
def test_schema_step_accepts_a_commit_at_or_after_the_guard(tmp_path, job, history, at):
    repo, shas = history
    _at(repo, shas[at])
    proc = _schema_step(tmp_path, job, repo, shas["guard"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"descends from {shas['guard']} (#152)" in proc.stdout


@pytest.mark.parametrize("at", ["root", "before"])
def test_schema_step_refuses_a_commit_without_the_guard(tmp_path, job, history, at):
    repo, shas = history
    _at(repo, shas[at])
    proc = _schema_step(tmp_path, job, repo, shas["guard"])
    assert proc.returncode == 1
    assert "does not descend from" in proc.stdout
    assert "has no schema check. Refusing." in proc.stdout


def test_schema_step_refuses_a_checkout_that_is_not_the_dispatched_commit(
        tmp_path, job, history):
    repo, shas = history
    _at(repo, shas["after"])
    proc = _schema_step(tmp_path, job, repo, shas["guard"], head=shas["guard"])
    assert proc.returncode == 1
    assert "not the dispatched commit" in proc.stdout
    proc = _schema_step(tmp_path, job, repo, shas["guard"], head="")
    assert proc.returncode == 1
    assert "not the dispatched commit" in proc.stdout


def test_schema_step_refuses_when_the_guard_is_not_in_history(tmp_path, job, history):
    repo, shas = history
    _at(repo, shas["after"])
    proc = _schema_step(tmp_path, job, repo, "0" * 40)
    assert proc.returncode == 1
    assert "is not in this checkout's history" in proc.stdout
    # A depth-1 checkout of a good commit cannot confirm it either.
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", "--branch", "main",
         f"file://{repo}", str(shallow))
    assert _git(shallow, "rev-parse", "HEAD").stdout.strip() == shas["after"]
    proc = _schema_step(tmp_path, job, shallow, shas["guard"])
    assert proc.returncode == 1
    assert "is not in this checkout's history" in proc.stdout


def test_schema_step_accepts_this_checkout(tmp_path, job, head_sha):
    if not _has_commit(_ROOT, _SCHEMA_GUARD):
        pytest.skip("this checkout's history does not reach #152")
    proc, *_ = _run_step(tmp_path, job, _SCHEMA_STEP, head=head_sha)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("ref", ["v0.1.1-qa.2", "18e5bbd"])
def test_schema_step_refuses_real_commits_before_152(tmp_path, job, ref):
    # v0.1.1-qa.2 and #151 ship a deploy.sh with no schema check.
    found = _git(_ROOT, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False)
    if found.returncode != 0 or not _has_commit(_ROOT, _SCHEMA_GUARD):
        pytest.skip(f"{ref} or #152 is not in this checkout's history")
    sha = found.stdout.strip()
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--shared", "--no-checkout", str(_ROOT), str(clone))
    _git(clone, "update-ref", "--no-deref", "HEAD", sha)
    proc = _schema_step(tmp_path, job, clone, _SCHEMA_GUARD)
    assert proc.returncode == 1
    assert f"{sha} does not descend from {_SCHEMA_GUARD}" in proc.stdout


# --- The deploy step ---------------------------------------------------------

def test_deploy_step_backs_up_then_deploys_only_staging(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(tmp_path, job, _DEPLOY)
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


def test_deploy_step_refuses_an_older_checkout_against_a_newer_chronicle(tmp_path, job):
    # The schema check deploy.sh runs: a live chronicle one migration ahead
    # of this checkout stops the run after the backup and the probe.
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _DEPLOY, env={"FLY_STUB_APPLIED": str(_known() + 1)})
    assert proc.returncode == 1
    assert "is older than the live chronicle schema" in proc.stderr
    assert [c[0] for c in calls] == ["ssh", "ssh"]
    _assert_only_staging(calls)


def test_deploy_step_never_skips_the_backup(tmp_path, job):
    # With no machine to back up, the run stops at the backup and deploys
    # nothing. A first deploy is the owner's terminal step (runbook 3a).
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _DEPLOY, env={"FLY_STUB_BACKUP_FAIL": "1"})
    assert proc.returncode == 1
    assert not any(call[0] == "deploy" for call in calls)
    script = _step(job, _DEPLOY)["run"]
    assert "--first-deploy" not in script
    assert "args" not in script


def test_deploy_step_refuses_over_a_failed_backup(tmp_path, job):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _DEPLOY, env={"FLY_STUB_BACKUP_FAIL": "1"})
    assert proc.returncode == 1
    assert "unbacked chronicle" in proc.stderr
    assert [c[0] for c in calls] == ["ssh"]
    _assert_only_staging(calls)


@pytest.mark.parametrize("app", [_PRODUCTION, "", "enfolded-staging-2"])
def test_deploy_step_refuses_another_app_before_deploy_sh(tmp_path, job, app):
    proc, calls, _curls, _summary = _run_step(
        tmp_path, job, _DEPLOY, env={"FLY_APP": app})
    assert proc.returncode == 1
    assert "::error::FLY_APP is not enfolded-staging" in proc.stdout
    assert calls == []


def test_deploy_step_passes_the_app_explicitly(job):
    # Even if the job env were changed after the guard, deploy.sh is told
    # the staging app by name.
    script = _step(job, _DEPLOY)["run"]
    lines = [line.strip() for line in script.splitlines()
             if "scripts/deploy.sh" in line and not line.strip().startswith("#")]
    assert lines == ["FLY_APP=enfolded-staging bash scripts/deploy.sh"]


# --- The health and record steps ---------------------------------------------

def test_health_step_passes_on_status_ok(tmp_path, job):
    proc, calls, curls, summary = _run_step(
        tmp_path, job, _HEALTH,
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
        tmp_path, job, _HEALTH,
        env={"HEALTH_ATTEMPTS": "4", "HEALTH_INTERVAL_SECONDS": "0",
             "CURL_STUB_OK_ON": "1", "CURL_STUB_BODY": body})
    assert proc.returncode == 1
    assert len(curls) == 4
    assert "::error::Staging /health did not answer status ok in 4 attempts." in proc.stdout
    assert "- Health: not ok after 4 attempts" in summary


def test_health_step_accepts_compact_json(tmp_path, job):
    proc, _calls_, curls, _summary = _run_step(
        tmp_path, job, _HEALTH,
        env={"HEALTH_ATTEMPTS": "2", "HEALTH_INTERVAL_SECONDS": "0",
             "CURL_STUB_OK_ON": "1", "CURL_STUB_BODY": '{"status":"ok"}'})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(curls) == 1


def test_health_step_fails_when_staging_never_answers(tmp_path, job):
    proc, _calls_, curls, _summary = _run_step(
        tmp_path, job, _HEALTH,
        env={"HEALTH_ATTEMPTS": "3", "HEALTH_INTERVAL_SECONDS": "0"})
    assert proc.returncode == 1
    assert len(curls) == 3


def test_record_step_writes_the_target_to_the_summary(tmp_path, job):
    proc, calls, _curls, summary = _run_step(tmp_path, job, _RECORD)
    assert proc.returncode == 0, proc.stderr
    assert "- App: `enfolded-staging` (disposable staging twin)" in summary
    assert "- Ref: `refs/heads/main`" in summary
    assert re.search(r"- Commit: `[0-9a-f]{40}`", summary)
    assert _TOKEN not in proc.stdout + summary
    assert calls == []
