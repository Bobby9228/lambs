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
  --reindex und --reindex-file sind als Platzhalter implementiert.
  Volle sqlite-vec Hybrid-Suche wird in Phase 6 aktiviert.

Aufruf:
  memory_search.py "deploy failed" --top 8
  memory_search.py "nanobot port" --top 3 --grep-only
  memory_search.py "restart" --top 5 --expand-hops 2
  memory_search.py --reindex          (Phase 6)
  memory_search.py --reindex-file CURRENT/stack.md  (Phase 6)
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
        print("[memory_search] reindex: Phase 6 — sqlite-vec noch nicht aktiv")
        return

    if not args.query:
        parser.print_help()
        return

    if args.expand_hops > 0:
        print(f"[memory_search] Hinweis: --expand-hops ist in Phase 1-5 nicht aktiv (Phase 6 Feature).")

    hits = grep_search(args.query, args.top)

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
