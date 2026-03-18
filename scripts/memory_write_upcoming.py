#!/usr/bin/env python3
"""
LAMBS Write Upcoming — Prospektives Gedächtnis für datierte Reminder.

Modi:
  Erstellen: memory_write_upcoming.py <YYYY-MM-DD> "<aufgabe>" [--runbook RUNBOOKS/x.md]
  Erledigen: memory_write_upcoming.py --done UPCOMING/<datei>
  Snoosen:   memory_write_upcoming.py --snooze UPCOMING/<datei> --to <YYYY-MM-DD>

Fixes gegenüber v1:
  - argparse statt sys.argv → Aufgaben mit Leerzeichen funktionieren korrekt
  - Path-Traversal-Guard via .resolve().relative_to() bei --done/--snooze
  - Datumsformat-Validierung via date.fromisoformat()
  - atomarer Write via tempfile + os.replace (wie memory_write_current.py)
"""

import argparse, os, re
from datetime import date
from pathlib import Path
from input_sanitizer import sanitize_or_raise, SanitizationError

REPO = Path.home() / ".nanobot/workspace/memory_repo"


def _safe_resolve(user_path: str) -> Path:
    """
    Löst einen User-Pfad auf und prüft dass er innerhalb von REPO liegt.
    Verhindert Path-Traversal wie: --done '../../scripts/memory_write_current.py'
    Raises ValueError wenn der Pfad außerhalb von REPO liegt.
    """
    candidate = (REPO / user_path).resolve()
    try:
        candidate.relative_to(REPO.resolve())
    except ValueError:
        raise ValueError(f"Pfad außerhalb von REPO nicht erlaubt: {user_path!r}")
    return candidate


def cmd_create(args):
    """Erstellt einen neuen Reminder."""
    due_date = args.due_date
    aufgabe  = args.aufgabe
    runbook  = args.runbook or ""

    # Datumsformat validieren
    try:
        date.fromisoformat(due_date)
    except ValueError:
        print(f"[upcoming] Ungültiges Datum: {due_date!r} (erwartet: YYYY-MM-DD)")
        raise SystemExit(1)

    try:
        sanitize_or_raise(aufgabe)
    except SanitizationError as e:
        print(f"[upcoming] BLOCKIERT: {e}")
        raise SystemExit(1)

    slug = re.sub(r"[^a-z0-9]+", "-", aufgabe.lower()).strip("-")[:30]
    filename = f"{due_date}-{slug}.md"
    outfile  = REPO / "UPCOMING" / filename
    outfile.parent.mkdir(parents=True, exist_ok=True)

    content = (
        f"---\n"
        f"due: {due_date}\n"
        f"created: {date.today().isoformat()}\n"
        f"status: pending\n"
        f"runbook: {runbook}\n"
        f"---\n"
        f"## Reminder\n"
        f"{aufgabe}\n"
    )

    # Atomarer Write
    tmp = outfile.parent / f".upcoming.tmp.{os.getpid()}"
    tmp.write_text(content)
    os.replace(tmp, outfile)
    print(f"[upcoming] Reminder erstellt: {filename}")


def cmd_done(args):
    """Markiert einen Reminder als erledigt."""
    try:
        filepath = _safe_resolve(args.file)
    except ValueError as e:
        print(f"[upcoming] BLOCKIERT: {e}")
        raise SystemExit(1)
    if not filepath.exists():
        print(f"[upcoming] Datei nicht gefunden: {args.file}")
        raise SystemExit(1)
    text = filepath.read_text().replace("status: pending", "status: done")
    tmp  = filepath.parent / f".upcoming.tmp.{os.getpid()}"
    tmp.write_text(text)
    os.replace(tmp, filepath)
    print(f"[upcoming] Als erledigt markiert: {filepath.name}")


