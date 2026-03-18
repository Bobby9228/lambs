#!/usr/bin/env python3
"""
LAMBS Repo Validator — Schema-Validierung vor git commits.

Zweck:
  Verhindert schleichenden Schema-Drift: ohne Validierung können Key-Synonyme
  (nanobot_port vs port_nanobot), Duplikate und fehlendes Frontmatter
  über Zeit akkumulieren und das Retrieval verschlechtern.

Integration:
  Wird in memory_commit_push.sh vor "git add -A" aufgerufen.
  Exit 1 bricht den Commit ab — der Repo-Zustand bleibt unverändert.

Prüfungen:
  check_stack():          Key-Value-Format + Duplikate in stack.md
  check_upcoming():       Pflicht-Frontmatter (due, status) in UPCOMING/
  check_file_sizes():     Warnung bei Dateien > 100KB (blockiert nicht)
  check_readonly_guards(): injection_patterns.json muss nicht-beschreibbar sein

Aufruf:
  python3 validate_repo.py
  Exit 0: alles OK
  Exit 1: Fehler gefunden (Details auf stdout)
"""
import re, sys, stat
from pathlib import Path

REPO = Path.home() / ".nanobot/workspace/memory_repo"
ERRORS = []

def check_stack():
    """
    Prüft CURRENT/stack.md auf Key-Value-Format und doppelte Keys.
    """
    stack = REPO / "CURRENT/stack.md"
    if not stack.exists():
        ERRORS.append("CURRENT/stack.md fehlt")
        return
    lines = [l for l in stack.read_text().splitlines() if l.strip() and not l.startswith("#")]
    bad = [l for l in lines if l.startswith("- ") and ":" not in l]
    if bad:
        ERRORS.append(f"stack.md: {len(bad)} Zeilen ohne ':' — Key-Value Format prüfen")
    keys = [re.match(r"-\s+(\S+):", l) for l in lines if l.startswith("- ")]
    keys = [m.group(1).lower() for m in keys if m]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        ERRORS.append(f"stack.md: Doppelte Keys: {dupes}")

def check_upcoming():
    """
    Prüft ob UPCOMING/-Dateien das Pflicht-Frontmatter enthalten.
    """
    upcoming_dir = REPO / "UPCOMING"
    if not upcoming_dir.exists():
        return
    for f in upcoming_dir.glob("*.md"):
        text = f.read_text()
        if "due:" not in text:
            ERRORS.append(f"UPCOMING/{f.name}: 'due:' Frontmatter fehlt")
        if "status:" not in text:
            ERRORS.append(f"UPCOMING/{f.name}: 'status:' Frontmatter fehlt")

def check_file_sizes():
    for f in REPO.rglob("*.md"):
        size = f.stat().st_size
        if size > 100_000:  # 100KB — warnt aber blockiert nicht
            print(f"[validate] Warnung: {f.relative_to(REPO)} ist {size//1024}KB groß")

def check_readonly_guards():
    """
    Stellt sicher dass sicherheitskritische Dateien nicht beschreibbar sind.
    """
    guards = [REPO / "CURRENT/injection_patterns.json"]
    for g in guards:
        if not g.exists():
            ERRORS.append(f"{g.name}: Sicherheitsdatei fehlt — chmod 444 nach Anlegen nicht vergessen")
            continue
        mode = g.stat().st_mode
        if mode & (stat.S_IWGRP | stat.S_IWOTH | stat.S_IWUSR):
            ERRORS.append(
                f"{g.name}: Datei ist beschreibbar (erwartet: readonly). "
                f"Fix: chmod 444 {g}"
            )

def main():
    check_stack()
    check_upcoming()
    check_file_sizes()
    check_readonly_guards()
    if ERRORS:
        for e in ERRORS:
            print(f"[validate] FEHLER: {e}")
        sys.exit(1)
    print(f"[validate] OK")

if __name__ == "__main__":
    main()
