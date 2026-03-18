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

# nanobot agent -m: bestätigter CLI-Befehl laut nanobot README
# Stderr wird unterdrückt (nanobot-Startmeldungen sollen nicht in die Ausgabe)
nanobot agent -m "$PROMPT" 2>/dev/null