def cmd_snooze(args):
    """Snoozed einen Reminder auf ein neues Datum."""
    try:
        filepath = _safe_resolve(args.file)
    except ValueError as e:
        print(f"[upcoming] BLOCKIERT: {e}")
        raise SystemExit(1)
    if not filepath.exists():
        print(f"[upcoming] Datei nicht gefunden: {args.file}")
        raise SystemExit(1)
    try:
        date.fromisoformat(args.to)
    except ValueError:
        print(f"[upcoming] Ungültiges Datum: {args.to!r} (erwartet: YYYY-MM-DD)")
        raise SystemExit(1)
    text = filepath.read_text()
    text = re.sub(r"due: \S+", f"due: {args.to}", text)
    text = text.replace("status: pending", "status: snoozed")
    tmp  = filepath.parent / f".upcoming.tmp.{os.getpid()}"
    tmp.write_text(text)
    os.replace(tmp, filepath)
    print(f"[upcoming] Gesnoozed bis: {args.to}")


def main():
    parser = argparse.ArgumentParser(description="LAMBS Upcoming Memory Writer")
    sub = parser.add_subparsers(dest="cmd")

    # Erstellen: memory_write_upcoming.py create 2026-04-01 "rotate ssh keys" --runbook RUNBOOKS/security.md
    p_create = sub.add_parser("create", help="Neuen Reminder erstellen")
    p_create.add_argument("due_date", help="Fälligkeitsdatum (YYYY-MM-DD)")
    p_create.add_argument("aufgabe", help="Aufgabenbeschreibung (in Anführungszeichen)")
    p_create.add_argument("--runbook", default="", help="Optionaler Runbook-Link")

    # Erledigen: memory_write_upcoming.py done UPCOMING/2026-04-01-rotate-ssh-keys.md
    p_done = sub.add_parser("done", help="Reminder als erledigt markieren")
    p_done.add_argument("file", help="Pfad relativ zu REPO (z.B. UPCOMING/datei.md)")

    # Snoosen: memory_write_upcoming.py snooze UPCOMING/... --to 2026-04-15
    p_snooze = sub.add_parser("snooze", help="Reminder verschieben")
    p_snooze.add_argument("file", help="Pfad relativ zu REPO")
    p_snooze.add_argument("--to", required=True, help="Neues Datum (YYYY-MM-DD)")

    # Rückwärtskompatibilität: altes Interface (positionale Args ohne Subcommand)
    # memory_write_upcoming.py 2026-04-01 "aufgabe" [--runbook ...]
    # memory_write_upcoming.py --done UPCOMING/...
    # memory_write_upcoming.py --snooze UPCOMING/... --to ...
    parsed, remaining = parser.parse_known_args()

    if parsed.cmd is None:
        # Legacy-Modus
        import sys
        legacy = sys.argv[1:]
        if not legacy:
            parser.print_help()
            raise SystemExit(1)
        if legacy[0] == "--done":
            if len(legacy) < 2:
                print("Usage: memory_write_upcoming.py --done UPCOMING/<datei>")
                raise SystemExit(1)
            parsed.file = legacy[1]
            cmd_done(parsed)
        elif legacy[0] == "--snooze":
            if len(legacy) < 4 or legacy[2] != "--to":
                print("Usage: memory_write_upcoming.py --snooze UPCOMING/<datei> --to <YYYY-MM-DD>")
                raise SystemExit(1)
            parsed.file = legacy[1]
            parsed.to   = legacy[3]
            cmd_snooze(parsed)
        else:
            # Positionale Args: <datum> <aufgabe> [--runbook x]
            if len(legacy) < 2:
                print("Usage: memory_write_upcoming.py <YYYY-MM-DD> \"<aufgabe>\" [--runbook RUNBOOKS/x.md]")
                raise SystemExit(1)
            parsed.due_date = legacy[0]
            parsed.aufgabe  = legacy[1]
            parsed.runbook  = ""
            if "--runbook" in legacy:
                idx = legacy.index("--runbook")
                parsed.runbook = legacy[idx + 1] if idx + 1 < len(legacy) else ""
            cmd_create(parsed)
        return

    dispatch = {"create": cmd_create, "done": cmd_done, "snooze": cmd_snooze}
    dispatch[parsed.cmd](parsed)


if __name__ == "__main__":
    main()
