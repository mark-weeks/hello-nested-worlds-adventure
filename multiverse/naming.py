"""Names, addresses and identity keys (ADR-041).

A node's *name* is a label: its three curated words. Its *address* is its
path from the root, which `world_nodes.path` stores dot-joined ("1.2.1");
the digits form is the same path with no separator ("121"). Its *key* is the
string every identity-keyed derivation hashes or seeds from:

    f"{name}-{digits}"

That is byte for byte the name a generator-version-2 world stored, so no
random input moved when names lost their suffix. A world born under version 2
or earlier already stores that string as its name, so its key is the stored
name alone (`key_for`).

This module imports nothing from the store, persistence or the generator, so
every layer can use it. Nodes carry `address` (digits form) and `key`; both
are set by the generator and by the store. A hand-built node has neither and
keys on its name, as it always did.
"""
from __future__ import annotations

# The last generator version whose stored names end in their own path digits.
LEGACY_NAME_VERSION = 2


def digits_of(path) -> str:
    """The digits form of an address: (1, 2, 1) or "1.2.1" -> "121".

    Unambiguous because every path component is a single digit (breadth is
    capped at 9, `generator.MAX_GENERATOR_BREADTH`).
    """
    if isinstance(path, str):
        return path.replace(".", "")
    return "".join(str(i) for i in path)


def dotted_of(address) -> str:
    """The stored form of an address: "121" or (1, 2, 1) -> "1.2.1"."""
    if isinstance(address, str):
        return ".".join(address.replace(".", ""))
    return ".".join(str(i) for i in address)


def key_for(name: str, digits: str, generator_version: int) -> str:
    """The identity key of a stored node (ADR-041 D4)."""
    if generator_version <= LEGACY_NAME_VERSION:
        return name  # the stored name already ends in its digits
    return f"{name}-{digits}"


def legacy_address(name: str) -> str | None:
    """The path digits a version-2 name ends in ("Hidden Thorn
    Quark-11431112111" -> "11431112111"), or None. Only for names from a
    world born under generator version 2 or earlier, and for hand-built
    nodes; a position is otherwise read from the node, never from a name."""
    base, separator, suffix = (name or "").rpartition("-")
    if separator and base and suffix.isdigit():
        return suffix
    return None


def node_key(node) -> str:
    """What identity-keyed hashes and seeds take for this node."""
    return getattr(node, "key", None) or node.name


def node_address(node) -> str | None:
    """The node's address in digits form, or None when it has none.

    A node the generator or the store built carries it. A hand-built node
    falls back to the digits a version-2 style name ends in.
    """
    return getattr(node, "address", None) or legacy_address(node.name)


def node_path(node) -> str | None:
    """The node's address in the stored, dot-joined form."""
    address = node_address(node)
    return dotted_of(address) if address else None


def name_carries_address(node) -> bool:
    """True when the name itself ends in path digits: a node of a world born
    under generator version 2 or earlier, or a hand-built node named that
    way. Such a place keeps the wording that refers to those digits."""
    return legacy_address(node.name) is not None
