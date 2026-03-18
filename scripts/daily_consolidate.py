#!/usr/bin/env python3
"""
LAMBS Daily Consolidator — Verdichtet HISTORY.md zu strukturierten Tageseinträgen.

Zweck:
  Implementiert das "Offline-Konsolidierungs"-Prinzip aus der kognitiven
  Neurowissenschaft (analog zum Schlaf-Replay im Hippocampus): rohe Events
  aus HISTORY.md werden zu einem strukturierten DAILY/-Eintrag verdichtet.
  Schicht 1 (Scratchpad) → Schicht 2 (Kanonisches Memory).

LLM-Bridge:
  Nutzt llm_call.sh → nanobot agent -m. Kein OPENAI_API_KEY auf dem Host.
  Bei nicht erreichbarem nanobot: Template-Fallback (Rohauflistung der Events).

Output-Format (LLM-Instruktion):
  ## Events | ## Entscheidungen | ## Offene Punkte — max. 30 Zeilen, keine Prosa.

Output-Validation:
  LLM-Output wird vor dem Commit geprüft (max. 50 Zeilen, keine Secrets/Injektionen).
  Bei Verstoß: QUARANTINE/ statt DAILY/. Commit wird nicht ausgeführt.

Cron: täglich 23:05 (nach reindex, vor pattern_counter)
"""
import subprocess
from datetime import date
from pathlib import Path

HISTORY  = Path.home() / ".nanobot/workspace/memory/HISTORY.md"
REPO     = Path.home() / ".nanobot/workspace/memory_repo"
LLM_CALL = Path.home() / ".nanobot/scripts/llm_call.sh"
TODAY    = date.today().isoformat()

def main():
    if not HISTORY.exists():
        print("[consolidate] HISTORY.md nicht gefunden")
        return

    today_lines = [
        line for line in HISTORY.read_text().splitlines()
        if line.startswith(TODAY)
    ]

    if len(today_lines) < 3:
        print(f"[consolidate] Nur {len(today_lines)} Einträge heute — überspringe")
        return

    events_text = "\n".join(today_lines)
    prompt = (
        "Du bist ein Archivar. Fasse folgende Events als strukturierten Tageslog zusammen. "
        "Format: ## Events | ## Entscheidungen | ## Offene Punkte. "
        f"Max 30 Zeilen. Keine freie Prosa. Deutsch.\n\nEvents:\n{events_text}"
    )

    result = subprocess.run(
        [str(LLM_CALL), prompt, "800"],
        capture_output=True,
        text=True,
        timeout=70,
    )

    if result.returncode != 0 or not result.stdout.strip():
        # llm_call.sh logs stderr and retry details to ~/.nanobot/logs/llm_call.log
        print(
            "[consolidate] LLM nicht erreichbar/leer — Template-Fallback "
            f"(rc={result.returncode})"
        )
        summary = "## Events\n" + "\n".join(f"- {line}" for line in today_lines[:20])
    else:
        summary = result.stdout.strip()

    # Output-Validation: LLM-Output vor dem Commit prüfen
    output_lines = summary.splitlines()
    suspicious = ["ignore previous", "system:", "you are now", "sk-", "ghp_", "bearer "]
    is_clean = (
        len(output_lines) <= 50
        and not any(p in summary.lower() for p in suspicious)
    )
    if not is_clean:
        quarantine = REPO / "QUARANTINE"
        quarantine.mkdir(exist_ok=True)
        (quarantine / f"{TODAY}-daily.md").write_text(summary)
        print(f"[consolidate] QUARANTÄNE: Output-Validation fehlgeschlagen — nicht committed")
        return

    outfile = REPO / f"DAILY/{TODAY}.md"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(f"# {TODAY}\n\n{summary}\n")
    print(f"[consolidate] DAILY/{TODAY}.md geschrieben ({len(today_lines)} Events)")

if __name__ == "__main__":
    main()
