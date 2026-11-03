"""A player name is one name under trim, NFKC and case folding (ADR-004 §7).

Uniqueness and the reserved names used to compare Python's ``str.lower()``
(or SQLite's ASCII-only ``lower(trim(name))`` index), so 'Élodie' and
'élodie', or a composed and a decomposed 'Élodie' that look identical, could
both be registered, and a fullwidth 'Ｓｃｏｕｔ' passed the reserved-name
check. Every path now compares ``persistence.name_key``. These tests drive
the real mint CLI, ``POST /register``, the keyless WebSocket join, the
body-name path and the store, and read what was stored.

Out of scope, by statement: NFKC does not fold confusable letters from
other scripts (Cyrillic 'а' for Latin 'a'), nor invisible format
characters such as a zero-width space.
"""
from __future__ import annotations

import sqlite3
import string
import threading
import time
import unicodedata
from urllib.parse import quote

import pytest

import main
import persistence
from consciousness import WANDERER_CAST
from multiverse.generator import generate_node_hierarchy
from persistence import participants
from server import _Handler, _ThreadedServer, guard
from tests.test_agent_identities import _request
from tests.test_day_one_recording import _ws_connect

ELODIE = "\u00c9lodie"           # 'Élodie' with a precomposed É
ELODIE_LOWER = "\u00e9lodie"     # 'élodie'
ELODIE_NFD = "E\u0301lodie"      # 'E' + combining acute: looks like ELODIE

KEY_A = "nw_" + "a" * 32
KEY_B = "nw_" + "b" * 32
KEY_C = "nw_" + "c" * 32

TWINS = [
    pytest.param(ELODIE, ELODIE_LOWER, id="capital-then-lower"),
    pytest.param(ELODIE_LOWER, ELODIE, id="lower-then-capital"),
    pytest.param(ELODIE, ELODIE_NFD, id="composed-then-decomposed"),
    pytest.param(ELODIE_NFD, ELODIE, id="decomposed-then-composed"),
    pytest.param(ELODIE_NFD, ELODIE_LOWER.upper(), id="decomposed-then-upper"),
    pytest.param("Ｅｌｏｄｉｅ", "elodie", id="fullwidth-then-ascii"),
]


@pytest.fixture()
def open_srv():
    """A real server; the gate stays open until a test mints or creates an invite."""
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(5)


class _MintArgs:
    invite_action = "mint"
    note = None
    unscreened = True

    def __init__(self, name):
        self.name = name


def _mint_cli(name):
    main.cmd_invite(_MintArgs(name))


def _register(port, token, name):
    return _request(port, "/register", key="", body={"invite": token, "name": name})


def _stored_names():
    return sorted(row["name"] for row in persistence.list_invite_keys(include_revoked=True))


# ── Twins are one name, in either order, on every claiming path ─────────────

@pytest.mark.parametrize("first, second", TWINS)
def test_the_mint_cli_refuses_a_twin_in_either_order(first, second, capsys):
    _mint_cli(first)
    with pytest.raises(SystemExit, match="already registered — choose another name"):
        _mint_cli(second)
    assert _stored_names() == [first]


@pytest.mark.parametrize("first, second", TWINS)
def test_register_refuses_a_twin_and_keeps_the_token(open_srv, first, second):
    persistence.create_registration_token("nwr_one")
    persistence.create_registration_token("nwr_two")
    status, data = _register(open_srv, "nwr_one", first)
    assert status == 200 and data["name"] == first, data
    status, data = _register(open_srv, "nwr_two", second)
    assert status == 409, data
    assert data == {"error": f"the name '{second}' is taken — choose another"}
    # One transaction: the refused claim spent nothing and minted nothing.
    assert persistence.lookup_registration_token("nwr_two") is not None
    assert _stored_names() == [first]


def test_a_minted_name_and_a_registered_twin_refuse_each_other(open_srv, capsys):
    _mint_cli(ELODIE)
    persistence.create_registration_token("nwr_one")
    status, data = _register(open_srv, "nwr_one", ELODIE_LOWER)
    assert status == 409, data
    persistence.create_registration_token("nwr_two")
    status, data = _register(open_srv, "nwr_two", "Zo\u00eb")       # 'Zoë'
    assert status == 200, data
    with pytest.raises(SystemExit, match="already registered"):
        _mint_cli("ZOE\u0308")                                      # 'ZOË', decomposed
    assert _stored_names() == sorted([ELODIE, "Zo\u00eb"])
    assert persistence.lookup_registration_token("nwr_one") is not None


