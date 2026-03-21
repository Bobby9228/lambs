#!/bin/bash
# =============================================================================
# memory_backup.sh — LAMBS 3-2-1 Backup via restic
# =============================================================================
# Voraussetzungen (einmalig):
#   apt-get install -y restic || snap install restic
#   restic init --repo /var/backups/lambs-memory
#   echo "<passwort>" > ~/.nanobot/backup.key && chmod 400 ~/.nanobot/backup.key
#
# RPO: max 24h Datenverlust (tägliches Backup + 6h Git-Sync)
# RTO: ~30min (restic restore + git clone + Scripts vorhanden)
#
# Restore-Test (monatlich manuell):
#   restic --repo /var/backups/lambs-memory restore latest --target /tmp/lambs-restore
#   ls /tmp/lambs-restore/
# =============================================================================
set -euo pipefail
RESTIC_PASSWORD_FILE="$HOME/.nanobot/backup.key"
LOG="$HOME/.nanobot/logs/backup.log"

if [ ! -f "$RESTIC_PASSWORD_FILE" ]; then
    echo "[backup] FEHLER: $RESTIC_PASSWORD_FILE fehlt — Backup übersprungen" >> "$LOG"
    exit 1
fi

restic --repo /var/backups/lambs-memory \
       --password-file "$RESTIC_PASSWORD_FILE" \
       backup \
       "$HOME/.nanobot/workspace/memory_repo" \
       "$HOME/.nanobot/workspace/memory/MEMORY.md" \
       --tag lambs \
       --quiet

echo "[backup] $(date -Iseconds)" >> "$LOG"
