#!/bin/bash
# =============================================================================
# memory_commit_push.sh — LAMBS Git-Sync
# =============================================================================
# Zweck:
#   Committet ausstehende Änderungen im Memory-Repo und pusht sie zum Remote.
#   Läuft 4× täglich via Cron. Alle Write-Scripts machen lokale Änderungen,
#   dieser Script synchronisiert sie gebündelt zum Remote (Batch-Sync-Prinzip).
#
# Sicherheits-Mechanismen:
#   flock:       Verhindert Race Condition mit gleichzeitigen Agent-Writes
#   --ff-only:   Kein automatisches Mergen — Single-Writer-Policy
#   set -euo:    Bricht bei jedem Fehler ab (kein stilles Weiterlaufen)
#   last_success: Timestamp für health_check.py (stille Ausfälle erkennen)
#
# Single-Writer-Policy:
#   Nur dieser Server schreibt ins Repo. Änderungen von anderen Geräten
#   müssen als PR/Review gemacht und dann hier gepullt werden.
#   Bei ff-only Fehler: KEIN automatisches Rebase, manuell lösen.
#   Runbook: RUNBOOKS/git-divergence.md
# =============================================================================
set -euo pipefail
REPO="$HOME/.nanobot/workspace/memory_repo"
LOCK="$HOME/.nanobot/logs/repo.lock"
LOG="$HOME/.nanobot/logs/sync.log"
SUCCESS="$HOME/.nanobot/logs/sync_last_success"

mkdir -p "$(dirname "$LOG")"

# Globales flock — verhindert Race Condition mit gleichzeitigen Cron/Agent-Writes
exec 9>"$LOCK"
flock -w 10 9 || { echo "[memory_sync] Lock timeout $(date)" >> "$LOG"; exit 1; }

cd "$REPO" || exit 1

# Repo-Validierung vor dem Commit
python3 "$HOME/.nanobot/scripts/validate_repo.py" || {
    echo "[memory_sync] FEHLER: validate_repo.py fehlgeschlagen — Commit abgebrochen $(date)" >> "$LOG"
    exit 1
}

# Single-Writer Policy: nur dieser Server schreibt.
# Bei --ff-only Fehler: nicht automatisch rebasen, manuell lösen.
# Runbook: RUNBOOKS/git-divergence.md
if ! git pull --ff-only --quiet 2>>"$LOG"; then
    echo "[memory_sync] FEHLER: git pull --ff-only fehlgeschlagen — Divergenz? Manuell lösen. $(date)" >> "$LOG"
    python3 "$HOME/.nanobot/scripts/health_check.py" --alert "git pull fehlgeschlagen" 2>/dev/null || true
    exit 1
fi

git add -A
if ! git diff --cached --quiet; then
    git commit -m "auto: $(date '+%Y-%m-%d %H:%M')" --quiet
    if ! git push --quiet 2>>"$LOG"; then
        echo "[memory_sync] FEHLER: git push fehlgeschlagen $(date)" >> "$LOG"
        exit 1
    fi
    echo "[memory_sync] pushed at $(date '+%H:%M')" >> "$LOG"
fi
date -Iseconds > "$SUCCESS"  # last_success für health_check.py