def test_a_stored_name_keeps_the_spelling_it_was_typed_with(open_srv):
    persistence.create_registration_token("nwr_one")
    status, data = _register(open_srv, "nwr_one", f"  {ELODIE_NFD} ")
    assert status == 200 and data["name"] == ELODIE_NFD
    # Trimmed as before, and never normalized: the decomposed form stays.
    assert _stored_names() == [ELODIE_NFD]
    assert guard.registered_name(data["key"]) == ELODIE_NFD
    _mint_cli("Ｍｉｒａ")
    assert "Ｍｉｒａ" in _stored_names()


# ── German sharp s ──────────────────────────────────────────────────────────

def test_sharp_s_is_the_same_name_as_ss(open_srv, capsys):
    """``str.casefold`` maps 'ß' and the capital 'ẞ' to 'ss' (``lower`` does
    not), so 'Straße', 'STRASSE', 'Strasse' and 'STRAẞE' are one name, and
    'Teßera' is the cast name Tessera."""
    assert persistence.name_key("Straße") == persistence.name_key("STRASSE") == "strasse"
    assert persistence.name_key("STRA\u1e9eE") == "strasse"
    _mint_cli("Straße")
    for twin in ("STRASSE", "Strasse", "STRA\u1e9eE", "straße"):
        with pytest.raises(SystemExit, match="already registered"):
            _mint_cli(twin)
    persistence.create_registration_token("nwr_one")
    status, data = _register(open_srv, "nwr_one", "Strasse")
    assert status == 409, data
    status, data = _register(open_srv, "nwr_one", "Teßera")
    assert status == 403 and data["error"] == "'Teßera' belongs to the world — choose another name"
    assert _stored_names() == ["Straße"]


# ── Reserved names in compatibility spellings ───────────────────────────────

RESERVED_SPELLINGS = [
    pytest.param("Ｓｃｏｕｔ", id="fullwidth-scout"),
    pytest.param("Ｔｅｓｓｅｒａ", id="fullwidth-cast-name"),
    pytest.param("Cartographer-\u2468", id="circled-digit-cast-name"),
    pytest.param("\U0001d40e\U0001d41b\U0001d42c\U0001d41e\U0001d42b\U0001d42f"
                 "\U0001d41e\U0001d42b", id="math-bold-observer"),
    pytest.param("The\u00a0Locksmith", id="no-break-space-cast-name"),
]


def test_every_reserved_spelling_below_names_a_server_identity():
    names = {"Scout", "Tessera", "Cartographer-9", "Observer", "The Locksmith"}
    assert names <= set(WANDERER_CAST) | {"Scout", "Observer"}
    from agents import identities
    for param in RESERVED_SPELLINGS:
        assert identities.canonical(param.values[0]) in names, param.id


@pytest.mark.parametrize("name", RESERVED_SPELLINGS)
def test_register_refuses_a_reserved_name_in_any_compatibility_form(open_srv, name):
    persistence.create_registration_token("nwr_live")
    status, data = _register(open_srv, "nwr_live", name)
    assert status == 403 and data == {
        "error": f"'{name}' belongs to the world — choose another name"}
    assert persistence.lookup_registration_token("nwr_live") is not None
    assert persistence.list_invite_keys() == []


@pytest.mark.parametrize("name", RESERVED_SPELLINGS)
def test_keyless_ws_join_refuses_a_reserved_name_in_any_compatibility_form(
        open_srv, name):
    sock, status = _ws_connect(open_srv, 4620, quote(name))
    try:
        assert b"403" in status, status
    finally:
        sock.close()
    assert persistence.get_mutations(4620) == []


def test_keyless_ws_join_refuses_a_reserved_name_the_cap_leaves_spaces_after(open_srv):
    # Trim, then cap at 32: the cap can end on spaces that the old
    # ``lower()`` comparison kept, so 'Tessera' + spaces slipped through.
    padded = "Tessera" + " " * 25 + "trailing"
    sock, status = _ws_connect(open_srv, 4621, quote(padded))
    try:
        assert b"403" in status, status
    finally:
        sock.close()
    assert persistence.get_mutations(4621) == []


