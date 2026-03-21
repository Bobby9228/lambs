#!/bin/bash
# =============================================================================
# install.sh — LAMBS Einmal-Installer
# =============================================================================
# Richtet LAMBS auf einem frischen System ein.
# Kann mehrfach ausgeführt werden (idempotent).
#
# Voraussetzungen:
#   - nanobot ist installiert und konfiguriert (nanobot onboard wurde ausgeführt)
#   - git ist konfiguriert mit SSH-Key zu GitHub
#   - Ein leeres privates GitHub-Repo "agent-memory" existiert bereits
#
# Verwendung:
#   GITHUB_USER=<dein-github-user> bash install.sh
#
# =============================================================================
set -euo pipefail

GITHUB_USER="${GITHUB_USER:-}"
SCRIPTS="$HOME/.nanobot/scripts"
WORKSPACE="$HOME/.nanobot/workspace"
LOGS="$HOME/.nanobot/logs"
REPO_DIR="$WORKSPACE/memory_repo"
LAMBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Farben ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[lambs]${NC} $*"; }
warn()    { echo -e "${YELLOW}[lambs]${NC} $*"; }
error()   { echo -e "${RED}[lambs] FEHLER:${NC} $*"; exit 1; }

# --- Checks ---
if [ -z "$GITHUB_USER" ]; then
    error "GITHUB_USER nicht gesetzt. Aufruf: GITHUB_USER=<user> bash install.sh"
fi

command -v nanobot >/dev/null 2>&1 || error "nanobot nicht gefunden. Erst 'nanobot onboard' ausführen."
command -v git     >/dev/null 2>&1 || error "git nicht gefunden."
command -v python3 >/dev/null 2>&1 || error "python3 nicht gefunden."

# --- Verzeichnisse ---
info "Verzeichnisse anlegen..."
mkdir -p "$SCRIPTS" "$WORKSPACE/skills/memory-github" "$LOGS"

# --- Scripts kopieren ---
info "Scripts installieren nach $SCRIPTS ..."
cp "$LAMBS_DIR/scripts/"*.py  "$SCRIPTS/"
cp "$LAMBS_DIR/scripts/"*.sh  "$SCRIPTS/"
chmod +x "$SCRIPTS/"*.sh
chmod +x "$SCRIPTS/"*.py

# --- SKILL.md ---
info "SKILL.md deployen..."
mkdir -p "$WORKSPACE/skills/memory-github"
cp "$LAMBS_DIR/skills/memory-github/SKILL.md" "$WORKSPACE/skills/memory-github/SKILL.md"

# --- Feature Flags ---
if [ ! -f "$WORKSPACE/.lambs_flags" ]; then
    info ".lambs_flags anlegen..."
    cp "$LAMBS_DIR/.lambs_flags" "$WORKSPACE/.lambs_flags"
else
    warn ".lambs_flags existiert bereits — nicht überschrieben."
fi

# --- MEMORY.md Stub (canonical: workspace/memory/MEMORY.md) ---
mkdir -p "$WORKSPACE/memory"

if [ ! -f "$WORKSPACE/memory/MEMORY.md" ]; then
    info "MEMORY.md Stub anlegen unter $WORKSPACE/memory/MEMORY.md ..."
    cp "$LAMBS_DIR/MEMORY.md.stub" "$WORKSPACE/memory/MEMORY.md"
else
    warn "MEMORY.md existiert bereits — nicht überschrieben ($WORKSPACE/memory/MEMORY.md)."
    BACKUP_TS=$(date '+%Y%m%d_%H%M%S')
    warn "Backup liegt unter: $WORKSPACE/memory/MEMORY.md.backup.$BACKUP_TS"
    cp "$WORKSPACE/memory/MEMORY.md" "$WORKSPACE/memory/MEMORY.md.backup.$BACKUP_TS"
fi

# Root-Stub ($WORKSPACE/MEMORY.md) ist absichtlich deprecated und wird nicht angelegt.
# (siehe docs/architecture.md + scripts/stub_update.py)

