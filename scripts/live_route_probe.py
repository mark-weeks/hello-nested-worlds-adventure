#!/usr/bin/env python3
"""Authenticated live-route probe for one temporary world.

Drives the ordinary gameplay endpoints with an acknowledged check key and
reads that machine's model-spend ledger. It names no provider and no model.
The check key travels only in the X-Beta-Key header.

Cases, each prepared by the operator before the run:

- success: /speak and /agent/voice return HTTP 200 and ai true, and an Act
  free-text intention is accepted with a receipt. Each dispatch settles.
- hold: shared voice returns the hold line, and Ideas and a published
  profile return their hold lines.
- quiet: only the voice allowance is spent. Classification still settles,
  and voice returns the quiet line with no voice reservation.
- identity: with the kill switch on, a sincere identity question still
  receives the authored honesty answer.

An uncertain reservation fails ADR-035 requirement 4 even when the reply
itself was usable. Any world that is not declared temporary is refused
before a place is discovered. Running this acknowledges the current notice
for the check key, including the age confirmation: run it only as the
operator who holds that key.

The shared line is locally ambiguous, so classification is part of the
pass on a server that classifies only ambiguous lines and on one that
classifies every shared line.
"""
from __future__ import annotations

import argparse
from collections import Counter
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from consciousness import honesty  # noqa: E402
from server import guard, moderation  # noqa: E402

# Seven digits make the local screen ambiguous without naming a person.
# A later change that classifies every shared line still classifies this one.
SHARED_LINE = "A traveler counts 1234567 lights."
IDENTITY_LINE = "Are you human?"
INTENTION = "brighten the quiet between the lights"
AGENT_NAME = "Tessera"
_LIMIT = 1024 * 1024
_VOICE_TASKS = frozenset({"node", "inhabitant", "intent"})
_USAGE_COUNTS = ("input_tokens", "output_tokens", "cache_read_tokens")


