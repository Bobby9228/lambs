"""LAMBS feature flags loader.

Reads ~/.nanobot/workspace/.lambs_flags (KEY=VALUE lines) and validates boolean flags.

- Accept only 0/1 for boolean flags.
- On invalid values: warn to stderr and apply defaults.

This module is dependency-free and safe to import from cron scripts.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_FLAGS = {
    "LAMBS_SEARCH_ENABLED": "1",
    "LAMBS_WRITE_ENABLED": "1",
    "LAMBS_CONSOLIDATE_ENABLED": "1",
    "LAMBS_PATTERN_ENABLED": "1",
    "LAMBS_SEMANTIC_ENABLED": "0",
}


@dataclass(frozen=True)
class Flags:
    search: bool
    write: bool
    consolidate: bool
    pattern: bool
    semantic: bool


def _warn(msg: str) -> None:
    print(f"[lambs_flags] WARN: {msg}", file=sys.stderr)


def _parse_flags_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _bool01(name: str, value: str) -> bool:
    if value not in ("0", "1"):
        _warn(f"{name} has invalid value {value!r} (expected '0' or '1'); using default {DEFAULT_FLAGS[name]!r}.")
        value = DEFAULT_FLAGS[name]
    return value == "1"


def load_flags() -> Flags:
    flags_file = Path(os.environ.get("LAMBS_FLAGS_FILE", str(Path.home() / ".nanobot/workspace/.lambs_flags")))
    raw = {**DEFAULT_FLAGS, **_parse_flags_file(flags_file)}

    return Flags(
        search=_bool01("LAMBS_SEARCH_ENABLED", raw["LAMBS_SEARCH_ENABLED"]),
        write=_bool01("LAMBS_WRITE_ENABLED", raw["LAMBS_WRITE_ENABLED"]),
        consolidate=_bool01("LAMBS_CONSOLIDATE_ENABLED", raw["LAMBS_CONSOLIDATE_ENABLED"]),
        pattern=_bool01("LAMBS_PATTERN_ENABLED", raw["LAMBS_PATTERN_ENABLED"]),
        semantic=_bool01("LAMBS_SEMANTIC_ENABLED", raw["LAMBS_SEMANTIC_ENABLED"]),
    )
