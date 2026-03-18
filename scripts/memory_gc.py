#!/usr/bin/env python3
"""
LAMBS Memory Garbage Collector — wöchentliche Repo-Hygiene.

Zweck:
  Implementiert selektives Vergessen (aus der Kognitionswissenschaft bekannt
  als notwendige Funktion zur Kapazitätserhaltung). Entfernt Rauschen ohne
  echte Fakten zu löschen.

Was GC TUT:
  - PROPOSALS/: älter als 30 Tage ohne Approve → ARCHIVE/ (nicht gelöscht)
  - RUNBOOKS/: ≥3 PREVENT-Zeilen → high-error-flag setzen
  - DAILY/: älter als 2 Jahre → gzip-komprimieren (bleibt durchsuchbar via zgrep)
  - CURRENT/: widersprüchliche Keys in verschiedenen Dateien → Conflict-Proposal
  - UPCOMING/: status==done → ARCHIVE/upcoming/ (Audit-Log bleibt erhalten)

Was GC NIEMALS TUT:
  - CURRENT/ löschen oder überschreiben
  - DECISIONS/ anfassen
  - HISTORY.md truncaten

Cron: Sonntag 02:00 (nach Backup, zu ruhiger Zeit)
"""
import gzip, shutil, re
from datetime import date, timedelta
from pathlib import Path

REPO     = Path.home() / ".nanobot/workspace/memory_repo"
TODAY    = date.today()
CUTOFF   = (TODAY - timedelta(days=30)).isoformat()

def archive_old_proposals():
    """
    Verschiebt ungenehmigte Proposals nach 30 Tagen ins ARCHIVE/.
    """
    archive = REPO / "ARCHIVE/proposals"
    archive.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in (REPO / "PROPOSALS").glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m and m.group(1) < CUTOFF:
            shutil.move(str(f), archive / f.name)
            count += 1
    print(f"[gc] {count} Proposals archiviert")

def flag_high_error_runbooks():
    """
    Setzt high-error-flag auf Runbooks mit ≥3 PREVENT-Zeilen.
    """
    for f in (REPO / "RUNBOOKS").glob("*.md"):
        text = f.read_text()
        prevent_count = text.lower().count("prevent:")
        if prevent_count >= 3:
            if "<!-- high-error-runbook -->" not in text:
                f.write_text(f"<!-- high-error-runbook -->\n{text}")
                print(f"[gc] high-error-flag gesetzt: {f.name}")

def detect_conflicts():
    """
    Sucht widersprüchliche Key-Value-Paare über mehrere CURRENT/-Dateien.
    """
    key_values: dict[str, list[tuple[str, str]]] = {}
    for f in (REPO / "CURRENT").rglob("*.md"):
        for line in f.read_text().splitlines():
            m = re.match(r"-\s+(\w[\w_\-]+):\s+(.+)", line)
            if m:
                key, val = m.group(1).lower(), m.group(2).strip()
                key_values.setdefault(key, []).append((val, str(f.relative_to(REPO))))

    conflicts = {k: v for k, v in key_values.items() if len(set(x[0] for x in v)) > 1}
    for key, entries in conflicts.items():
        slug = re.sub(r"[^a-z0-9]+", "-", key)
        out  = REPO / f"PROPOSALS/{TODAY}-conflict-{slug}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"- {val} (in {src})" for val, src in entries)
        out.write_text(f"# Konflikt erkannt: {key}\n\n{body}\n\nBitte CURRENT/ manuell bereinigen.\n")
        print(f"[gc] Konflikt: {key} → {out.name}")

def compress_old_daily():
    """
    Komprimiert DAILY/-Einträge die älter als 2 Jahre sind via gzip.
    """
    cutoff = (TODAY - timedelta(days=730)).isoformat()
    count = 0
    for f in (REPO / "DAILY").glob("*.md"):
        if f.stem < cutoff:
            gz_path = f.with_suffix(".md.gz")
            with f.open("rb") as fi, gzip.open(gz_path, "wb") as fo:
                fo.write(fi.read())
            f.unlink()
            count += 1
    if count:
        print(f"[gc] {count} DAILY-Dateien komprimiert (>2 Jahre)")

def archive_done_upcomings():
    """
    Verschiebt erledigte Upcoming-Reminder ins ARCHIVE/upcoming/.
    """
    archive = REPO / "ARCHIVE/upcoming"
    archive.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in (REPO / "UPCOMING").glob("*.md"):
        if "status: done" in f.read_text():
            shutil.move(str(f), archive / f.name)
            count += 1
    print(f"[gc] {count} erledigte Upcoming-Reminder archiviert")

def main():
    print(f"[gc] Start {TODAY}")
    archive_old_proposals()
    flag_high_error_runbooks()
    detect_conflicts()
    compress_old_daily()
    archive_done_upcomings()
    print("[gc] Fertig")

if __name__ == "__main__":
    main()
