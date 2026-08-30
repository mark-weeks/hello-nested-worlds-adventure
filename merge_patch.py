"""Shared RFC 7396 JSON Merge Patch semantics."""
from __future__ import annotations

from typing import Any


def json_merge_patch(target: Any, patch: Any) -> Any:
    """Apply one RFC 7396 merge patch without mutating either input."""
    if not isinstance(patch, dict):
        return patch
    out = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        elif isinstance(value, dict):
            out[key] = json_merge_patch(out.get(key), value)
        else:
            out[key] = value
    return out
