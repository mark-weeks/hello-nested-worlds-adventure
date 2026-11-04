"""A player name is one name under trim, NFKC and case folding (ADR-004 §7).

Uniqueness and the reserved names used to compare Python's ``str.lower()``
(or SQLite's ASCII-only ``lower(trim(name))`` index), so 'Élodie' and
'élodie', or a composed and a decomposed 'Élodie' that look identical, could
both be registered, and a fullwidth 'Ｓｃｏｕｔ' passed the reserved-name
check. Every path now compares ``persistence.name_key``. These tests drive
the real mint CLI, ``POST /register``, the keyless WebSocket join, the
body-name path and the store, and read what was stored.

The key also drops Unicode's default-ignorable code points (a zero-width
space, a soft hyphen, a variation selector), as NFKC_Casefold does, and
``/register`` and ``invite mint`` refuse a name holding one, a control
character, or nothing visible (decided under the owner's delegation,
2026-11-04; ADR-004 §7).

Out of scope, by statement: NFKC does not fold confusable letters from
other scripts (Cyrillic 'а' for Latin 'a').
"""
from __future__ import annotations

import functools
import json
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
    # apart from Latin 'A'.
    assert persistence.name_key("\u0410da") != persistence.name_key("Ada")


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

    NFKD(toCasefold(NFKD(toCasefold(NFD(X))))), with the default-ignorable
    code points removed before the last NFKD, as NFKC_Casefold removes
    them, and trimmed like the names. The removed set is derived here by
    Unicode's own rule (`_derived_default_ignorable`), not read from
    ``persistence``.
    """
    folded = unicodedata.normalize("NFD", text.strip()).casefold()
    folded = unicodedata.normalize("NFKD", folded).casefold()
    ignorable = _derived_default_ignorable()
    folded = "".join(c for c in folded if ord(c) not in ignorable)
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
    """Keys are equal exactly when D146 keys (default-ignorables removed)
    are, over the Latin, Greek, letterlike, enclosed, ligature, fullwidth
    and general-punctuation blocks and the default-ignorables. (A run over
    every code point is recorded in the CHANGELOG, not repeated here.)"""
    blocks = [range(0x20, 0x250), range(0x370, 0x400), range(0x1E00, 0x2000),
              range(0x2100, 0x2190), range(0x2460, 0x2500), range(0xFB00, 0xFB07),
              range(0xFF01, 0xFF5F),
              # Spaces, zero-width and bidirectional controls, variation
              # selectors and other default-ignorables, removed by the key.
              range(0x2000, 0x2070), range(0xFE00, 0xFE10),
              [0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x180E, 0x3164, 0xFEFF,
               0xFFA0, 0x1D173, 0xE0001, 0xE0100]]
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


# ── Review follow-up: revoked names, the body-name re-trim, operator argv ────

def test_a_revoked_name_stays_taken_in_any_spelling(open_srv, capsys):
    # The scan compares every registered name, revoked ones included: a
    # revoked player's name is not free for someone else to take.
    _mint_cli(ELODIE)
    (row,) = persistence.list_invite_keys(include_revoked=True)
    assert persistence.revoke_invite_key(row["key"][:16])  # digest prefix
    with pytest.raises(SystemExit, match="already registered"):
        _mint_cli(ELODIE_LOWER)
    persistence.create_registration_token("nwr_one")
    status, data = _register(open_srv, "nwr_one", ELODIE_NFD)
    assert status == 409, data
    assert persistence.lookup_registration_token("nwr_one") is not None
    assert _stored_names() == [ELODIE]


def test_a_keyless_body_name_is_trimmed_again_after_the_cap(open_srv):
    # Trim, cap at 32, trim again: a cap that ends on spaces leaves none in
    # the name the chronicle records.
    seed = 4625
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    status, _ = _request(open_srv, "/puzzle/attempt", key="", body={
        "seed": seed, "depth": 1, "node_name": node.name,
        "answer": "not it", "player_name": "Ada" + " " * 29 + "trailing"})
    assert status == 200
    attempts = [row for row in persistence.get_mutations(seed)
                if row["type"] == "PUZZLE_ATTEMPT"]
    assert [row["player"] for row in attempts] == ["Ada"]


# A byte that is not UTF-8 on the command line reaches Python as a lone
# surrogate (surrogateescape): `--name $'\xff'` is "\udcff".
ARGV_NOT_UTF8 = "\udcff"


def test_the_mint_cli_refuses_a_name_with_no_utf8_form_cleanly(capsys):
    with pytest.raises(SystemExit, match="must be plain text"):
        _mint_cli(ARGV_NOT_UTF8 + "Ada")
    assert persistence.list_invite_keys(include_revoked=True) == []


def test_the_play_cli_refuses_a_name_with_no_utf8_form_before_a_session(monkeypatch):
    started = []
    monkeypatch.setattr("interface.run_session", lambda **kwargs: started.append(kwargs))

    class PlayArgs:
        seed = 42
        depth = 1
        name = "Ada" + ARGV_NOT_UTF8

    with pytest.raises(SystemExit, match="must be plain text"):
        main.cmd_play(PlayArgs())
    assert started == []


@pytest.mark.parametrize("action", ["suspend", "ban"])
def test_the_sanction_cli_refuses_a_target_with_no_utf8_form_cleanly(action, capsys):
    _mint_cli("Ada")

    class SanctionArgs:
        sanction_action = action
        player = "Ada" + ARGV_NOT_UTF8
        reason = "spam"
        hours = 24
        days = None

    with pytest.raises(SystemExit) as exc:
        main.cmd_sanction(SanctionArgs())
    assert str(exc.value) == "A player name must be plain text."


# ── Owner decisions (delegated, 2026-11-04) ─────────────────────────────────
#
# Default-ignorable code points leave the key and are refused on the claiming
# paths; the mint CLI caps a name at 32 characters; play --name refuses a
# registered name on the shared world; `invite duplicates` lists names that
# share a key.

# Unicode's derivation of Default_Ignorable_Code_Point (the header of
# DerivedCoreProperties.txt): Other_Default_Ignorable_Code_Point + Cf +
# Variation_Selector - White_Space - FFF9..FFFB - 13430..13438 -
# Prepended_Concatenation_Mark. Categories, names and whitespace come from
# the pinned interpreter's UCD (14.0.0); the two PropList sets it has no
# accessor for are listed from PropList-14.0.0.txt.
_OTHER_DEFAULT_IGNORABLE = frozenset([
    0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x2065, 0x3164, 0xFFA0,
    *range(0xFFF0, 0xFFF9), 0xE0000, *range(0xE0002, 0xE0020),
    *range(0xE0080, 0xE0100), *range(0xE01F0, 0xE1000)])
_PREPENDED_CONCATENATION_MARK = frozenset([
    *range(0x0600, 0x0606), 0x06DD, 0x070F, 0x0890, 0x0891, 0x08E2,
    0x110BD, 0x110CD])


@functools.lru_cache(maxsize=1)
def _derived_default_ignorable() -> frozenset[int]:
    derived = set(_OTHER_DEFAULT_IGNORABLE)
    for cp in range(0x110000):
        char = chr(cp)
        category = unicodedata.category(char)
        if category not in ("Cf", "Mn") or char.isspace():
            continue
        if (0xFFF9 <= cp <= 0xFFFB or 0x13430 <= cp <= 0x13438
                or cp in _PREPENDED_CONCATENATION_MARK):
            continue
        if category == "Cf" or "VARIATION SELECTOR" in unicodedata.name(char, ""):
            derived.add(cp)
    return frozenset(derived)


# The members the decision names, each checked on its own below.
KNOWN_INVISIBLES = [
    0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, *range(0x180B, 0x1810),
    *range(0x200B, 0x2010), *range(0x202A, 0x202F), *range(0x2060, 0x2070),
    0x3164, *range(0xFE00, 0xFE10), 0xFEFF, 0xFFA0, 0x1D173, 0xE0001, 0xE0100,
]


def test_the_default_ignorable_table_is_unicode_14s():
    # The hardcoded ranges agree with Unicode's own derivation over the
    # pinned interpreter's character data: 4,174 code points.
    assert unicodedata.unidata_version == "14.0.0"
    assert persistence.DEFAULT_IGNORABLE == _derived_default_ignorable()
    assert len(persistence.DEFAULT_IGNORABLE) == 4174
    assert set(KNOWN_INVISIBLES) <= persistence.DEFAULT_IGNORABLE


def test_an_invisible_character_leaves_the_key_wherever_it_stands():
    from agents import identities
    for cp in KNOWN_INVISIBLES:
        char = chr(cp)
        for name in ("Sc" + char + "out", "Scout" + char, char + "Scout",
                     " " + char + " Scout"):
            assert persistence.name_key(name) == "scout", (hex(cp), ascii(name))
            assert identities.canonical(name) == "Scout", (hex(cp), ascii(name))


def test_the_key_stays_idempotent_when_an_invisible_character_parted_marks():
    # A combining grapheme joiner kept 'e' and U+0301 apart; once it is
    # removed they compose, so removal has to come before recomposition.
    assert persistence.name_key("e\u034f\u0301") == "\u00e9"
    samples = ["e\u034f\u0301", "a\u0301\u034f\u0316", "Ada\u200b ", "\u3164 Bea"]
    samples += [template.format(chr(cp)) for cp in KNOWN_INVISIBLES
                for template in ("e{}\u0301", "{}\u0301a", "A{}\u0345\u0313")]
    for text in samples:
        key = persistence.name_key(text)
        assert persistence.name_key(key) == key, ascii(text)
        assert not set(map(ord, key)) & persistence.DEFAULT_IGNORABLE, ascii(text)


def _seed_rows(*rows):
    """Insert invite rows as a database written before these checks holds them."""
    persistence.init_db()
    with sqlite3.connect(persistence._DB_PATH) as conn:
        for key, name, revoked in rows:
            conn.execute(
                "INSERT INTO invite_keys (key, name, revoked_at) VALUES (?, ?, ?)",
                (persistence._credential_digest(key), name,
                 "2026-11-01 00:00:00" if revoked else None))


def test_a_stored_name_with_an_invisible_character_is_its_visible_form(open_srv, capsys):
    # Written before the refusal (or restored from such a backup): the key
    # drops the invisible character, so its visible spelling is taken, and
    # the sanction lookup finds the stored row by that spelling.
    from persistence import sanctions
    _seed_rows((KEY_A, "Ada\u200b", False), (KEY_B, "Sc\u00adout Bea", False))
    with pytest.raises(SystemExit, match="already registered"):
        _mint_cli("Ada")
    persistence.create_registration_token("nwr_one")
    status, data = _register(open_srv, "nwr_one", "ADA")
    assert status == 409, data
    status, data = _register(open_srv, "nwr_one", "scout bea")
    assert status == 409, data
    assert persistence.lookup_registration_token("nwr_one") is not None
    assert sanctions.resolve("ada")["name"] == "Ada\u200b"
    assert _stored_names() == sorted(["Ada\u200b", "Sc\u00adout Bea"])


@pytest.mark.parametrize("name", ["Scout\u200b", "Sc\u00adout", "\u3164Tessera",
                                  "Observer\ufe0f"])
def test_play_refuses_a_reserved_name_with_an_invisible_character(monkeypatch, name):
    started = []
    monkeypatch.setattr("interface.run_session", lambda **kwargs: started.append(kwargs))
    with pytest.raises(SystemExit, match="reserved world name"):
        main.cmd_play(_PlayArgs(name, 42))
    assert started == []


INVISIBLE_NAMES = [
    pytest.param("Ada\u200b", id="zero-width-space"),
    pytest.param("Sc\u00adout", id="soft-hyphen"),
    pytest.param("Bea\ufe0f", id="variation-selector"),
    pytest.param("Ada\u202eaeB", id="right-to-left-override"),
    pytest.param("\u3164", id="hangul-filler-only"),
    pytest.param("\u2800", id="braille-blank-only"),
    pytest.param("\u2800 \u2800", id="braille-blanks-and-a-space"),
    pytest.param("Ada\tBea", id="inner-tab"),
    pytest.param("Ada\x1b[31m", id="escape-sequence"),
    pytest.param("Ada\x00", id="nul"),
    pytest.param("Ada\u0085Bea", id="next-line"),
]


@pytest.mark.parametrize("name", INVISIBLE_NAMES)
def test_register_refuses_a_name_with_hidden_or_no_visible_text(open_srv, name):
    persistence.create_registration_token("nwr_live")
    status, data = _register(open_srv, "nwr_live", name)
    assert (status, data) == (400, {"error": persistence.INVISIBLE_NAME_ERROR})
    assert persistence.lookup_registration_token("nwr_live") is not None
    assert persistence.list_invite_keys(include_revoked=True) == []


@pytest.mark.parametrize("name", INVISIBLE_NAMES)
def test_the_mint_cli_refuses_a_name_with_hidden_or_no_visible_text(name, capsys):
    with pytest.raises(SystemExit) as exc:
        _mint_cli(name)
    assert str(exc.value) == ("A registered name must be visible text, with no "
                              "control or invisible characters.")
    assert persistence.list_invite_keys(include_revoked=True) == []


def test_a_keyless_body_name_with_hidden_or_no_visible_text_is_recorded_anonymously(
        open_srv):
    seed = 4626
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    for name in [param.values[0] for param in INVISIBLE_NAMES] + ["Ada Lovelace"]:
        status, _ = _request(open_srv, "/puzzle/attempt", key="", body={
            "seed": seed, "depth": 1, "node_name": node.name,
            "answer": "not it", "player_name": name})
        assert status == 200, ascii(name)
    attempts = [row for row in persistence.get_mutations(seed)
                if row["type"] == "PUZZLE_ATTEMPT"]
    players = [row["player"] for row in attempts]
    assert len(players) == len(INVISIBLE_NAMES) + 1
    assert [player for player in players if player is not None] == ["Ada Lovelace"]


@pytest.mark.parametrize("name", INVISIBLE_NAMES)
def test_keyless_ws_join_refuses_a_name_with_hidden_or_no_visible_text(open_srv, name):
    sock, status = _ws_connect(open_srv, 4627, quote(name))
    try:
        assert b"403" in status, status
        # The refusal's own body, read to its end: a soft-hyphenated 'Scout'
        # is also the reserved name, so the status alone cannot tell which
        # check refused it.
        sock.settimeout(5)
        body = b""
        while not body.rstrip().endswith(b"}"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            body += chunk
    finally:
        sock.close()
    assert json.loads(body) == {"error": persistence.INVISIBLE_NAME_ERROR}
    assert persistence.get_mutations(4627) == []


def test_the_mint_cli_caps_a_name_at_32_characters(capsys):
    with pytest.raises(SystemExit) as exc:
        _mint_cli("x" * 33)
    assert str(exc.value) == "A registered name must be 32 characters or fewer."
    assert persistence.list_invite_keys(include_revoked=True) == []
    _mint_cli("  " + "y" * 32 + "  ")        # the cap counts the trimmed name
    assert _stored_names() == ["y" * 32]


class _PlayArgs:
    depth = 1

    def __init__(self, name, seed):
        self.name = name
        self.seed = seed


def test_play_refuses_a_registered_name_in_any_spelling_on_the_shared_world(
        monkeypatch, capsys):
    started = []
    monkeypatch.setattr("interface.run_session", lambda **kwargs: started.append(kwargs))
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "382")
    _mint_cli(ELODIE)
    _mint_cli("Zo\u00eb")
    (zoe,) = [r for r in persistence.list_invite_keys() if r["name"] == "Zo\u00eb"]
    assert persistence.revoke_invite_key(zoe["key"][:16])
    for spelling in (ELODIE, ELODIE_LOWER, ELODIE_NFD, ELODIE_LOWER.upper(),
                     "Ｅ\u0301ｌｏｄｉｅ", "\u00e9lodie\u200b",
                     "ZOE\u0308"):                     # 'ZO\u00cb', revoked: still taken
        with pytest.raises(SystemExit) as exc:
            main.cmd_play(_PlayArgs(spelling, 382))
        assert str(exc.value) == (f"'{spelling}' is a registered player's name — "
                                  "choose another with --name."), ascii(spelling)
    assert started == []
    main.cmd_play(_PlayArgs("Bea", 382))
    assert started == [{"seed": 382, "depth": 1, "player_name": "Bea"}]


def test_play_under_a_registered_name_off_the_shared_world_is_unaffected(
        monkeypatch, capsys):
    started = []
    monkeypatch.setattr("interface.run_session", lambda **kwargs: started.append(kwargs))
    _mint_cli(ELODIE)
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "382")
    main.cmd_play(_PlayArgs(ELODIE_LOWER, 7))     # not the hosted seed
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "")
    main.cmd_play(_PlayArgs(ELODIE_LOWER, 42))    # local multi-world mode
    assert [kwargs["seed"] for kwargs in started] == [7, 42]


def test_invite_duplicates_lists_each_group_and_exits_1(capsys):
    _seed_rows((KEY_A, ELODIE, False), (KEY_B, ELODIE_LOWER, False),
               (KEY_C, ELODIE_NFD, True),
               ("nw_" + "d" * 32, "Ada", False), ("nw_" + "e" * 32, "Ada\u200b", False),
               ("nw_" + "f" * 32, "B\u00e9a\x1b[2J", False),
               ("nw_" + "0" * 32, "B\u00c9A\x1b[2j", False),
               ("nw_" + "1" * 32, "Zo\u00eb", False))
    before = persistence.list_invite_keys(include_revoked=True)
    with pytest.raises(SystemExit) as exc:
        main.main(["invite", "duplicates"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert out.startswith("3 group(s) of registered names share a name key")
    assert "\x1b" not in out and "\u200b" not in out
    lines = out.splitlines()
    # Each row shows the name through `_shown` (an escape sequence or an
    # invisible character written as its escape), then exactly as ascii().
    shown = {ELODIE: ELODIE, ELODIE_LOWER: ELODIE_LOWER, ELODIE_NFD: ELODIE_NFD,
             "Ada": "Ada", "Ada\u200b": "Ada\\u200b",
             "B\u00e9a\x1b[2J": "B\u00e9a\\x1b[2J", "B\u00c9A\x1b[2j": "B\u00c9A\\x1b[2j"}
    for name, display in shown.items():
        (row,) = [line for line in lines if ascii(name) in line]
        assert row.startswith(f"  {display} "), (ascii(name), row)
    assert "Zo" not in out
    (decomposed,) = [line for line in lines if ascii(ELODIE_NFD) in line]
    assert decomposed.rstrip().endswith("revoked")
    # Each group's lines sit together, one blank line between groups.
    groups = [block.splitlines() for block in out.split("\n\n")[1:]]
    assert sorted(len(group) for group in groups) == [2, 2, 3]
    assert persistence.list_invite_keys(include_revoked=True) == before


def test_invite_duplicates_exits_0_when_every_name_is_its_own(capsys):
    main.main(["invite", "duplicates"])                     # no rows at all
    _mint_cli(ELODIE)
    _mint_cli("Zo\u00eb")
    _mint_cli("Ada")
    capsys.readouterr()
    main.main(["invite", "duplicates"])
    assert capsys.readouterr().out == "No two registered names share a name key.\n"

