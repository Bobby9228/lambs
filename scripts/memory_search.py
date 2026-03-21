#!/usr/bin/env python3
"""
LAMBS Memory Search — grep-basiertes Retrieval mit Layer-Scoring und Salienz.

Zweck:
  Durchsucht das kanonische Memory-Repo und gibt Top-K relevante Snippets zurück.
  Wird vom nanobot-Agent via SKILL.md aufgerufen, damit der Agent nur benötigte
  Informationen erhält statt die gesamte MEMORY.md injiziert zu bekommen.
  Kernstück von Schicht 3 (Retrieval) in der LAMBS-Architektur.

Scoring-Logik (höher = wichtiger):
  CURRENT 4.0 > DECISIONS/RUNBOOKS 3.0 > UPCOMING 2.0 > DAILY 1.0 > PROPOSALS 0.5
  Salience-Bonus: #critical/PREVENT-Inhalte werden zusätzlich höher gewichtet.

Seiteneffekte:
  Schreibt jede Suchanfrage in memory_search.log für Co-Occurrence-Tracking.
  Das Log wird von pattern_counter.py täglich ausgewertet.

Phase 6 Upgrade:
  Optionaler Semantic-Index via sqlite-vec + sentence-transformers.
  Aktiviert über LAMBS_SEMANTIC_ENABLED=1.

Aufruf:
  memory_search.py "deploy failed" --top 8
  memory_search.py "nanobot port" --top 3 --grep-only
  memory_search.py "restart" --top 5 --expand-hops 2
  memory_search.py --reindex
  memory_search.py --reindex-file CURRENT/stack.md
"""
import argparse, subprocess, sys, os, json
from datetime import datetime
from pathlib import Path

from flags import load_flags

REPO = Path.home() / ".nanobot/workspace/memory_repo"
LOG  = Path.home() / ".nanobot/memory_search.log"

# Schicht-Gewichte: steuern das Ranking wenn mehrere Schichten denselben Begriff enthalten.
# CURRENT hat das höchste Gewicht — enthält immer den aktuellen Wahrheitszustand.
# DAILY hat das niedrigste — historische Events können veraltet sein.
# Wird multipliziert mit salience_weight für den finalen Snippet-Score.
LAYER_WEIGHTS = {
    "CURRENT":   4.0,  # Aktuelle Konfiguration, Regeln
    "DECISIONS": 3.0,  # Architecture Decision Records
    "RUNBOOKS":  3.0,  # Ausführbare Checklisten
    "DAILY":     1.0,  # Historische Tageseinträge (können veraltet sein)
    "PROPOSALS": 0.5,  # Noch nicht genehmigte Vorschläge
    "UPCOMING":  2.0,  # Prospektive Reminder
}

def layer_weight(filepath: str) -> float:
    """
    Bestimmt das Ranking-Gewicht anhand des Schicht-Ordners im Pfad.

    Args:
        filepath: Relativer Pfad ab REPO-Root, z.B. "CURRENT/stack.md"

    Returns:
        Gewicht als float. Unbekannte Pfade erhalten 1.0 (Standardwert).
    """
    for layer, w in LAYER_WEIGHTS.items():
        if f"/{layer}/" in filepath or filepath.startswith(layer):
            return w
    return 1.0

