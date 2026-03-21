#!/usr/bin/env python3
"""
LAMBS Stub Updater — hält MEMORY.md mit CURRENT/stack.md synchron.

Zweck:
  MEMORY.md ist der System-Prompt-Stub den nanobot bei jedem Request injiziert.
  Er enthält einen AUTO-GENERATED BLOCK mit den aktuellen Kernfakten aus
  CURRENT/stack.md. Dieser Block wird nie manuell gepflegt — stub_update.py
  regeneriert ihn nach jedem memory_write_current.py Aufruf automatisch.

Warum automatisch statt manuell:
  Ohne automatischen Sync divergiert der Stub still von CURRENT/stack.md.
  Der Agent würde dann veraltete Kernfakten aus dem Stub verwenden.

Sicherheits-Invariante:
  MEMORY.md darf niemals 50 Zeilen überschreiten (assert). Bei Verletzung
  wird ein AssertionError geworfen und der Write abgebrochen.
"""
from pathlib import Path
import re

WORKSPACE = Path.home() / ".nanobot/workspace"
REPO      = WORKSPACE / "memory_repo"

# Canonical location for the injected MEMORY.md stub.
# Jakob decision (21. März 2026): root stub path is deprecated/removed.
STUB = WORKSPACE / "memory" / "MEMORY.md"

STACK   = REPO / "CURRENT/stack.md"
MAX_LINES = 50

def run():
    """
    Liest CURRENT/stack.md und ersetzt den AUTO-GENERATED BLOCK in MEMORY.md.

    Ablauf:
        1. stack.md lesen, max. 15 Key-Value-Zeilen extrahieren
        2. Neuen Block-Text aufbauen mit Instruktionen + Kernfakten
        3. Regex-Replace im MEMORY.md (zwischen den Kommentar-Markern)
        4. Längen-Assert: MEMORY.md darf 50 Zeilen nicht überschreiten
        5. Datei schreiben

    Raises:
        AssertionError: wenn MEMORY.md nach dem Update > MAX_LINES Zeilen hätte.
    """
    if not STACK.exists():
        print("[stub_update] CURRENT/stack.md nicht gefunden")
        return

    # Extrahiere Key-Value Zeilen aus stack.md
    kv_lines = []
    for line in STACK.read_text().splitlines():
        line = line.strip()
        if line.startswith("- ") and ":" in line:
            kv_lines.append(line)
        if len(kv_lines) >= 15:
            break

    new_block = "\n".join([
        "<!-- AUTO-GENERATED BLOCK: stub_update.py — nicht manuell editieren -->",
        "Kanonisches Memory: ~/.nanobot/workspace/memory_repo/",
        "",
        "Für Fakten/Entscheidungen/Runbooks:",
        '  exec python3 ~/.nanobot/scripts/memory_search.py "<query>" --top 8',
        "",
        "Für heutige Events:",
        '  grep -i "<query>" ~/.nanobot/workspace/memory/HISTORY.md | tail -20',
        "",
        "## Aktuelle Kernfakten (auto-generiert aus CURRENT/stack.md)",
        *kv_lines,
        "<!-- END AUTO-GENERATED BLOCK -->",
    ])

    if not STUB.exists():
        print("[stub_update] MEMORY.md nicht gefunden — wird neu angelegt")
        STUB.parent.mkdir(parents=True, exist_ok=True)
        STUB.write_text(
            "# Agent Memory\n"
            "<!-- AUTO-GENERATED BLOCK: stub_update.py — nicht manuell editieren -->\n"
            "<!-- END AUTO-GENERATED BLOCK -->\n"
        )

    stub_text = STUB.read_text()

    updated = re.sub(
        r"<!-- AUTO-GENERATED BLOCK.*?<!-- END AUTO-GENERATED BLOCK -->",
        new_block,
        stub_text,
        flags=re.DOTALL
    )

    lines = updated.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError(
            f"MEMORY.md hätte {len(lines)} Zeilen — Maximum ist {MAX_LINES}! Write abgebrochen."
        )

    STUB.parent.mkdir(parents=True, exist_ok=True)
    STUB.write_text(updated)

    print(f"[stub_update] MEMORY.md aktualisiert ({len(lines)} Zeilen) → {STUB}")

if __name__ == "__main__":
    run()
