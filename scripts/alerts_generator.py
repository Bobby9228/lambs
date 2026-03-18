#!/usr/bin/env python3
"""
LAMBS Alerts Generator — erzeugt täglich ALERTS.md aus Fehlern und Reminders.

Zweck:
  ALERTS.md ist die "aktuelle Aufmerksamkeitsfläche" des Agents — analog zum
  Arbeitsgedächtnis. Die Datei wird täglich überschrieben und enthält nur
  das was gerade relevant ist: aktuelle Fehler + fällige Reminder.

Quellen:
  1. HISTORY.md: Einträge mit #error/#critical/#warning der letzten 3 Tage
  2. UPCOMING/: Reminder mit due <= morgen und status == pending

Runbook-Matching:
  Für jeden Fehler wird via KNOWN_TAGS-Dictionary ein passendes Runbook
  gesucht (zwei Stufen: direkter #Tag-Match, dann Keyword-Normalisierung).
  Semantische Suche erst in Phase 6 mit MiniLM.

Seiteneffekte:
  Überschreibt ALERTS.md vollständig — kein Append. Die Datei ist immer
  ein aktueller Snapshot, nicht ein kumulatives Log.

Cron: täglich um 23:15 (nach pattern_counter)
"""
import subprocess
from datetime import date, timedelta
from pathlib import Path

HISTORY  = Path.home() / ".nanobot/workspace/memory/HISTORY.md"
REPO     = Path.home() / ".nanobot/workspace/memory_repo"
ALERTS   = Path.home() / ".nanobot/workspace/ALERTS.md"
UPCOMING = REPO / "UPCOMING"
TODAY    = date.today()

KNOWN_TAGS = {
    "#docker":  ["docker", "container", "image", "compose"],
    "#deploy":  ["deploy", "rollout", "release", "push"],
    "#oom":     ["oom", "killed", "memory", "out of memory"],
    "#network": ["timeout", "connection refused", "unreachable", "dns"],
    "#auth":    ["auth", "token", "oauth", "forbidden", "401", "403"],
    "#disk":    ["disk", "no space", "inode", "storage"],
}

def find_runbook(error_line: str) -> str:
    """
    Findet ein passendes Runbook für einen Fehler-Log-Eintrag.

    Zweistufiger Matching-Ansatz:
        Stufe 1: Direkter #Tag-Match (z.B. "#docker" in der Log-Zeile)
                 → sofortige grep-Suche im RUNBOOKS/-Ordner
        Stufe 2: Keyword-Normalisierung (erste 5 Wörter >3 Zeichen)
                 → prüft ob ein Wort zu bekannten Keyword-Gruppen gehört

    Args:
        error_line: Eine Zeile aus HISTORY.md mit Fehler-Tag

    Returns:
        String mit Runbook-Link oder Hinweis auf fehlenden Runbook.
    """

    line_lower = error_line.lower()

    # 1. Direkter #Tag im Log
    for tag in KNOWN_TAGS:
        if tag in line_lower:
            result = subprocess.run(
                ["grep", "-Rl", "--include=*.md", tag[1:], str(REPO / "RUNBOOKS")],
                capture_output=True, text=True
            )
            matches = result.stdout.strip().splitlines()
            if matches:
                rel = matches[0].replace(str(REPO) + "/", "")
                return f"→ Runbook: [[{rel}]]"

    # 2. Keyword-Normalisierung (lowercase, erste 3 relevante Wörter)
    words = [w for w in line_lower.split() if len(w) > 3][:5]
    for word in words:
        for tag, keywords in KNOWN_TAGS.items():
            if any(kw in word for kw in keywords):
                result = subprocess.run(
                    ["grep", "-Rl", "--include=*.md", keywords[0], str(REPO / "RUNBOOKS")],
                    capture_output=True, text=True
                )
                matches = result.stdout.strip().splitlines()
                if matches:
                    rel = matches[0].replace(str(REPO) + "/", "")
                    return f"→ Runbook: [[{rel}]]"

    return "→ kein Runbook — Kandidat für Skill-Generierung"

def get_error_alerts() -> list[str]:
    """
    Sammelt Fehler-Einträge der letzten 3 Tage aus HISTORY.md.

    Filtert auf #error, #critical und #warning Tags. Begrenzt auf
    die letzten 10 Einträge um den Alert-Output übersichtlich zu halten.
    Für jeden Fehler wird find_runbook() aufgerufen um direkt einen
    Lösungsweg zu verlinken.

    Returns:
        Liste von formatierten Alert-Strings für ALERTS.md.
    """
    if not HISTORY.exists():
        return []
    lines = HISTORY.read_text().splitlines()
    cutoff = (TODAY - timedelta(days=3)).isoformat()
    errors = [
        l for l in lines
        if any(tag in l.lower() for tag in ["#error", "#critical", "#warning"])
        and l[:10] >= cutoff
    ][-10:]

    blocks = []
    for e in errors:
        tag = "#critical" if "#critical" in e.lower() else "#error" if "#error" in e.lower() else "#warning"
        runbook = find_runbook(e)
        blocks.append(f"- [{tag.upper()[1:]}] {e[:100]}\n  {runbook}")
    return blocks

def get_upcoming_alerts() -> list[str]:
    """
    Sammelt fällige Reminder aus UPCOMING/ (heute + morgen).

    Liest YAML-Frontmatter aus jeder Upcoming-Datei und prüft das
    due-Datum. Übersprungene (done/snoozed) werden ignoriert.
    Überfällige Reminder (due < heute) erhalten einen [OVERDUE]-Marker.

    Returns:
        Liste von formatierten Reminder-Strings für ALERTS.md.
    """
    if not UPCOMING.exists():
        return []
    blocks = []
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    for f in sorted(UPCOMING.glob("*.md")):
        text = f.read_text()
        if "status: done" in text or "status: snoozed" in text:
            continue
        # Extrahiere due-Datum aus Frontmatter
        for line in text.splitlines():
            if line.startswith("due:"):
                due = line.split(":", 1)[1].strip()
                if due <= tomorrow:
                    if "## Reminder" in text:
                        tail = text.split("## Reminder", 1)[1].strip()
                        title = tail.splitlines()[0].strip() if tail.splitlines() else f.stem
                    else:
                        title = f.stem
                    overdue = " [OVERDUE]" if due < TODAY.isoformat() else ""
                    blocks.append(f"- [UPCOMING{overdue}] {due} — {title}\n  Datei: {f.name}")
                break
    return blocks

def main():
    error_alerts    = get_error_alerts()
    upcoming_alerts = get_upcoming_alerts()

    if not error_alerts and not upcoming_alerts:
        content = f"## Active Alerts (generated {TODAY} — keine offenen Alerts)\n"
    else:
        lines = [f"## Active Alerts (generated {TODAY})"]
        if upcoming_alerts:
            lines.append("\n### Upcoming Reminders")
            lines.extend(upcoming_alerts)
        if error_alerts:
            lines.append("\n### Recent Errors")
            lines.extend(error_alerts)
        content = "\n".join(lines) + "\n"

    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    ALERTS.write_text(content)
    print(f"[alerts] {len(error_alerts)} Fehler, {len(upcoming_alerts)} Reminder")

if __name__ == "__main__":
    main()
