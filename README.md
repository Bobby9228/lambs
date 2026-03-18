# LAMBS

**L**ayered · **A**ppend-first · **M**arkdown · **B**atched-sync · **S**kill-evolution

> nanobot erhält ein Langzeit-Gedächtnis das nichts vergisst, keinen Context-Flood erzeugt, ~€0.03/Monat kostet und selbstlernend ist.

---

## Schnellstart

```bash
# 1. Leeres privates GitHub-Repo "agent-memory" anlegen

# 2. LAMBS installieren
GITHUB_USER=<dein-user> bash install.sh

# 3. Stack befüllen
python3 ~/.nanobot/scripts/memory_write_current.py agent_port 3000
python3 ~/.nanobot/scripts/memory_write_current.py vps_provider hetzner
# ... weitere Keys aus CURRENT/stack.md

# 4. Smoke-Tests
python3 ~/.nanobot/scripts/memory_search.py "nanobot" --top 3
~/.nanobot/scripts/memory_commit_push.sh
```

---

## Architektur

```
Schicht 1 — Scratchpad:    HISTORY.md          (agent schreibt live)
Schicht 2 — Kanonisch:     memory_repo/         (git, versioniert)
Schicht 3 — Retrieval:     memory_search.py     (grep → Phase 6: sqlite-vec)
Schicht 4 — Evolution:     pattern_counter.py   (Cluster → Proposals)
Schicht 5 — Sicherheit:    input_sanitizer.py   (PII + Injection-Guard)
```

### Verzeichnisstruktur des Memory-Repos

```
memory_repo/
├── CURRENT/          # Aktueller Wahrheitszustand (layer_weight: 4.0)
│   ├── stack.md      # Ports, Container, Config — einzige Quelle der Wahrheit
│   ├── rules.md      # Verhaltensregeln, Policies
│   └── injection_patterns.json  # readonly (chmod 444)
├── DECISIONS/        # Architecture Decision Records (layer_weight: 3.0)
├── RUNBOOKS/         # Ausführbare Checklisten (layer_weight: 3.0)
├── UPCOMING/         # Datierte Reminder (layer_weight: 2.0)
├── DAILY/            # Konsolidierte Tageseinträge (layer_weight: 1.0)
├── PROPOSALS/        # Auto-generierte Runbook-Vorschläge (layer_weight: 0.5)
├── ARCHIVE/          # Archivierte Proposals + erledigte Upcomings
├── QUARANTINE/       # LLM-Outputs die Validation nicht bestanden (kein Commit)
└── INDEX.md          # Schnellnavigation
```

---
## Docs
- Architecture: docs/architecture.md
- Security model: docs/security.md
- Ops & Cron: docs/ops-cron.md
- Nanobot dependency + LLM bridge contract: docs/nanobot.md
- Phase 6 (semantic / sqlite-vec): docs/phase6-semantic.md
- Changelog: CHANGELOG.md

## Development
CI runs on PRs (pytest + shellcheck + ruff on tests).
