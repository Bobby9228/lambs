#!/bin/bash
set -euo pipefail
# =============================================================================
# install_cron.sh — LAMBS Cron-Installer
# =============================================================================
# Sauberes BEGIN/END-Block-Replace via awk — keine fuzzy grep-v.
# Mehrfaches Ausführen ist sicher: Block wird immer komplett ersetzt.
# Liest .lambs_flags — reindex-Cron nur wenn LAMBS_SEMANTIC_ENABLED=1.
# =============================================================================
SCRIPTS="$HOME/.nanobot/scripts"
LOGS="$HOME/.nanobot/logs"
FLAGS="$HOME/.nanobot/workspace/.lambs_flags"
PATH_LINE="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mkdir -p "$LOGS"

# Feature-Flags sicher einlesen — kein source (verhindert Code-Execution bei manipulierter Datei)
LAMBS_SEMANTIC_ENABLED=0
if [ -f "$FLAGS" ]; then
    while IFS='=' read -r key val; do
        # Nur bekannte Keys mit Wert 0 oder 1 akzeptieren
        [[ "$key" =~ ^[A-Z_]+$ ]] && [[ "$val" =~ ^[01]$ ]] || continue
        case "$key" in
            LAMBS_SEMANTIC_ENABLED) LAMBS_SEMANTIC_ENABLED="$val" ;;
        esac
    done < <(grep -v '^\s*#' "$FLAGS" | grep '=')
fi

# Kern-Jobs (immer aktiv)
CORE_JOBS=$(cat <<EOF
$PATH_LINE
0 */6 * * * $SCRIPTS/memory_commit_push.sh >> $LOGS/sync.log 2>&1
5 23 * * * python3 $SCRIPTS/daily_consolidate.py >> $LOGS/consolidate.log 2>&1
10 23 * * * python3 $SCRIPTS/pattern_counter.py >> $LOGS/pattern.log 2>&1
15 23 * * * python3 $SCRIPTS/alerts_generator.py >> $LOGS/alerts.log 2>&1
0 2 * * 0 python3 $SCRIPTS/memory_gc.py >> $LOGS/gc.log 2>&1
30 8 * * * python3 $SCRIPTS/health_check.py >> $LOGS/health.log 2>&1
EOF
)

# Reindex-Job nur wenn Phase 6 aktiv
REINDEX_JOB=""
if [ "$LAMBS_SEMANTIC_ENABLED" = "1" ]; then
    REINDEX_JOB="0 23 * * * python3 $SCRIPTS/memory_search.py --reindex >> $LOGS/reindex.log 2>&1"
    echo "[install_cron] LAMBS_SEMANTIC_ENABLED=1 → reindex-Cron aktiv"
else
    echo "[install_cron] LAMBS_SEMANTIC_ENABLED=0 → kein reindex-Cron (Phase 6 nicht aktiv)"
fi

# Gesamter LAMBS-Block per heredoc — Zeilenumbrüche garantiert korrekt
NEW_BLOCK=$(cat <<EOF
# BEGIN LAMBS
$CORE_JOBS
$REINDEX_JOB
# END LAMBS
EOF
)

# Bestehenden LAMBS-Block entfernen, neuen einfügen
EXISTING=$(crontab -l 2>/dev/null | awk '/^# BEGIN LAMBS/{skip=1} /^# END LAMBS/{skip=0; next} !skip')
printf '%s\n%s\n' "$EXISTING" "$NEW_BLOCK" | crontab -
echo "[install_cron] Cron installiert:"
crontab -l | awk '/^# BEGIN LAMBS/,/^# END LAMBS/'
