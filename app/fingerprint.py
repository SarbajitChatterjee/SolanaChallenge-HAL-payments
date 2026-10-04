"""Purchase fingerprint: the same item with the same params gives the same value,
whatever the key order, spacing (also inside a string) or upper/lower case of the strings."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split()).lower()   # "Duping  Bahn " -> "duping bahn"
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def canonical_json(params: Any) -> str:
    return json.dumps(_canonical(params or {}),
                      sort_keys=True,
                      separators=(",", ":"),
                      ensure_ascii=False,
                      default=str)


def fingerprint(tool: str, params: Any) -> str:
    """SHA-256 of the tool (or raw URL) and the canonical params."""
    return hashlib.sha256(f"{tool.strip().lower()}\n{canonical_json(params)}".encode()).hexdigest()