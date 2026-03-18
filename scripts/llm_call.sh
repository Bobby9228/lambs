#!/bin/bash
# =============================================================================
# llm_call.sh — LAMBS LLM-Bridge
# =============================================================================
# Zweck:
#   Delegiert einen einzelnen LLM-Prompt an den laufenden nanobot-Agent.
#   Wird von daily_consolidate.py und pattern_counter.py als Cron-Bridge
#   verwendet, damit keine separaten API-Keys auf dem Host gespeichert werden
#   müssen. Der Agent nutzt seinen konfigurierten Provider (OpenRouter, OAuth).
#
# Verwendung:
#   llm_call.sh "<prompt>"          → Antwort auf stdout
#   llm_call.sh "<prompt>" 500      → Antwort mit Token-Hint
#
# Rückgabewerte:
#   Exit 0 + Text auf stdout  → Erfolg
#   Exit 1 + leerer stdout    → nanobot nicht erreichbar (Caller nutzt Fallback)
#
# Abhängigkeiten:
#   - nanobot muss installiert und konfiguriert sein (nanobot onboard)
#   - nanobot muss im PATH des aufrufenden Prozesses liegen
#     Falls nicht: absoluten Pfad eintragen, z.B. /usr/local/bin/nanobot
#
# Technischer Hintergrund (warum kein --max-tokens Flag):
#   nanobot agent -m hat kein natives Token-Limit-Flag. Der Hint wird
#   deshalb als natürlichsprachliche Anweisung im Prompt übergeben.
# =============================================================================
set -euo pipefail
PROMPT="${1:-}"

if [ -z "$PROMPT" ]; then
    echo "Usage: llm_call.sh \"<prompt>\" [max_tokens_hint]" >&2
    exit 1
fi

# Token-Hint als Prompt-Ergänzung (nanobot hat kein --max-tokens)
if [ -n "${2:-}" ]; then
    PROMPT="$PROMPT (Antworte in maximal $2 Tokens.)"
fi

LOG_DIR="${HOME}/.nanobot/logs"
LOG_FILE="${LOG_DIR}/llm_call.log"
TIMEOUT_SECONDS="${LAMBS_LLM_TIMEOUT_SECONDS:-60}"
RETRIES="${LAMBS_LLM_RETRIES:-2}"
SLEEP_SECONDS="${LAMBS_LLM_RETRY_SLEEP_SECONDS:-2}"

mkdir -p "$LOG_DIR" 2>/dev/null || true

run_once() {
    # nanobot agent -m: bestätigter CLI-Befehl laut nanobot README
    # stdout = Model Output, stderr = Diagnostics (in Logfile)
    if command -v timeout >/dev/null 2>&1; then
        timeout "$TIMEOUT_SECONDS" nanobot agent -m "$PROMPT" 2>>"$LOG_FILE"
    else
        # Fallback ohne timeout (nicht ideal, aber besser als hart zu scheitern)
        nanobot agent -m "$PROMPT" 2>>"$LOG_FILE"
    fi
}

attempt=0
while [ "$attempt" -le "$RETRIES" ]; do
    attempt=$((attempt + 1))
    ts="$(date -Iseconds)"
    echo "[$ts] llm_call attempt=${attempt}/${RETRIES} timeout=${TIMEOUT_SECONDS}s" >>"$LOG_FILE"

    # Capture output so we can validate empties without polluting stdout.
    out="$(run_once || true)"
    if [ -n "$out" ]; then
        printf '%s\n' "$out"
        exit 0
    fi

    echo "[$ts] llm_call: empty output (attempt ${attempt})" >>"$LOG_FILE"
    if [ "$attempt" -le "$RETRIES" ]; then
        sleep "$SLEEP_SECONDS"
    fi
done

# Non-zero exit: bridge failed.
exit 1
