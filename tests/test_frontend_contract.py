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


class TestGatedFetchesCarryInviteKey:
    """REGRESSION (P1-4): every data / paid fetch in the React client must go
    through withKey(), or it 403s under the beta gate. The `/image` scene-
    background fetch was the lone bare fetch(), so in gated beta mode the fal.ai
    backgrounds — the /app headline feature — silently failed (403 swallowed by
    an empty .catch). Assert the gated endpoints are wrapped, in source and in
    the shipped bundle."""

    # Endpoints that are gated + (some) rate-limited server-side; a bare fetch
    # to any of these breaks under the invite gate.
    _GATED = ("/image", "/speak", "/puzzle/attempt")

    def test_source_wraps_gated_fetches_in_withkey(self):
        src = _all_text(_FRONTEND_SRC, ".jsx") + _all_text(_FRONTEND_SRC, ".js")
        # The specific fetch that regressed: /image must go through withKey().
        assert 'withKey("/image")' in src, (
            "React source calls /image without withKey() — the scene background "
            "will 403 under the beta gate"
        )
        # And there must be no bare fetch("/image" left anywhere.
        assert 'fetch("/image"' not in src, (
            'found a bare fetch("/image") — gated endpoints must be wrapped '
            "in withKey()"
        )

    @pytest.mark.skipif(not _BUILT_APP.exists(),
                        reason="static/app not built; run: cd frontend && npm run build")
    def test_built_bundle_forwards_key_on_image(self):
        # The minifier rewrites identifiers, but the "/image" string literal and
        # the withKey helper's `key=` query assembly both survive minification;
        # the bundle must still contain the /image path and the key-append
        # helper so the shipped client forwards the credential.
        bundle = _all_text(_BUILT_APP, ".js")
        assert "/image" in bundle, "built /app bundle no longer references /image"
        assert "key=" in bundle, (
            "built /app bundle has no key= query assembly — rebuild the frontend "
            "so the withKey() fix ships"
        )


class TestExplorerShellResilience:
    """REGRESSION (P1-1/P1-2/P1-3): the invite default landing page (`/`, the D3
    explorer) must (a) load D3 same-origin, not from the d3js.org CDN, (b) carry
    a mobile viewport meta so it isn't an unusable desktop crush on a phone, and
    (c) show first-run onboarding to INVITED users — who arrive with ?name= and
    skip the join modal, so the intro can't live inside that modal."""

    _INDEX = _ROOT / "static" / "index.html"
    _EXPLORER = _ROOT / "static" / "explorer.js"
    _VENDORED_D3 = _ROOT / "static" / "d3.v7.min.js"

    def test_d3_served_same_origin_not_cdn(self):
        html = self._INDEX.read_text()
        assert 'src="/d3.v7.min.js"' in html, "index.html must load vendored D3"
        # No <script> or CSP dependency on the external CDN. (A doc comment
        # mentioning the old host is fine; a script src / CSP host is not.)
        assert 'src="https://d3js.org' not in html
        assert self._VENDORED_D3.exists(), "vendored static/d3.v7.min.js is missing"
        assert "d3js.org v7" in self._VENDORED_D3.read_text(errors="ignore")[:80]

    def test_viewport_meta_present(self):
        html = self._INDEX.read_text()
        assert 'name="viewport"' in html and "width=device-width" in html

    def test_onboarding_shown_outside_join_modal(self):
        html = self._INDEX.read_text()
        js = self._EXPLORER.read_text()
        # A dedicated intro overlay exists (not folded into the name-entry modal).
        assert 'id="intro-modal"' in html
        assert 'id="btn-begin"' in html
        # It is gated on a first-run flag and runs ahead of the name/auto-join
        # split, so an invited (?name=) user still sees it exactly once.
        assert "nw_seen_intro" in js
        assert "btn-begin" in js
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