def test_a_keyless_body_name_in_a_compatibility_form_is_recorded_anonymously(open_srv):
    seed = 4622
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    for param in RESERVED_SPELLINGS:
        status, _ = _request(open_srv, "/puzzle/attempt", key="", body={
            "seed": seed, "depth": 1, "node_name": node.name,
            "answer": "not it", "player_name": param.values[0]})
        assert status == 200, param.id
    attempts = [row for row in persistence.get_mutations(seed)
                if row["type"] == "PUZZLE_ATTEMPT"]
    assert len(attempts) == len(RESERVED_SPELLINGS)
    assert {row["player"] for row in attempts} == {None}


@pytest.mark.parametrize("name", RESERVED_SPELLINGS)
def test_mint_and_play_clis_refuse_a_reserved_name_in_any_compatibility_form(
        monkeypatch, name):
    with pytest.raises(SystemExit, match="reserved world name"):
        _mint_cli(name)
    assert persistence.list_invite_keys() == []
    started = []
    monkeypatch.setattr("interface.run_session", lambda **kwargs: started.append(kwargs))

    class PlayArgs:
        seed = 42
        depth = 1

    PlayArgs.name = name
    with pytest.raises(SystemExit, match="reserved world name"):
        main.cmd_play(PlayArgs())
    assert started == []


# ── ASCII is unchanged; confusables are out of scope ────────────────────────

def test_an_ascii_name_keys_exactly_as_lower_of_strip():
    samples = [string.printable, "Ada", "  ADA  ", "aDa", "\tBea\n", "Cartographer-9",
               "x" * 40, "The Locksmith", "o'Brien", "A  B"]
    samples += [c for c in string.printable]
    for text in samples:
        assert persistence.name_key(text) == text.strip().lower(), repr(text)


def test_confusable_scripts_are_not_folded():
    # Stated limit, not an endorsement: NFKC keeps Cyrillic 'А' (U+0410)
    # apart from Latin 'A', and a zero-width space survives the trim.
    assert persistence.name_key("\u0410da") != persistence.name_key("Ada")
    assert persistence.name_key("Ada\u200b") != persistence.name_key("Ada")


def test_the_key_is_never_truncated():
    # The 32-character cap is the displayed name's; NFKC can expand past it.
    name = "\ufdfa"  # one character, eighteen after NFKC
    assert len(persistence.name_key(name)) == 18


# ── Concurrent claims ───────────────────────────────────────────────────────

def _interleave(monkeypatch):
    """Hold claim A just before its INSERT until claim B has started.

    B has started once it issues BEGIN IMMEDIATE (where it waits for A's
    write lock) or reaches its own INSERT (when nothing serializes the two
    claims). A SQLite trace callback runs at the start of each statement,
    before any lock is taken.
    """
    persistence.init_db()
    a_at_insert = threading.Event()
    b_started = threading.Event()
    original = persistence._connect

    def traced():
        conn = original()
        who = threading.current_thread().name

        def trace(sql):
            statement = sql.lstrip().upper()
            if who == "claim-a" and statement.startswith("INSERT INTO INVITE_KEYS"):
                a_at_insert.set()
                b_started.wait(10)
            elif who == "claim-b" and statement.startswith(
                    ("BEGIN IMMEDIATE", "INSERT INTO INVITE_KEYS")):
                b_started.set()

        conn.set_trace_callback(trace)
        return conn

    monkeypatch.setattr(persistence, "_connect", traced)
    return a_at_insert


