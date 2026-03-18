# Nanobot dependency

LAMBS is a **memory kit** designed to be used with a nanobot-style agent runtime.

This repository does *not* ship nanobot itself.

## What LAMBS expects

### 1) A working agent runtime

LAMBS assumes you have an agent that:
- writes an append-only event log (`HISTORY.md` or similar)
- can be instructed via a workspace skill (e.g. `skills/memory-github/SKILL.md`)

### 2) LLM bridge command

Some scripts optionally require an LLM call (daily consolidation, proposal generation, health alerts).
To avoid managing extra API keys on the host, LAMBS delegates those calls to the agent runtime via:

- `scripts/llm_call.sh`

#### Contract

`llm_call.sh` must:
- accept a prompt as argument 1
- optionally accept a max_tokens argument 2
- print the model output to **stdout**
- return **exit code 0** on success
- return **non-zero** on failure
- not hang forever (must enforce a timeout internally, or be called under `timeout`)

If the bridge is unavailable, callers should:
- fall back to template mode, or
- quarantine the output (never auto-commit suspicious output)

## Where to document your concrete nanobot integration

If you are using a specific nanobot implementation (CLI flags / container name / HTTP endpoint), document it in your canonical memory repo under:

- `CURRENT/stack.md` (runtime facts)
- `RUNBOOKS/` (operational procedures)
