# Architecture (LAMBS)

LAMBS = **L**ayered · **A**ppend-first · **M**arkdown · **B**atched-sync · **S**kill-evolution.

Goal: give a nanobot-style agent long-term memory that **doesn’t flood prompt context**, stays **auditable**, and remains **cheap**.

## Layers

1. **Scratchpad (nanobot-native)**
   - `~/.nanobot/workspace/memory/HISTORY.md` (append-only event log)
   - `~/.nanobot/workspace/memory/YYYY-MM-DD.md` (daily scratch)

2. **Canonical memory (Git repo, source of truth)**
   - A separate Git repository (e.g. `agent-memory`) containing Markdown:
     - `CURRENT/` (small, up-to-date state)
     - `DECISIONS/` (ADRs)
     - `RUNBOOKS/` (procedures)
     - `DAILY/` (consolidated daily logs)
     - `PROPOSALS/` (auto-generated suggestions)
     - `UPCOMING/` (dated reminders)

3. **Retrieval (no context flood)**
   - Local `MEMORY.md` becomes a **stub** pointing to tools.
   - `memory_search.py` returns **top-k snippets** with a hard budget.

4. **Skill evolution (self-learning, controlled)**
   - `pattern_counter.py` generates **proposals**, not auto-edits to RUNBOOKS.
   - Human approves via `approve_proposal.sh`.

5. **Safety / integrity**
   - `input_sanitizer.py` blocks PII & injection-style content.
   - suspicious LLM outputs go to `QUARANTINE/`.

## Canonical repo layout

```text
memory_repo/
├── CURRENT/          # current truth (keep small)
│   ├── stack.md
│   ├── rules.md
│   └── injection_patterns.json
├── DECISIONS/
├── RUNBOOKS/
├── UPCOMING/
├── DAILY/
├── PROPOSALS/
├── ARCHIVE/
├── QUARANTINE/
└── INDEX.md
```

### Why Git?

- Diffable & auditable changes
- Cheap backups (remote + local)
- No vendor lock-in

### Why a MEMORY.md stub?

Many agent frameworks inject a single `MEMORY.md` into the system prompt. If that file grows, prompts eventually blow up.
LAMBS keeps the injected file tiny and uses **targeted retrieval** instead.
