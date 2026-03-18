# Ops & Cron

This file documents how LAMBS runs in production.

## Cron overview

Typical schedule (example):

- 4×/day: `memory_commit_push.sh` (batch sync)
- nightly: `daily_consolidate.py` → `pattern_counter.py` → `alerts_generator.py`
- weekly: `memory_gc.py`

Idempotent installation is handled by `scripts/install_cron.sh`.

## Batch sync contract

`memory_commit_push.sh`:
- acquires a lock (single-writer policy)
- `git pull --ff-only`
- `git add -A && git commit ...` if needed
- `git push`

## nanobot dependency

LAMBS assumes a working **nanobot** installation (or compatible agent runtime) on the host.

Details: see `docs/nanobot.md`.

### LLM bridge

Scripts that require an LLM call do **not** use `OPENAI_API_KEY` directly. Instead they call:

- `scripts/llm_call.sh`

Contract (summary):
- prompt in, text out (stdout)
- non-zero exit code on failure
- bounded runtime (timeout)

If the bridge fails, callers should fall back to template mode or quarantine output.

## Logs

Logs are written to `~/.nanobot/logs/`.
If something fails “silently”, start by checking:

- `sync.log`
- `consolidate.log`
- `pattern.log`
- `alerts.log`
- `gc.log`
