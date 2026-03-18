# Phase 6: Semantic retrieval (optional)

Phase 1–5 are intentionally **ML-free** and rely on `grep` for speed and simplicity.

Phase 6 adds optional semantic search (e.g. sqlite-vec + MiniLM embeddings) to improve recall when:
- queries are semantically related but lexically different
- the repo grows large and keyword search becomes insufficient

## Design goals

- Keep Phase 1–5 working without extra dependencies.
- Make semantic indexing opt-in via feature flag.
- Index updates must be incremental and safe.

## Not implemented yet

The repository contains stubs/flags for Phase 6, but the vector index implementation is intentionally deferred until there is a measured need.
