#!/usr/bin/env python3
"""
LAMBS Pattern Counter — Selbstlern-Loop via Clustering, Drift-Erkennung und Co-Occurrence.

Drei Kernfunktionen:
  1. Heuristisches Tag-Clustering (Phase 4, ML-frei)
  2. PAMU Drift Detection
  3. Co-Occurrence Tracking

Cron: täglich 23:10 (nach daily_consolidate, vor alerts_generator)
"""
import re
import subprocess
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HISTORY    = Path.home() / ".nanobot/workspace/memory/HISTORY.md"
REPO       = Path.home() / ".nanobot/workspace/memory_repo"
SEARCH_LOG = Path.home() / ".nanobot/memory_search.log"
LLM_CALL   = Path.home() / ".nanobot/scripts/llm_call.sh"
TODAY      = date.today()
CUTOFF     = (TODAY - timedelta(days=30)).isoformat()

TAG_GROUPS = {
    "docker":  ["#docker", "#container", "#image", "#compose", "exit code", "oom killed"],
    "deploy":  ["#deploy", "#rollout", "#release", "rollback", "deploy failed"],
    "network": ["#network", "timeout", "connection refused", "unreachable", "#dns"],
    "auth":    ["#auth", "#oauth", "token", "forbidden", "401", "403"],
    "storage": ["#disk", "no space", "inode", "#storage", "disk full"],
    "agent":   ["#agent", "agent", "main-agent", "#bot"],
}

def load_history_entries() -> list[str]:
    if not HISTORY.exists():
        return []
    return [line for line in HISTORY.read_text().splitlines() if line[:10] >= CUTOFF and line.strip()]

def heuristic_cluster(entries: list[str]) -> dict[str, list[str]]:
    """Gruppiert HISTORY-Einträge anhand von TAG_GROUPS-Keywords (ML-frei)."""
    clusters: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        entry_lower = entry.lower()
        matched = False
        for group, keywords in TAG_GROUPS.items():
            if any(kw in entry_lower for kw in keywords):
                clusters[group].append(entry)
                matched = True
                break
        if not matched:
            clusters["misc"].append(entry)
    return {k: v for k, v in clusters.items() if len(v) >= 3}

def runbook_exists_for(group: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["grep", "-Rl", "--include=*.md", group, str(REPO / "RUNBOOKS")],
        capture_output=True, text=True
    )
    matches = result.stdout.strip().splitlines()
    if matches:
        return True, Path(matches[0]).name
    return False, ""

def generate_proposal(group: str, cluster: list[str]) -> str:
    """Generiert Runbook-Vorschlag via LLM — mit Fallback bei Timeout/Fehler."""
    events_text = "\n".join(f"- {e}" for e in cluster[:8])
    prompt = (
        f"Schreibe eine knappe Runbook-Checkliste für folgende wiederkehrende '{group}'-Events. "
        "Format: ## Problem | ## Checkliste (nummerierte Schritte) | ## PREVENT. "
        f"Deutsch.\n\nEvents:\n{events_text}"
    )
    fallback = (
        f"## Problem\nWiederkehrendes {group}-Muster ({len(cluster)} Events)\n\n"
        f"## Checkliste\n1. Prüfe Logs\n2. Prüfe CURRENT/stack.md\n3. Restart wenn nötig\n\n"
        "## PREVENT\n" + "\n".join(f"- {e[:80]}" for e in cluster[:5])
    )
    try:
        result = subprocess.run(
            [str(LLM_CALL), prompt, "500"],
            capture_output=True,
            text=True,
            timeout=70,
        )
        if result.returncode != 0 or not result.stdout.strip():
            print(
                f"[pattern_counter] LLM bridge failed/empty for group '{group}' "
                f"(rc={result.returncode}) — Template-Fallback"
            )
            return fallback
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        # Explizit abfangen damit pattern_last_success trotzdem geschrieben wird
        print(f"[pattern_counter] LLM-Timeout für Gruppe '{group}' — Template-Fallback")
        return fallback

def validate_output(text: str, max_lines: int = 50) -> bool:
    """Validiert LLM-Output auf Sicherheit und Größe (OWASP LLM02)."""
    lines = text.splitlines()
    if len(lines) > max_lines:
        return False
    suspicious = ["ignore previous", "system:", "you are now", "sk-", "ghp_"]
    return not any(p in text.lower() for p in suspicious)