@pytest.mark.parametrize("first, second", [
    pytest.param(ELODIE, ELODIE_LOWER, id="capital-first"),
    pytest.param(ELODIE_LOWER, ELODIE, id="lower-first"),
])
@pytest.mark.parametrize("second_path", ["mint", "redeem"])
def test_two_concurrent_claims_of_one_name_admit_exactly_one(
        monkeypatch, first, second, second_path):
    persistence.create_registration_token("nwr_race")
    a_at_insert = _interleave(monkeypatch)
    outcomes = {}

    def claim(label, call):
        try:
            call()
            outcomes[label] = "registered"
        except persistence.NameUnavailable:
            outcomes[label] = "refused"
        except Exception as exc:  # noqa: BLE001 — reported by the assertion
            outcomes[label] = repr(exc)

    a = threading.Thread(name="claim-a", target=claim, args=(
        "a", lambda: persistence.mint_invite_key(KEY_A, first)))
    if second_path == "mint":
        def second_claim():
            persistence.mint_invite_key(KEY_B, second)
    else:
        def second_claim():
            persistence.redeem_registration_token("nwr_race", KEY_B, second)
    b = threading.Thread(name="claim-b", target=claim, args=("b", second_claim))
    a.start()
    assert a_at_insert.wait(10), "claim A never reached its INSERT"
    b.start()
    a.join(15)
    b.join(15)
    assert outcomes == {"a": "registered", "b": "refused"}
    assert _stored_names() == [first]
    # A refused redemption leaves its token for another try.
    assert persistence.lookup_registration_token("nwr_race") is not None


# ── A database that already holds two names with one key ────────────────────

def test_a_seeded_legacy_duplicate_crashes_nothing(open_srv, capsys):
    """Written before this check, the ASCII index let both rows in. Both
    keep working under their own spelling; no new twin can join them."""
    persistence.mint_invite_key(KEY_A, ELODIE)
    with sqlite3.connect(persistence._DB_PATH) as conn:
        conn.execute("INSERT INTO invite_keys (key, name) VALUES (?, ?)",
                     (persistence._credential_digest(KEY_B), ELODIE_LOWER))
        conn.execute("INSERT INTO invite_keys (key, name) VALUES (?, ?)",
                     (persistence._credential_digest(KEY_C), ELODIE_NFD))
    before = _stored_names()
    assert before == sorted([ELODIE, ELODIE_LOWER, ELODIE_NFD])

    with pytest.raises(SystemExit, match="already registered"):
        _mint_cli("ÉLODIE")
    persistence.create_registration_token("nwr_one")
    status, data = _register(open_srv, "nwr_one", ELODIE)
    assert status == 409, data
    # Each credential still authenticates as its own exact spelling.
    for key, name in ((KEY_A, ELODIE), (KEY_B, ELODIE_LOWER), (KEY_C, ELODIE_NFD)):
        assert guard.registered_name(key) == name
        status, data = _request(open_srv, "/me", key=key)
        assert status == 200 and data["participant"]["name"] == name, data
    assert len({participants.identify(k)["id"] for k in (KEY_A, KEY_B, KEY_C)}) == 3
    assert _stored_names() == before


# ── Review follow-up ────────────────────────────────────────────────────────

def _d146(text):
    """Unicode's compatibility caseless match key (D146), as a reference.

    NFKD(toCasefold(NFKD(toCasefold(NFD(X))))), trimmed like the names.
    """
    folded = unicodedata.normalize("NFD", text.strip()).casefold()
    folded = unicodedata.normalize("NFKD", folded).casefold()
    return unicodedata.normalize("NFKD", folded).strip()


def test_case_variants_with_a_mark_after_a_ypogegrammeni_are_one_name(capsys):
    # NFKC first composed 'ά' + U+0345 into U+1FB4 past the U+0313, and
    # folding U+1FB4 put the U+0313 on the new iota; 'Ά' has no composite.
    capital, small = "Ά̓ͅ", "ᾴ̓"
    assert _d146(capital) == _d146(small)
    assert persistence.name_key(capital) == persistence.name_key(small)
    _mint_cli("Th" + capital + "o")
    with pytest.raises(SystemExit, match="already registered"):
        _mint_cli("th" + small + "o")
    assert _stored_names() == ["Th" + capital + "o"]


@pytest.mark.parametrize("wrap", [
    pytest.param(lambda c: "a" + c + "b", id="between-letters"),
    pytest.param(lambda c: c + "̓ͅ", id="before-ypogegrammeni-psili"),
    pytest.param(lambda c: c, id="alone"),
])
def test_the_key_partitions_names_as_unicode_compatibility_caseless_match(wrap):
    """Keys are equal exactly when D146 keys are, over the Latin, Greek,
    letterlike, enclosed, ligature and fullwidth blocks. (A run over every
    code point is recorded in the CHANGELOG, not repeated here.)"""
    blocks = [range(0x20, 0x250), range(0x370, 0x400), range(0x1E00, 0x2000),
              range(0x2100, 0x2190), range(0x2460, 0x2500), range(0xFB00, 0xFB07),
              range(0xFF01, 0xFF5F)]
    by_key, by_ref = {}, {}
    for block in blocks:
        for cp in block:
            text = wrap(chr(cp))
            key, ref = persistence.name_key(text), _d146(text)
            assert by_key.setdefault(key, ref) == ref, hex(cp)
            assert by_ref.setdefault(ref, key) == key, hex(cp)


