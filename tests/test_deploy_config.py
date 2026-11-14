"""Guards for the Fly.io deploy contract.

REGRESSION (P1): the Dockerfile / fly.toml / .dockerignore existed only as
fenced code inside docs/infrastructure/fly-deployment.md — never committed —
so `fly deploy` had nothing to build and the config was untested. These tests
assert the files exist AND that the launch-critical invariants hold: a single
always-on machine (so in-memory rate limits / rooms and the persisted spend
counters survive), a cheap gate-exempt health check that never calls the LLM,
the DB on the volume, and no secrets/dev-DB leaking into the image.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    p = _ROOT / name
    assert p.exists(), f"{name} must be committed at the repo root (deploy contract)"
    return p.read_text()


@pytest.fixture
def cfg():
    return tomllib.loads(_read("fly.toml"))


def test_deploy_files_exist():
    for name in ("Dockerfile", "fly.toml", ".dockerignore"):
        assert (_ROOT / name).exists(), f"missing deploy file: {name}"


class TestFlyToml:
    def test_external_routes_start_controlled_and_off(self, cfg, monkeypatch):
        from consciousness import model_policy, runtime

        # These are deploy defaults, not optional operator overrides. In
        # particular, the kill switches alone would not activate the durable
        # permission boundary if REQUIRE_MODEL_POLICY disappeared.
        safety = (model_policy.REQUIRED_ENV, "NESTED_WORLDS_DISABLE_AI",
                  "NESTED_WORLDS_DISABLE_IMAGES")
        assert {name: cfg["env"].get(name) for name in safety} == {
            name: "1" for name in safety}
        monkeypatch.delenv(model_policy.POLICY_ENV, raising=False)
        monkeypatch.delenv("NESTED_WORLDS_TEST_WORLD", raising=False)
        for name in safety:
            monkeypatch.setenv(name, cfg["env"][name])
        monkeypatch.setenv(runtime.PROVIDER_ENV, "unregistered_deploy_fixture")
        monkeypatch.setenv(runtime.SHARED_MODEL_ENV, " ")

        def forbidden(*_args, **_kwargs):
            pytest.fail("all-off production defaults resolved a provider")

        monkeypatch.setattr(runtime, "provider_for", forbidden)
        monkeypatch.setattr(runtime, "get_provider", forbidden)
        snapshot = model_policy.initialize()
        assert model_policy.active() and snapshot.enabled_routes == ()
        # A provider key or a switch changed after startup cannot grant a
        # route missing from the immutable production startup snapshot.
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key-added-after-startup")
        monkeypatch.setenv("NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY", "fixture-compatible-key")
        monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "0")
        monkeypatch.setenv("NESTED_WORLDS_DISABLE_IMAGES", "0")
        assert model_policy.current() is snapshot
        assert runtime.configured() is False
        for task in runtime.TASKS:
            assert runtime.configured(task) is False
            with pytest.raises(model_policy.ModelPolicyDenied):
                runtime.model_for(task)

    def test_single_always_on_machine(self, cfg):
        svc = cfg["http_service"]
        # Auto-stop would suspend the app when idle, dropping WS sessions and
        # clearing in-memory state; min_machines_running>=1 keeps it warm.
        assert svc["auto_stop_machines"] is False
        assert svc["min_machines_running"] >= 1

    def test_internal_port_matches_app(self, cfg):
        # The server binds 8080 (see Dockerfile CMD); the proxy must target it.
        assert cfg["http_service"]["internal_port"] == 8080

    def test_force_https(self, cfg):
        assert cfg["http_service"]["force_https"] is True

    def test_health_check_is_cheap_and_correct(self, cfg):
        health = cfg["http_service"]["checks"]["health"]
        assert health["path"] == "/health"      # gate-exempt, returns {"status":"ok"}
        assert health["method"].upper() == "GET"

    def test_db_lives_on_the_volume(self, cfg):
        # HOME=/data puts ~/.nested-worlds/worlds.db on the mounted volume,
        # and the volume must mount at that same path.
        assert cfg["env"]["HOME"] == "/data"
        assert cfg["mounts"]["destination"] == "/data"

    def test_launch_hosts_exactly_one_world(self, cfg):
        from multiverse.generator import DEFAULT_WORLD_SEED

        # Public world selection is an operator decision, never a player input.
        # Keeping this in committed config makes an accidental multi-world
        # launch a deploy-contract failure.
        seed = cfg["env"].get("NESTED_WORLDS_CANONICAL_SEED")
        assert seed is not None and str(seed).strip()
        assert int(seed) == DEFAULT_WORLD_SEED

    def test_ws_connection_cap_within_proxy_hard_limit(self, cfg):
        # The app's WS cap must not exceed the Fly proxy connection hard_limit,
        # or the proxy would shed connections the app still thinks it can hold.
        hard = cfg["http_service"]["concurrency"]["hard_limit"]
        app_cap = int(cfg["env"].get("NESTED_WORLDS_MAX_WS_CONNECTIONS", "128"))
        assert app_cap <= hard, (
            f"NESTED_WORLDS_MAX_WS_CONNECTIONS={app_cap} exceeds proxy "
            f"hard_limit={hard}"
        )


class TestDockerignore:
    def test_excludes_secrets_and_dev_db(self):
        body = _read(".dockerignore")
        for pattern in (".env", "*.db"):
            assert pattern in body, f".dockerignore must exclude {pattern!r}"


class TestDockerfile:
    def test_serves_on_8080_with_home_on_volume(self):
        body = _read("Dockerfile")
        assert "HOME=/data" in body
        assert "8080" in body

    def test_frontend_stage_copies_every_root_file_postbuild_reads(self):
        # `npm run build` triggers frontend/scripts/normalize-build.mjs, which
        # copies root files (`new URL("../../<name>", import.meta.url)`) into
        # static/app. Stage 1 of the Dockerfile builds inside /build with only
        # what it COPYs before `npm run build`, so any root file the script
        # reads but the stage does not copy makes `docker build` (and therefore
        # `fly deploy`) fail with ENOENT — a path no CI job exercises.
        script = _read("frontend/scripts/normalize-build.mjs")
        required = set(re.findall(r'\["([^"]+)",\s*"[^"]+"\]', script))
        assert required, "postbuild copy inventory not found in normalize-build.mjs"

        stage_one = _read("Dockerfile").split("# --- Stage 2")[0]
        copied: set[str] = set()
        for line in stage_one.splitlines():
            if "npm run build" in line:
                break
            if line.startswith("COPY "):
                copied.update(line.split()[1:-1])
        missing = sorted(required - copied)
        assert not missing, f"stage 1 never copies {missing} before npm run build"