class ProbeError(Exception):
    """A closed-set failure. The message never carries a key or a reply."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _origin(url: str) -> str:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
        if (parsed.scheme not in {"http", "https"} or not hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError
        try:
            local = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            local = hostname.lower() == "localhost"
        if parsed.scheme == "http" and not local:
            raise ValueError
    except ValueError:
        raise ProbeError(
            "Use an HTTPS origin, or HTTP loopback, without credentials, path or query."
        ) from None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _load_key(args) -> str:
    sources = [args.key is not None, args.key_file is not None,
               bool(os.environ.get("ENFOLDED_LIVE_ROUTE_KEY"))]
    if sum(sources) != 1:
        raise ProbeError(
            "Pass the check key once, with --key-file, --key, or ENFOLDED_LIVE_ROUTE_KEY."
        )
    if args.key is not None:
        raw = args.key
    elif args.key_file is not None:
        try:
            raw = Path(args.key_file).read_text(encoding="utf-8")
        except OSError:
            raise ProbeError("Could not read the check key file.") from None
    else:
        raw = os.environ.get("ENFOLDED_LIVE_ROUTE_KEY", "")
    key = raw.strip()
    if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise ProbeError("The check key is empty or contains invalid header characters.")
    return key


def _request(origin: str, method: str, path: str, payload, timeout: float,
             label: str, key: str | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {}
    if key is not None:
        headers["X-Beta-Key"] = key
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(origin + path, data=data, headers=headers, method=method)
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(_LIMIT + 1)
    except HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read(_LIMIT + 1)
        except (OSError, ValueError):
            raw = b""
        exc.close()
        if status in {301, 302, 303, 307, 308}:
            raise ProbeError(f"{label}: refused a redirect") from None
    except (URLError, TimeoutError, OSError):
        raise ProbeError(f"{label}: could not reach the server") from None
    if len(raw) > _LIMIT:
        raise ProbeError(f"{label}: response exceeded the probe limit")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ProbeError(f"{label}: returned a document the probe could not read") from None
    if not isinstance(body, dict):
        raise ProbeError(f"{label}: returned a document the probe could not read")
    return status, body


def _expect(status: int, actual: int, label: str) -> None:
    if actual != status:
        if actual == 403:
            raise ProbeError(f"{label}: the check key was refused")
        if actual == 428:
            raise ProbeError(f"{label}: the participation notice was not accepted")
        if actual == 404:
            raise ProbeError(f"{label}: the place was not found")
        raise ProbeError(f"{label}: HTTP {actual}")


def _ledger(path: Path) -> list[sqlite3.Row]:
    if not path.is_file():
        raise ProbeError("the ledger database was not found")
    try:
        conn = sqlite3.connect(path, timeout=5)
    except sqlite3.Error:
        raise ProbeError("the ledger could not be read") from None
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return list(conn.execute(
            """SELECT r.id, r.task, r.status, r.reserved_microusd, r.accounted_microusd,
                      r.usage_json, r.resolved_model, p.policy_json
               FROM model_spend_reservations r
               JOIN model_spend_policies p ON p.digest = r.policy_digest"""
        ))
    except sqlite3.Error:
        raise ProbeError("the ledger could not be read") from None
    finally:
        conn.close()


def _ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {row["id"] for row in _ledger(path)}


def _new_rows(path: Path, before: set[str]) -> list[sqlite3.Row]:
    return [row for row in _ledger(path) if row["id"] not in before]


def _approved(policy_json: str, task: str) -> list[str]:
    try:
        document = json.loads(policy_json)
        models = document["routes"][task]["resolved_models"]
    except (TypeError, KeyError, ValueError):
        raise ProbeError("the stored policy could not be read") from None
    if not isinstance(models, list) or any(type(item) is not str or not item for item in models):
        raise ProbeError("the stored policy could not be read")
    return models


def _assert_settled(row: sqlite3.Row) -> None:
    status = row["status"]
    if status == "uncertain":
        raise ProbeError("failed ADR-035 requirement 4: a reservation status is uncertain")
    if status != "settled":
        raise ProbeError(f"a reservation status is {status}")
    reserved = row["reserved_microusd"]
    accounted = row["accounted_microusd"]
    if type(reserved) is not int or type(accounted) is not int or accounted > reserved:
        raise ProbeError("accounted microUSD exceeded the reservation")
    try:
        usage = json.loads(row["usage_json"])
    except (TypeError, ValueError):
        usage = None
    if not isinstance(usage, dict) or any(
            type(usage.get(field)) is not int or usage[field] < 0 for field in _USAGE_COUNTS):
        raise ProbeError("usage did not carry prompt, completion and cached-token counts")
    resolved = row["resolved_model"]
    if type(resolved) is not str or resolved not in _approved(row["policy_json"], row["task"]):
        raise ProbeError("resolved model is not in that task's approved resolved_models")


def _assert_dispatch(path: Path, before: set[str], expected: Counter) -> set[str]:
    rows = _new_rows(path, before)
    found = Counter(row["task"] for row in rows)
    if found != expected:
        raise ProbeError("ledger tasks did not match this call")
    for row in rows:
        _assert_settled(row)
    return before | {row["id"] for row in rows}


def _forbid_voice(path: Path | None, before: set[str]) -> None:
    if path is None:
        return
    if any(row["task"] in _VOICE_TASKS for row in _new_rows(path, before)):
        raise ProbeError("a voice reservation was written during a hold")


def _discover(origin: str, key: str, timeout: float) -> dict:
    status, body = _request(origin, "GET", "/world?depth=1", None, timeout, "world", key)
    _expect(200, status, "world")
    world = body.get("world")
    if (not isinstance(world, dict) or type(world.get("name")) is not str or not world["name"]
            or type(world.get("level")) is not str or not world["level"]):
        raise ProbeError("world: the place could not be read")
    return world


def _voice(origin: str, key: str, timeout: float, path: str, payload: dict, label: str) -> tuple[int, dict]:
    status, body = _request(origin, "POST", path, payload, timeout, label, key)
    _expect(200, status, label)
    return status, body


def _assert_live(body: dict, label: str) -> None:
    if body.get("ai") is not True:
        raise ProbeError(f"{label}: ai was not true")
    response = body.get("response")
    if type(response) is not str or not response.strip():
        raise ProbeError(f"{label}: voice returned no line")
    if response == moderation.HOLD_LINE:
        raise ProbeError(f"{label}: voice returned the hold line")
    if response == guard.QUIET_RESPONSE:
        raise ProbeError(f"{label}: voice returned the quiet line")


def _assert_hold(body: dict, label: str) -> None:
    if (body.get("response") != moderation.HOLD_LINE or body.get("held") is not True
            or body.get("ai") is not False):
        raise ProbeError(f"{label}: the shared hold line was not returned")


def _assert_quiet(body: dict, label: str) -> None:
    if (body.get("response") != guard.QUIET_RESPONSE or body.get("ai") is not False
            or body.get("held") not in (None, False)):
        raise ProbeError(f"{label}: the quiet line was not returned")


def _assert_product_hold(status: int, body: dict, line: str, label: str) -> None:
    if status != 422 or body.get("error") != line or body.get("held") is not True:
        raise ProbeError(f"{label}: its hold line was not returned")


def _acknowledge(origin: str, key: str, timeout: float, notice: dict) -> None:
    if notice.get("ready") is not True or type(notice.get("revision")) is not str or not notice["revision"]:
        raise ProbeError("the participation notice is not ready")
    if notice.get("required") is True and notice.get("accepted") is not True:
        status, body = _request(
            origin, "POST", "/participation",
            {"accepted": True, "revision": notice["revision"], "age_confirmed": True},
            timeout, "participation", key,
        )
        _expect(200, status, "participation")
        if body.get("accepted") is not True:
            raise ProbeError("participation: the notice was not accepted")


def _success(origin: str, key: str, timeout: float, place: dict, db: Path) -> dict:
    name = place["name"]
    status, arrived = _request(
        origin, "POST", "/position", {"node": name, "depth": 1}, timeout, "position", key,
    )
    _expect(200, status, "position")
    if arrived.get("saved") is not True:
        raise ProbeError("position: could not arrive at the place")
    before = _ids(db)
    speak = {"message": SHARED_LINE, "node_name": name}
    _, body = _voice(origin, key, timeout, "/speak", speak, "speak")
    _assert_live(body, "speak")
    before = _assert_dispatch(db, before, Counter({"moderation": 1, "node": 1}))
    agent = {"message": SHARED_LINE, "node_name": name, "agent_name": AGENT_NAME}
    _, body = _voice(origin, key, timeout, "/agent/voice", agent, "agent voice")
    _assert_live(body, "agent voice")
    before = _assert_dispatch(db, before, Counter({"moderation": 1, "inhabitant": 1}))
    status, body = _request(
        origin, "POST", "/interventions/commit",
        {"node": name, "version": 3, "request_id": "probe-act-01", "intention": INTENTION},
        timeout, "intention", key,
    )
    _expect(200, status, "intention")
    if (body.get("accepted") is not True or type(body.get("id")) is not str or not body["id"]
            or "ai" in body):
        raise ProbeError("intention: the accepted receipt was not returned")
    _assert_dispatch(db, before, Counter({"intent": 1}))
    return {"case": "success", "settled": {"moderation": 2, "node": 1, "inhabitant": 1, "intent": 1}}


def _hold(origin: str, key: str, timeout: float, place: dict, db: Path | None) -> dict:
    name = place["name"]
    before = _ids(db)
    _, body = _voice(origin, key, timeout, "/speak",
                     {"message": SHARED_LINE, "node_name": name}, "speak")
    _assert_hold(body, "speak")
    _, body = _voice(origin, key, timeout, "/agent/voice",
                     {"message": SHARED_LINE, "node_name": name, "agent_name": AGENT_NAME},
                     "agent voice")
    _assert_hold(body, "agent voice")
    status, body = _request(
        origin, "POST", "/ideas/submit",
        {"title": "A count of lights", "description": SHARED_LINE,
         "request_id": "probe-idea01", "public_credit": False},
        timeout, "ideas", key,
    )
    _assert_product_hold(status, body, moderation.IDEAS_HOLD, "ideas")
    status, body = _request(
        origin, "POST", "/profile/save",
        {"bio": SHARED_LINE, "goals": "Watch the lights.", "published": True},
        timeout, "profile", key,
    )
    _assert_product_hold(status, body, moderation.PROFILE_HOLD, "profile")
    _forbid_voice(db, before)
    return {"case": "hold", "speak": "held", "agent_voice": "held", "ideas": "held", "profile": "held"}


def _quiet(origin: str, key: str, timeout: float, place: dict, db: Path) -> dict:
    name = place["name"]
    before = _ids(db)
    _, body = _voice(origin, key, timeout, "/speak",
                     {"message": SHARED_LINE, "node_name": name}, "speak")
    _assert_quiet(body, "speak")
    before = _assert_dispatch(db, before, Counter({"moderation": 1}))
    _, body = _voice(origin, key, timeout, "/agent/voice",
                     {"message": SHARED_LINE, "node_name": name, "agent_name": AGENT_NAME},
                     "agent voice")
    _assert_quiet(body, "agent voice")
    _assert_dispatch(db, before, Counter({"moderation": 1}))
    return {"case": "quiet", "moderation_settled": 2, "voice_reservations": 0}


def _identity(origin: str, key: str, timeout: float, place: dict, db: Path | None) -> dict:
    name = place["name"]
    before = _ids(db)
    _, body = _voice(origin, key, timeout, "/speak",
                     {"message": IDENTITY_LINE, "node_name": name}, "speak")
    if (body.get("ai") is not False or body.get("held") not in (None, False)
            or body.get("response") != honesty.place_answer(place["level"])):
        raise ProbeError("speak: the authored honesty answer was not returned")
    _, body = _voice(origin, key, timeout, "/agent/voice",
                     {"message": IDENTITY_LINE, "node_name": name, "agent_name": AGENT_NAME},
                     "agent voice")
    if (body.get("ai") is not False or body.get("held") not in (None, False)
            or body.get("response") != honesty.agent_answer(body.get("persona") if isinstance(body.get("persona"), str) else None)):
        raise ProbeError("agent voice: the authored honesty answer was not returned")
    if db is not None and _new_rows(db, before):
        raise ProbeError("a reservation was written for an authored honesty answer")
    return {"case": "identity", "ai": False}


def run(args) -> dict:
    origin = _origin(args.url)
    if args.timeout <= 0:
        raise ProbeError("the timeout must be positive")
    _, notice = _request(origin, "GET", "/participation", None, args.timeout, "participation")
    if notice.get("temporary") is not True:
        raise ProbeError("refusing a world that is not declared temporary")
    if args.case in {"success", "quiet"} and args.db is None:
        raise ProbeError("this case needs --db so the ledger can be checked")
    key = _load_key(args)
    _acknowledge(origin, key, args.timeout, notice)
    place = _discover(origin, key, args.timeout)
    db = None if args.db is None else Path(args.db)
    if args.case == "success":
        summary = _success(origin, key, args.timeout, place, db)
    elif args.case == "hold":
        summary = _hold(origin, key, args.timeout, place, db)
    elif args.case == "quiet":
        summary = _quiet(origin, key, args.timeout, place, db)
    else:
        summary = _identity(origin, key, args.timeout, place, db)
    print(json.dumps(summary, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--case", required=True, choices=("success", "hold", "quiet", "identity"))
    parser.add_argument("--key", default=None)
    parser.add_argument("--key-file", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--timeout", type=float, default=30)
    try:
        run(parser.parse_args(argv))
    except ProbeError as exc:
        print(f"live-route probe: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
