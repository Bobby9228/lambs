#!/usr/bin/env python3
"""
LAMBS Write Current — Upsert für CURRENT/stack.md.

Zweck:
  Schreibt einen Key-Value-Fakt dauerhaft in CURRENT/stack.md.
  Upsert-Semantik: existierender Key wird überschrieben, neuer Key wird
  angehängt. Immer atomar via tempfile+os.replace — kein halbfertiger
  Zustand möglich.

Sicherheits-Kette:
  1. input_sanitizer.sanitize_or_raise() — blockiert PII/Injektionen
  2. Contradiction Engine — warnt bei großem semantischen Drift
  3. fcntl.flock() — verhindert Race Condition mit Cron-Jobs
  4. os.replace() — atomischer Write, crash-sicher
  5. stub_update.py — hält MEMORY.md automatisch synchron

Nach dem Write:
  Ruft memory_search.py --reindex-file auf (Phase 6: sofortiger Index-Update).
  In Phase 1-5 gibt --reindex-file nur eine Meldung aus ohne Seiteneffekte.
"""

import sys, subprocess, os, fcntl, re
from pathlib import Path
from input_sanitizer import sanitize_or_raise, SanitizationError

REPO    = Path.home() / ".nanobot/workspace/memory_repo"
STACK   = REPO / "CURRENT/stack.md"
ALERTS  = Path.home() / ".nanobot/workspace/ALERTS.md"
LOCK    = Path.home() / ".nanobot/logs/repo.lock"
MAX_LINES = 50

def contradiction_check(key: str, old_val: str, new_val: str):
    """
    Erkennt semantisch signifikante Wertänderungen und schreibt einen Alert.

    Implementiert eine heuristische PAMU (Preference-Aware Memory Update)
    Prüfung: wenn der neue Wert keine gemeinsamen Tokens mit dem alten hat,
    ist das ein starkes Signal für einen konfigurationskritischen Drift.

    Phase 6 Upgrade: Embedding-basierter Cosine-Vergleich statt Token-Set.

    Args:
        key:     Der Key der aktualisiert wird
        old_val: Der bisherige Wert (aus stack.md gelesen)
        new_val: Der neue Wert (aus Aufruf-Argumenten)

    Seiteneffekt:
        Schreibt eine [CONTRADICTION]-Zeile in ALERTS.md wenn Drift erkannt.
        Der Write wird trotzdem ausgeführt — Alert ist nur informativ.
    """

    # Heuristik: prüft Token-Disjunktheit (kein gemeinsames Wort zwischen alt und neu).
    # Feuert bei jeder einfachen Werteänderung — dient als grober Drift-Indikator,
    # nicht als präziser numerischer Vergleich. Phase 6: Cosine-Vergleich via MiniLM.
    old_nums = set(old_val.split())
    new_nums = set(new_val.split())
    if old_nums and new_nums and old_nums.isdisjoint(new_nums):
        msg = f"[CONTRADICTION] {key}: war '{old_val}', wird '{new_val}'\n"
        ALERTS.parent.mkdir(parents=True, exist_ok=True)
        with ALERTS.open("a") as f:
            f.write(msg)
        print(f"[write_current] Drift erkannt für {key!r} — Alert geschrieben")

def main():
    """
    CLI-Entry-Point: liest Key+Value aus argv, prüft und schreibt in stack.md.

    Ablauf:
        1. sanitize_or_raise() — blockiert bei PII/Injection
        2. stack.md lesen (explizites if/exists statt ternary)
        3. Key suchen (case-insensitive): überschreiben oder anhängen
        4. Contradiction Engine: Alert bei starkem Drift
        5. Längen-Check: max. 50 Zeilen
        6. Atomischer Write: flock → tempfile → os.replace
        7. stub_update.py aufrufen → MEMORY.md synchronisieren
        8. --reindex-file aufrufen → Phase 6: sofortiger Index-Update
    """
    if len(sys.argv) < 3:
        print("Usage: memory_write_current.py <key> <value>")
        sys.exit(1)

    key, value = sys.argv[1], " ".join(sys.argv[2:])

    # Key-Format validieren: nur alphanumerisch + Unterstrich/Bindestrich, kein Leerzeichen/Doppelpunkt
    import re as _re
    if not _re.match(r'^[a-zA-Z0-9_\-]+$', key):
        print(f"[write_current] BLOCKIERT: Key {key!r} enthält ungültige Zeichen (nur a-z, 0-9, _, - erlaubt)")
        sys.exit(1)

    # Key-Format validieren: nur Buchstaben, Zahlen, Unterstriche, Bindestriche
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_\-]*$', key):
        print(f"[write_current] BLOCKIERT: Ungültiges Key-Format: {key!r} (nur a-z, 0-9, _, - erlaubt)")
        sys.exit(1)

    try:
        sanitize_or_raise(f"{key}: {value}")
    except SanitizationError as e:
        print(f"[write_current] BLOCKIERT: {e}")
        sys.exit(1)

    lines = []
    if STACK.exists():
        lines = STACK.read_text().splitlines()
    # Explizites if/else — crasht nicht beim Refactoring im Gegensatz zu ternary
    key_lower = f"- {key.lower()}:"
    found = False
    new_lines = []

    for line in lines:
        if line.lower().startswith(key_lower):
            old_val = line.split(":", 1)[1].strip() if ":" in line else ""
            contradiction_check(key, old_val, value)
            new_lines.append(f"- {key}: {value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"- {key}: {value}")

    if len(new_lines) > MAX_LINES:
        print(f"[write_current] BLOCKIERT: stack.md hätte {len(new_lines)} Zeilen (max {MAX_LINES})")
        sys.exit(1)

    # Atomischer Write via tempfile + os.replace — crash-sicher
    # flock stellt sicher dass kein Cron-Job gleichzeitig schreibt
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        tmp = STACK.parent / f".stack.tmp.{os.getpid()}"
        tmp.write_text("\n".join(new_lines) + "\n")
        os.replace(tmp, STACK)  # atomisch — kein halbfertiger Zustand möglich
    print(f"[write_current] {'Aktualisiert' if found else 'Neu'}: {key} = {value}")
    # Stub + Index aktualisieren:
    subprocess.run(["python3", str(Path.home() / ".nanobot/scripts/stub_update.py")])
    subprocess.run(["python3", str(Path.home() / ".nanobot/scripts/memory_search.py"),
                    "--reindex-file", "CURRENT/stack.md"])

if __name__ == "__main__":
    main()
