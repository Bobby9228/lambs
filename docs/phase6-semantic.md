# Phase 6: Semantic retrieval (optional)

Phase 1–5 are intentionally **ML-free** and rely on `grep` for speed and simplicity.

Phase 6 adds optional semantic search (e.g. sqlite-vec + MiniLM embeddings) to improve recall when:
- queries are semantically related but lexically different
- the repo grows large and keyword search becomes insufficient

## Design goals

- Keep Phase 1–5 working without extra dependencies.
- Make semantic indexing opt-in via feature flag.
- Index updates must be incremental and safe.

## Status

Phase 6 is implemented.

## How it works

- When `LAMBS_SEMANTIC_ENABLED=1`, `memory_search.py` can build and query a semantic index.
- The index is stored at: `~/.nanobot/workspace/memory_repo/.lambs/semantic.sqlite3`
- Backend: `sqlite-vec` virtual table (`vec0`) + embeddings from `sentence-transformers`.

## Commands

```bash
# Build/update index for all markdown files
python3 ~/.nanobot/scripts/memory_search.py --reindex

# Reindex a single file
python3 ~/.nanobot/scripts/memory_search.py --reindex-file CURRENT/stack.md
```

## Retrieval behavior

- Default: grep search (Phase 1–5 behavior)
- If semantic is enabled and an index exists: results are augmented with semantic hits (hybrid mode).

## Notes

- Semantic dependencies are optional; if missing, LAMBS falls back to grep.
- Avoid indexing secrets: do not store tokens/keys in the memory repo.
