#!/usr/bin/env python3
"""
LAMBS Write ADR — Erstellt Architecture Decision Records in DECISIONS/.

Zweck:
  Legt eine neue, vorgefertigte ADR-Datei an wenn eine Entscheidung
  mit Kontext, Alternativen und Tradeoffs dokumentiert werden soll.
  ADRs sind die langfristigste Memory-Schicht — sie werden nie gelöscht.

Dateiname-Schema:
  ADR-YYYY-MM-DD-<slug>.md — automatisch aus Titel generiert.
  Slug: lowercase, nur a-z0-9 und Bindestriche, max. 40 Zeichen.

Nach dem Erstellen:
  Die Datei enthält ein Template mit Abschnitten die manuell ausgefüllt
  werden müssen. memory_search.py --reindex-file wird aufgerufen damit
  die ADR sofort durchsuchbar ist (Phase 6 aktiv).
"""

import sys
from datetime import date
from pathlib import Path
from input_sanitizer import sanitize_or_raise, SanitizationError
import re, subprocess

REPO = Path.home() / ".nanobot/workspace/memory_repo"

def main():
    if len(sys.argv) < 2:
        print("Usage: memory_write_adr.py <titel>")
        sys.exit(1)

    titel = " ".join(sys.argv[1:])
    try:
        sanitize_or_raise(titel)
    except SanitizationError as e:
        print(f"[write_adr] BLOCKIERT: {e}"); sys.exit(1)

    slug = re.sub(r"[^a-z0-9]+", "-", titel.lower()).strip("-")[:40]
    today = date.today().isoformat()
    filename = f"ADR-{today}-{slug}.md"
    outfile = REPO / "DECISIONS" / filename

    template = f"""# ADR: {titel}

Datum: {today}
Status: draft

## Kontext
<!-- Was ist die Situation? Warum ist eine Entscheidung nötig? -->

## Entscheidung
<!-- Was wurde entschieden? -->

## Alternativen
<!-- Welche Optionen wurden erwogen? -->

## Konsequenzen
<!-- Was sind die Auswirkungen? Tradeoffs? -->
"""
    outfile.write_text(template)
    print(f"[write_adr] {filename} erstellt — bitte ausfüllen")
    subprocess.run(["python3", str(Path.home() / ".nanobot/scripts/memory_search.py"),
                    "--reindex-file", f"DECISIONS/{filename}"])

if __name__ == "__main__":
    main()
