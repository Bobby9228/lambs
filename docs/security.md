# Security model

LAMBS is designed to avoid persistent prompt injection / memory poisoning.

## 1) Input sanitization (writes)

All `memory_write_*.py` scripts import `input_sanitizer.py`.

What it blocks:
- Oversized writes (default max 2KB)
- PII-like patterns (e-mail, phone-ish patterns)
- API key/token patterns (e.g. `sk-…`, `ghp_…`, `Bearer …`)
- Injection patterns from `CURRENT/injection_patterns.json`

## 2) Read-only injection patterns

`CURRENT/injection_patterns.json` is intended to be **manual-edit only** and can be set read-only (`chmod 444`).
This prevents tools from accidentally weakening the guardrails.

## 3) Output validation & quarantine (LLM outputs)

Some scripts call an LLM via `llm_call.sh`.
Before committing results into the canonical repo, LAMBS performs basic output validation.

If validation fails, outputs are stored in:
- `memory_repo/QUARANTINE/`

…instead of being committed.

## 4) Atomic writes + locks

`memory_write_current.py` uses:
- `flock` to avoid concurrent writes
- temp file + `os.replace()` for atomic updates

## 5) Principle of least autonomy

Runbooks are not edited automatically in the critical path.
LAMBS produces proposals and requires human approval for promotion into `RUNBOOKS/`.