def pamu_drift_check():
    if not HISTORY.exists():
        return
    lines = HISTORY.read_text().splitlines()
    cutoff_7  = (TODAY - timedelta(days=7)).isoformat()
    cutoff_90 = (TODAY - timedelta(days=90)).isoformat()
    port_pattern = re.compile(r"port[:\s]+(\d{4,5})", re.IGNORECASE)
    recent_ports, historic_ports = [], []
    for line in lines:
        m = port_pattern.search(line)
        if not m:
            continue
        if line[:10] >= cutoff_7:
            recent_ports.append(int(m.group(1)))
        elif line[:10] >= cutoff_90:
            historic_ports.append(int(m.group(1)))
    if recent_ports and historic_ports:
        avg_r = sum(recent_ports) / len(recent_ports)
        avg_h = sum(historic_ports) / len(historic_ports)
        if abs(avg_r - avg_h) > 10:
            out = REPO / f"PROPOSALS/{TODAY}-drift-port.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                f"# Drift erkannt: Port\n\n"
                f"- Historic avg (90d): {avg_h:.0f}\n"
                f"- Recent avg (7d): {avg_r:.0f}\n\n"
                "CURRENT/stack.md prüfen ob Port-Konfiguration aktuell ist.\n"
            )
            print(f"[pattern_counter] Port-Drift → PROPOSALS/{TODAY}-drift-port.md")

def co_occurrence_tracking():
    if not SEARCH_LOG.exists():
        return
    log_lines = SEARCH_LOG.read_text().splitlines()
    cutoff_30 = (TODAY - timedelta(days=30)).isoformat()
    recent = [l for l in log_lines if l[:10] >= cutoff_30]
    sequences: list[tuple[str, str]] = []
    for i in range(len(recent) - 1):
        a = recent[i].split(" → ")
        b = recent[i+1].split(" → ")
        if len(a) == 2 and len(b) == 2 and a[1].strip() != b[1].strip():
            sequences.append((a[1].strip(), b[1].strip()))
    counts: dict[tuple, int] = defaultdict(int)
    for pair in sequences:
        counts[pair] += 1
    significant = [(pair, cnt) for pair, cnt in counts.items() if cnt >= 3]
    if significant:
        print(f"[pattern_counter] {len(significant)} Co-Occurrence(s) — Index-Update in Phase 6")

def main():
    print(f"[pattern_counter] Start {TODAY} (heuristic mode — ML aktiviert in Phase 6)")
    entries = load_history_entries()
    print(f"[pattern_counter] {len(entries)} Einträge der letzten 30 Tage")
    clusters = heuristic_cluster(entries)
    print(f"[pattern_counter] {len(clusters)} Cluster mit ≥3 Mitgliedern")

    proposals_written = 0
    quarantine = REPO / "QUARANTINE"

    for group, cluster in clusters.items():
        exists, runbook_name = runbook_exists_for(group)
        if exists:
            rb_file = REPO / "RUNBOOKS" / runbook_name
            rb_text = rb_file.read_text()
            sample = cluster[0][:60]
            if f"PREVENT: {sample[:20]}" not in rb_text:
                rb_file.write_text(rb_text + f"\nPREVENT: {sample}\n")
                print(f"[pattern_counter] PREVENT ergänzt in {runbook_name}")
        else:
            proposal = generate_proposal(group, cluster)
            if not validate_output(proposal):
                quarantine.mkdir(parents=True, exist_ok=True)
                (quarantine / f"{TODAY}-{group}.md").write_text(proposal)
                print(f"[pattern_counter] QUARANTÄNE: Proposal für {group} — Validation fehlgeschlagen")
                continue
            out = REPO / f"PROPOSALS/{TODAY}-{group}.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(f"# Runbook-Vorschlag: {group}\n\n{proposal}\n")
            proposals_written += 1
            print(f"[pattern_counter] PROPOSAL: {out.name}")

    pamu_drift_check()
    co_occurrence_tracking()
    # FIX: datetime.now() statt date.today() — health_check.py erwartet ISO-Datetime
    (Path.home() / ".nanobot/logs/pattern_last_success").write_text(datetime.now().isoformat())
    print(f"[pattern_counter] Fertig. {proposals_written} neue Proposals.")

if __name__ == "__main__":
    main()
