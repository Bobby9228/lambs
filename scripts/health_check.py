#!/usr/bin/env python3
"""
LAMBS Health Check — tägliche Überprüfung der System-Gesundheit.

Zweck:
  Verhindert stille Ausfälle: Cron-Jobs die scheitern sind ohne Monitoring
  oft tagelang unbemerkt. health_check.py prüft last_success-Timestamps
  und meldet Überschreitungen.

Architektur (two-tier):
  Tier 1 (deterministisch, immer): schreibt Alert in ALERTS.md
    → Der Agent sieht den Alert beim nächsten Prompt-Aufruf
    → Funktioniert auch wenn nanobot gerade nicht läuft
  Tier 2 (optional, best-effort): nanobot agent -m für Echtzeit-Notification
    → Sofortige Benachrichtigung wenn nanobot erreichbar
    → Fehler werden mit try/except unterdrückt (non-critical path)

Prüf-Regeln:
  sync:    last_success darf max. 6h alt sein (Cron: alle 6h)
  pattern: last_success darf max. 26h alt sein (Cron: täglich + Puffer)

Cron: täglich um 08:30 (Tagesstart — Probleme der Nacht sichtbar machen)
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGS   = Path.home() / ".nanobot/logs"
LLM    = Path.home() / ".nanobot/scripts/llm_call.sh"

CHECKS = {
    "sync":    (LOGS / "sync_last_success",    6),   # max 6h alt
    "pattern": (LOGS / "pattern_last_success", 26),  # max 26h alt
}

def check_freshness(name: str, path: Path, max_hours: int) -> str | None:
    """
    Prüft ob eine last_success-Datei innerhalb des erlaubten Alters liegt.

    Returns:
        None wenn OK, Fehlermeldung als String wenn zu alt oder nicht vorhanden.
    """
    if not path.exists():
        return f"[health] {name}: last_success fehlt — noch nie gelaufen?"
    try:
        ts = datetime.fromisoformat(path.read_text().strip())
        # Support naive + aware timestamps
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age = now - ts
        if age > timedelta(hours=max_hours):
            hours = int(age.total_seconds()) // 3600
            return f"[health] {name}: letzter Erfolg vor {hours}h (Limit: {max_hours}h)"
    except Exception as e:
        return f"[health] {name}: last_success nicht lesbar — {e}"
    return None

def alert(message: str):
    """
    Schreibt Alert in ALERTS.md (deterministisch, immer funktioniert).
    Versucht zusätzlich llm_call.sh für Echtzeit-Notification —
    aber ALERTS.md ist die verlässliche Basis.

    WICHTIG: Damit der Agent bei 'LAMBS_HEALTH_ALERT:' eine Telegram-Nachricht
    sendet, muss in SKILL.md oder AGENTS.md eine Regel definiert sein:
    'Wenn ALERTS.md den Präfix LAMBS_HEALTH_ALERT: enthält → sende Notification.'
    Ohne diese Regel landet der Alert nur in ALERTS.md (trotzdem sichtbar).
    """
    import subprocess
    ALERTS = Path.home() / ".nanobot/workspace/ALERTS.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    alert_line = f"\n- [HEALTH ALERT] {ts}: {message}\n"
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    with ALERTS.open("a") as f:
        f.write(alert_line)
    print(message)
    # Optional: Echtzeit-Notification via nanobot CLI (nur wenn erreichbar)
    try:
        subprocess.run(
            ["nanobot", "agent", "-m", f"LAMBS_HEALTH_ALERT: {message}"],
            timeout=10, capture_output=True
        )
    except Exception:
        pass  # Fallback: Alert liegt in ALERTS.md

def main():
    args = sys.argv[1:]
    # Direkter Alert-Aufruf (z.B. von memory_commit_push.sh)
    if args and args[0] == "--alert":
        alert(" ".join(args[1:]))
        return

    problems = []
    for name, (path, max_h) in CHECKS.items():
        issue = check_freshness(name, path, max_h)
        if issue:
            problems.append(issue)

    if problems:
        for p in problems:
            alert(p)
    else:
        print(f"[health] Alle Checks OK ({datetime.now().strftime('%H:%M')})")

if __name__ == "__main__":
    main()