def grep_search(query: str, top: int) -> list[dict]:
    """
    Durchsucht das Memory-Repo case-insensitiv via grep.

    Parst das grep-Format "datei:zeile:text", berechnet Layer-Gewichte und
    begrenzt auf max. 2 Treffer pro Datei (Dedup), damit keine einzelne
    Datei alle Top-K Slots belegt.

    Args:
        query: Suchbegriff (direkt an grep übergeben, keine Regex-Transformation)
        top:   Maximale Anzahl zurückzugebender Treffer

    Returns:
        Liste von Dicts mit filepath, lineno, text, layer_weight.
        Leer wenn grep nicht gefunden oder keine Treffer.
    """
    try:
        result = subprocess.run(
            ["grep", "-RIn", "--include=*.md", "-e", query, str(REPO)],
            capture_output=True, text=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    hits = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        filepath, lineno, text = parts
        rel = filepath.replace(str(REPO) + "/", "")
        hits.append({
            "filepath": rel,
            "lineno": int(lineno),
            "text": text.strip(),
            "layer_weight": layer_weight(rel),
        })

    # Score = layer_weight (grep hat kein Ähnlichkeits-Score)
    hits.sort(key=lambda h: h["layer_weight"], reverse=True)

    # Dedup: max 2 Snippets pro Datei
    seen: dict[str, int] = {}
    deduped = []
    for h in hits:
        count = seen.get(h["filepath"], 0)
        if count < 2:
            deduped.append(h)
            seen[h["filepath"]] = count + 1

    return deduped[:top]

def extract_snippet(filepath: str, lineno: int, context: int = 10) -> str:
    """
    Extrahiert ±context Zeilen um eine Treffer-Zeile aus einer Datei.

    Fehlerhafte UTF-8-Bytes werden ersetzt statt eine Exception zu werfen,
    damit beschädigte Dateien den Retrieval-Flow nicht unterbrechen.

    Args:
        filepath: Relativer Pfad ab REPO-Root
        lineno:   Zeilennummer des grep-Treffers (1-basiert)
        context:  Anzahl Zeilen Kontext vor und nach dem Treffer

    Returns:
        Zusammengefügter Snippet-String, leer wenn Datei nicht existiert.
    """
    full = REPO / filepath
    if not full.exists():
        return ""
    lines = full.read_text(errors="replace").splitlines()
    start = max(0, lineno - context - 1)
    end   = min(len(lines), lineno + context)
    snippet_lines = lines[start:end]
    return "\n".join(snippet_lines)

def detect_salience(snippet: str) -> float:
    """
    Berechnet den Salienz-Multiplikator für einen Snippet.

    Implementiert das kognitionswissenschaftliche "Amygdala-Prinzip":
    kritische Inhalte werden stärker gewichtet und erscheinen bevorzugt
    in den Top-K Ergebnissen. Komplementär zu layer_weight.

    Stufen:
        1.5 → #critical oder #wichtig Tag
        1.3 → PREVENT:-Zeile (Guardrail aus Fehlererfahrung)
        1.0 → Standard, keine besondere Markierung

    Args:
        snippet: Extrahierter Textausschnitt

    Returns:
        Multiplikator für den finalen Ranking-Score.
    """
    text = snippet.lower()
    if "#critical" in text or "#wichtig" in text:
        return 1.5
    if "prevent:" in text:
        return 1.3
    return 1.0

def log_search(query: str, result_files: list[str]):
    """
    Schreibt Suchanfrage und Top-3 Ergebnis-Dateien ins Search-Log.

    Das Log dient als Datenquelle für das Co-Occurrence-Tracking in
    pattern_counter.py: Queries die zeitlich aufeinander folgen gelten
    als assoziiert, ihre Ziel-Dateien werden als "verwandt" markiert.

    Format: "YYYY-MM-DD HH:MM <query> → <filepath>"

    Args:
        query:        Die Suchanfrage
        result_files: Gefundene Dateipfade (nur Top-3 werden geloggt)
    """
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    for f in result_files[:3]:
        with LOG.open("a") as fh:
            fh.write(f"{ts} {query} → {f}\n")

def _try_semantic_deps():
    """Lazy import semantic deps. Returns (ok, errstr, modules)."""
    try:
        import sqlite3  # noqa: F401
        import sqlite_vec  # type: ignore
        import numpy as np  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore
        return True, "", (sqlite3, sqlite_vec, np, SentenceTransformer)
    except Exception as e:  # pragma: no cover
        return False, str(e), None


def _semantic_db_path() -> Path:
    return REPO / ".lambs" / "semantic.sqlite3"


def _semantic_model_name() -> str:
    # Keep it small + widely available.
    return os.environ.get("LAMBS_SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def _semantic_embed(text: str, SentenceTransformer):
    model = SentenceTransformer(_semantic_model_name())
    # normalize_embeddings => cosine similarity via L2 distance
    emb = model.encode([text], normalize_embeddings=True)
    return emb[0]


def semantic_reindex(paths: list[Path] | None = None) -> int:
    """(Phase 6) Build/update semantic index. Returns number of indexed docs."""
    flags = load_flags()
    if not flags.semantic:
        print("[memory_search] semantic disabled via LAMBS_SEMANTIC_ENABLED=0")
        return 0

    ok, err, mods = _try_semantic_deps()
    if not ok:
        print(f"[memory_search] semantic deps missing: {err}")
        return 0

    sqlite3, sqlite_vec, np, SentenceTransformer = mods

    db = _semantic_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    cur = conn.cursor()

    cur.execute("""
        create table if not exists docs(
            rowid integer primary key,
            path text unique,
            sha256 text not null,
            updated_at text not null
        )
    """)
    # 384 dims for all-MiniLM-L6-v2
    cur.execute("create virtual table if not exists vec using vec0(embedding float[384])")

    def iter_md_files():
        if paths:
            for p in paths:
                if p.is_file() and p.suffix == ".md":
                    yield p
            return
        for p in REPO.rglob("*.md"):
            if "/.git/" in str(p):
                continue
            if "/QUARANTINE/" in str(p):
                continue
            yield p

    indexed = 0
    for p in iter_md_files():
        rel = str(p.relative_to(REPO))
        txt = p.read_text(errors="replace")
        import hashlib
        sha = hashlib.sha256(txt.encode("utf-8", errors="ignore")).hexdigest()

        row = cur.execute("select rowid, sha256 from docs where path=?", (rel,)).fetchone()
        if row and row[1] == sha:
            continue

        emb = _semantic_embed(txt[:50_000], SentenceTransformer)
        emb_bytes = sqlite_vec.serialize_float32(np.asarray(emb, dtype=np.float32))

        if row:
            rowid = row[0]
            cur.execute("update docs set sha256=?, updated_at=datetime('now') where rowid=?", (sha, rowid))
            cur.execute("delete from vec where rowid=?", (rowid,))
        else:
            cur.execute("insert into docs(path, sha256, updated_at) values (?,?,datetime('now'))", (rel, sha))
            rowid = cur.lastrowid

        cur.execute("insert into vec(rowid, embedding) values (?,?)", (rowid, emb_bytes))
        indexed += 1

    conn.commit()
    conn.close()
    print(f"[memory_search] semantic reindex ok: {indexed} docs updated")
    return indexed


def semantic_search(query: str, top: int) -> list[dict]:
    flags = load_flags()
    if not flags.semantic:
        return []

    ok, err, mods = _try_semantic_deps()
    if not ok:
        print(f"[memory_search] semantic disabled (deps missing): {err}")
        return []

    sqlite3, sqlite_vec, np, SentenceTransformer = mods
    db = _semantic_db_path()
    if not db.exists():
        return []

    conn = sqlite3.connect(db)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    cur = conn.cursor()

    qemb = _semantic_embed(query, SentenceTransformer)
    qbytes = sqlite_vec.serialize_float32(np.asarray(qemb, dtype=np.float32))

    rows = cur.execute(
        """
        select docs.path, vec.distance
        from vec join docs on docs.rowid = vec.rowid
        where vec.embedding match ? and vec.k = ?
        order by vec.distance
        """,
        (qbytes, top),
    ).fetchall()
    conn.close()

    out = []
    for path, dist in rows:
        out.append({
            "filepath": path,
            "lineno": 1,
            "text": f"semantic distance={dist:.4f}",
            "layer_weight": layer_weight(path),
            "distance": float(dist),
        })
    return out


def main():
    if not load_flags().search:
        print("[memory_search] disabled via LAMBS_SEARCH_ENABLED=0")
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--budget", type=int, default=10000)
    parser.add_argument("--grep-only", action="store_true")
    parser.add_argument("--expand-hops", type=int, default=0,
                        help="(Phase 6, noch nicht aktiv) Graph-Hops für verwandte Snippets")
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--reindex-file", type=str)
    args = parser.parse_args()

    if args.reindex or args.reindex_file:
        if args.reindex_file:
            target = (REPO / args.reindex_file).resolve()
            if not target.exists():
                print(f"[memory_search] reindex-file not found: {args.reindex_file}")
                return
            semantic_reindex([target])
        else:
            semantic_reindex(None)
        return

    if not args.query:
        parser.print_help()
        return

    if args.expand_hops > 0:
        print(f"[memory_search] Hinweis: --expand-hops ist in Phase 1-5 nicht aktiv (Phase 6 Feature).")

    hits = grep_search(args.query, args.top)

    # Phase 6: optionally augment with semantic hits.
    if not args.grep_only:
        sem_hits = semantic_search(args.query, args.top)
        if sem_hits:
            seen = {(h["filepath"], h["lineno"]) for h in hits}
            for h in sem_hits:
                key = (h["filepath"], h["lineno"])
                if key not in seen:
                    hits.append(h)
                    seen.add(key)
            # Keep ordering simple: grep hits first, then semantic additions.
            hits = hits[: args.top]

    output_blocks = []
    total_chars = 0
    result_files = []

    for h in hits:
        snippet = extract_snippet(h["filepath"], h["lineno"])
        salience = detect_salience(snippet)
        block = (
            f"## [{h['filepath']}] "
            f"layer:{h['filepath'].split('/')[0]} "
            f"salience:{salience}\n"
            f"{snippet}\n"
        )
        if total_chars + len(block) > args.budget:
            break
        output_blocks.append(block)
        total_chars += len(block)
        result_files.append(h["filepath"])

    if output_blocks:
        print("\n---\n".join(output_blocks))
        log_search(args.query, result_files)
    else:
        print(f"[memory_search] Keine Treffer für: {args.query!r}")

if __name__ == "__main__":
    main()