def test_two_concurrent_redemptions_of_one_token_mint_exactly_one_key(monkeypatch):
    # Redemption is BEGIN IMMEDIATE from its token read, so the second
    # claim reads the token as spent. Without that, both reads passed and
    # the token's UPDATE did not look again: one link, two keys.
    persistence.create_registration_token("nwr_once")
    a_at_insert = _interleave(monkeypatch)
    outcomes = {}

    def claim(label, key, name):
        try:
            persistence.redeem_registration_token("nwr_once", key, name)
            outcomes[label] = "registered"
        except persistence.TokenInvalid:
            outcomes[label] = "invalid"
        except Exception as exc:  # noqa: BLE001 — reported by the assertion
            outcomes[label] = repr(exc)

    a = threading.Thread(name="claim-a", target=claim, args=("a", KEY_A, "Ada"))
    b = threading.Thread(name="claim-b", target=claim, args=("b", KEY_B, "Bea"))
    a.start()
    assert a_at_insert.wait(10), "claim A never reached its INSERT"
    b.start()
    a.join(15)
    b.join(15)
    assert outcomes == {"a": "registered", "b": "invalid"}
    assert _stored_names() == ["Ada"]
    tokens = persistence.list_registration_tokens(include_spent=True)
    assert [t["redeemed_name"] for t in tokens] == ["Ada"]


@pytest.mark.parametrize("name", ["\ud800", "Ada\udfff", " \udc80Bea "])
def test_register_refuses_a_name_with_no_utf8_form_as_a_client_error(open_srv, name):
    # An escaped lone surrogate in the JSON body has no UTF-8 form; storing
    # it raised UnicodeEncodeError, a 500 for the client's own mistake.
    persistence.create_registration_token("nwr_live")
    status, data = _register(open_srv, "nwr_live", name)
    assert (status, data) == (400, {"error": "a name must be plain text"})
    assert persistence.lookup_registration_token("nwr_live") is not None
    assert persistence.list_invite_keys(include_revoked=True) == []


def test_register_refuses_an_invite_with_no_utf8_form_as_an_unknown_one(open_srv):
    persistence.create_registration_token("nwr_live")
    status, data = _register(open_srv, "nwr_l\udfffive", "Ada")
    assert (status, data) == (403, {"error": "this invite is not valid"})
    assert persistence.lookup_registration_token("nwr_live") is not None
    assert persistence.list_invite_keys(include_revoked=True) == []


def test_a_keyless_body_name_with_no_utf8_form_is_recorded_anonymously(open_srv):
    seed = 4623
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    for name in ("\ud800", "Ada\udfff"):
        status, _ = _request(open_srv, "/puzzle/attempt", key="", body={
            "seed": seed, "depth": 1, "node_name": node.name,
            "answer": "not it", "player_name": name})
        assert status == 200, ascii(name)
    attempts = [row for row in persistence.get_mutations(seed)
                if row["type"] == "PUZZLE_ATTEMPT"]
    assert [row["player"] for row in attempts] == [None, None]


def test_keyless_ws_join_trims_again_after_the_cap(open_srv):
    # Trim, cap, trim again, as the body-name path does: a cap that ends on
    # spaces leaves none in the name the room and the chronicle show.
    seed = 4624
    sock, status = _ws_connect(open_srv, seed, quote("Ada" + " " * 29 + "trailing"))
    try:
        assert b"101" in status, status
        deadline = time.monotonic() + 10
        joins = []
        while not joins and time.monotonic() < deadline:
            joins = [row for row in persistence.get_mutations(seed)
                     if row["type"] == "PLAYER_JOIN"]
            time.sleep(0.05)
    finally:
        sock.close()
    assert [row["player"] for row in joins] == ["Ada"]
