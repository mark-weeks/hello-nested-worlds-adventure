"""Contract guards for the shipped browser client.

REGRESSION (P0): the React/Pixi app served at /app — the client the invite URL
used to point testers at — never called /speak or /puzzle, so the two headline
mechanics (talk to a Claude-voiced node, solve a node's puzzle) were unreachable
in the marketed client. No test caught it because nothing asserted a
frontend↔endpoint contract. These tests assert the core-loop endpoints are
present in BOTH the React source and its built bundle, and that the invite URL
lands testers on a client that delivers the loop.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import main

_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_SRC = _ROOT / "frontend" / "src"
_BUILT_APP = _ROOT / "static" / "app" / "assets"

# The endpoints that make /app a playable client rather than a viewer.
_CORE_LOOP_ENDPOINTS = ("/speak", "/puzzle/attempt", "/puzzle?seed")


def _all_text(root: Path, suffix: str) -> str:
    return "\n".join(p.read_text(errors="ignore")
                     for p in root.rglob(f"*{suffix}"))


class TestReactSourceWiresCoreLoop:
    def test_source_calls_speak_and_puzzle(self):
        src = _all_text(_FRONTEND_SRC, ".jsx") + _all_text(_FRONTEND_SRC, ".js")
        for ep in _CORE_LOOP_ENDPOINTS:
            assert ep in src, (
                f"React source does not call {ep!r} — the /app client can't "
                "reach the core loop (talk to node / solve puzzle)"
            )


class TestBuiltBundleWiresCoreLoop:
    @pytest.mark.skipif(not _BUILT_APP.exists(),
                        reason="static/app not built; run: cd frontend && npm run build")
    def test_built_bundle_calls_speak_and_puzzle(self):
        # The committed bundle is what the server actually serves at /app;
        # assert it was rebuilt after the source was wired.
        bundle = _all_text(_BUILT_APP, ".js")
        for ep in _CORE_LOOP_ENDPOINTS:
            assert ep in bundle, (
                f"built /app bundle is missing {ep!r} — rebuild the frontend "
                "(cd frontend && npm run build) so the shipped client matches "
                "the source"
            )


class TestInviteUrlTargetsPlayableClient:
    def test_invite_url_lands_on_root_not_bare_app(self):
        url = main.invite_share_url("nw_deadbeef", "Alice")
        # Must land on `/` (feature-complete, no-WebGL-dependency), carrying the
        # credential and name so the tester is one click from playing.
        assert url.startswith("<BASE>/?key=nw_deadbeef")
        assert "name=Alice" in url
        assert "/app?" not in url

    def test_invite_url_encodes_name(self):
        url = main.invite_share_url("nw_x", "Ada Lovelace")
        assert "Ada%20Lovelace" in url or "Ada+Lovelace" in url
