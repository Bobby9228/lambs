#!/bin/bash
# =============================================================================
# approve_proposal.sh — Verschiebt einen Proposal in RUNBOOKS/
# =============================================================================
# Usage: approve_proposal.sh PROPOSALS/2026-03-16-deploy.md
#
# Was passiert:
#   1. Proposal wird von PROPOSALS/ nach RUNBOOKS/ verschoben
#   2. git commit mit "approve: <dateiname>"
#   3. memory_commit_push.sh übernimmt den Push beim nächsten Cron-Lauf
#      (oder direkt pushen mit: git -C "$REPO" push)
# =============================================================================
set -euo pipefail
REPO="$HOME/.nanobot/workspace/memory_repo"

if [ -z "${1:-}" ]; then
    echo "Usage: approve_proposal.sh PROPOSALS/<dateiname>.md"
    exit 1
fi

PROPOSAL="$REPO/$1"
if [ ! -f "$PROPOSAL" ]; then
    echo "[approve] Datei nicht gefunden: $PROPOSAL"
    exit 1
fi

BASENAME=$(basename "$PROPOSAL")
DEST="$REPO/RUNBOOKS/$BASENAME"
mv "$PROPOSAL" "$DEST"
cd "$REPO"
git add RUNBOOKS/ PROPOSALS/
git commit -m "approve: $BASENAME"
echo "[approve] Approved: $DEST"
echo "[approve] Push erfolgt beim nächsten memory_commit_push.sh Lauf (Cron)"
echo "[approve] Oder direkt pushen: git -C \"$REPO\" push"
