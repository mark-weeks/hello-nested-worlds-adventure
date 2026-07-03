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