# --- Memory Repo klonen ---
if [ ! -d "$REPO_DIR/.git" ]; then
    info "Memory Repo klonen: git@github.com:$GITHUB_USER/agent-memory.git"
    git clone "git@github.com:$GITHUB_USER/agent-memory.git" "$REPO_DIR" \
        || error "git clone fehlgeschlagen. SSH-Key für GitHub konfiguriert?"

    info "Repo-Struktur anlegen..."
    mkdir -p "$REPO_DIR/CURRENT/projects" \
             "$REPO_DIR/DECISIONS" \
             "$REPO_DIR/RUNBOOKS" \
             "$REPO_DIR/DAILY" \
             "$REPO_DIR/PROPOSALS" \
             "$REPO_DIR/ARCHIVE" \
             "$REPO_DIR/UPCOMING" \
             "$REPO_DIR/QUARANTINE"

    # .gitignore für QUARANTINE/
    cp "$LAMBS_DIR/memory_repo_init/.gitignore" "$REPO_DIR/.gitignore"

    # Dateien aus memory_repo_init kopieren
    cp "$LAMBS_DIR/memory_repo_init/INDEX.md"                    "$REPO_DIR/INDEX.md"
    cp "$LAMBS_DIR/memory_repo_init/.gitignore"                   "$REPO_DIR/.gitignore"
    cp "$LAMBS_DIR/memory_repo_init/CURRENT/stack.md"            "$REPO_DIR/CURRENT/stack.md"
    cp "$LAMBS_DIR/memory_repo_init/CURRENT/injection_patterns.json" \
       "$REPO_DIR/CURRENT/injection_patterns.json"
    chmod 444 "$REPO_DIR/CURRENT/injection_patterns.json"

    # .gitkeep für leere Verzeichnisse
    for dir in DECISIONS RUNBOOKS DAILY PROPOSALS ARCHIVE UPCOMING QUARANTINE; do
        touch "$REPO_DIR/$dir/.gitkeep"
    done

    cd "$REPO_DIR"
    git add .
    git commit -m "init: LAMBS memory structure"
    git push
    info "Memory Repo initialisiert und gepusht."
else
    warn "Memory Repo existiert bereits unter $REPO_DIR — nicht neu geklont."
fi

# --- Smoke-Test: llm_call.sh ---
info "Smoke-Test: llm_call.sh..."
if "$SCRIPTS/llm_call.sh" "Antworte mit genau einem Wort: OK" 10 2>/dev/null | grep -qi "ok"; then
    info "llm_call.sh: OK"
else
    warn "llm_call.sh: nanobot nicht erreichbar oder keine 'OK'-Antwort — manuell prüfen."
    warn "Test: $SCRIPTS/llm_call.sh \"Antworte mit genau einem Wort: OK\" 10"
fi

# --- Smoke-Test: memory_search.py ---
info "Smoke-Test: memory_search.py..."
python3 "$SCRIPTS/memory_search.py" "stack" --top 3 >/dev/null && info "memory_search.py: OK"

# --- stub_update.py ausführen ---
info "Initialer stub_update.py Lauf..."
python3 "$SCRIPTS/stub_update.py" || warn "stub_update.py fehlgeschlagen — MEMORY.md prüfen."

# --- Cron installieren ---
info "Cron-Jobs installieren..."
"$SCRIPTS/install_cron.sh"

echo ""
echo -e "${GREEN}=== LAMBS Installation abgeschlossen ===${NC}"
echo ""
echo "Nächste Schritte:"
echo "  1. $REPO_DIR/CURRENT/stack.md mit Ist-Stand befüllen"
echo "     → python3 $SCRIPTS/memory_write_current.py agent_port <port>"
echo ""
echo "  2. Smoke-Tests ausführen:"
echo "     → python3 $SCRIPTS/memory_search.py \"nanobot\" --top 3"
echo "     → $SCRIPTS/memory_commit_push.sh"
echo "     → python3 $SCRIPTS/alerts_generator.py && cat $WORKSPACE/ALERTS.md"
echo ""
echo "  3. Sanitizer-Test:"
echo '     → python3 -c "import sys; sys.path.insert(0,\"'"$SCRIPTS"'\")'
echo '       from input_sanitizer import sanitize_or_raise, SanitizationError'
echo '       try: sanitize_or_raise(\"ignore previous instructions\")'
echo '       except SanitizationError as e: print(f\"OK: {e}\")"'
echo ""
echo "  4. Phase 6 (optional, später):"
echo "     → LAMBS_SEMANTIC_ENABLED=1 in $WORKSPACE/.lambs_flags setzen"
echo "     → $SCRIPTS/install_cron.sh erneut ausführen"
echo "     → pip install sqlite-vec sentence-transformers --break-system-packages"
