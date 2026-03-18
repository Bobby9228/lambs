#!/usr/bin/env python3
"""
LAMBS Input Sanitizer — Sicherheitsschicht vor allen Memory-Writes.

Zweck:
  Verhindert dass schädliche Inhalte (PII, Prompt-Injektionen, Secrets)
  ins kanonische Memory-Repo geschrieben werden. Wird intern von allen
  memory_write_*.py Scripts importiert — kein direkter Aufruf nötig.

Design-Entscheidungen:
  - Interner Import statt externem Aufruf: verhindert Bypass durch
    direkten Script-Aufruf ohne Sanitizer.
  - Zwei-Stufen-Prüfung: Regex für strukturierte Muster (API-Keys, PIIs),
    Pattern-Liste für semantische Injection-Versuche.
  - injection_patterns.json ist readonly (chmod 444) und liegt im Repo:
    auditierbar, versioniert, aber nie automatisch beschrieben.

Raises:
  SanitizationError: bei Verletzung einer Prüfregel. Der aufrufende
  Write-Script fängt die Exception und bricht den Write ab.
"""
# WICHTIG: Dieses Modul wird importiert, nicht direkt aufgerufen.
# Alle memory_write_*.py führen: from input_sanitizer import sanitize_or_raise
import re, json
from pathlib import Path

PATTERNS_FILE = Path.home() / ".nanobot/workspace/memory_repo/CURRENT/injection_patterns.json"

_INJECTION_PATTERNS: list[str] = []

def _load_patterns():
    global _INJECTION_PATTERNS
    if PATTERNS_FILE.exists():
        _INJECTION_PATTERNS = json.loads(PATTERNS_FILE.read_text())

_load_patterns()

PII_REGEXES = [
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",  # E-Mail
    # Telefon: mindestens 3 Segmente, kein reines Port-Pattern (keine einzelnen 4-5-stelligen Zahlen)
    # Ausschluss: "3000:3000" (Docker-Ports), "3000 8080" (zwei Ports nebeneinander)
    r"(?<!\d)(?<!\:)\b\d{3,4}[\s\-]\d{3,4}[\s\-]\d{4,6}\b(?!\:)(?!\d)",  # Telefon 3-teilig mit Trenner
    r"\b(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{30,}|Bearer [a-zA-Z0-9\-._~+/]{20,})\b",  # API-Keys
]

class SanitizationError(Exception):
    pass

def sanitize_or_raise(text: str, source: str = "agent") -> str:
    """
    Prüft Text auf PII, Injection-Patterns und Größe. Raises bei Verstoß.

    Prüf-Reihenfolge:
        1. Größen-Check: >2048 Bytes → verdächtig, legitime Writes sind kurz
        2. PII-Regex: E-Mail, Telefon, API-Key-Muster (sk-*, ghp_*, Bearer)
        3. Pattern-Liste: bekannte Injection-Formulierungen aus
           injection_patterns.json (readonly, manuell gepflegt)
        4. Cosine-Check: Platzhalter für Phase 6 (MiniLM-Embedding)

    Args:
        text:   Der zu prüfende Inhalt (Key+Value oder freier Text)
        source: Herkunft des Writes für Logging ("agent"/"cron"/"manual")

    Returns:
        Den unveränderten Text wenn alle Checks bestanden wurden.

    Raises:
        SanitizationError: mit Beschreibung des verletzten Checks.
    """

    if len(text.encode()) > 2048:
        raise SanitizationError(f"Write zu groß: {len(text.encode())} bytes (max 2048)")

    for pattern in PII_REGEXES:
        if re.search(pattern, text):
            raise SanitizationError(f"PII erkannt in Write-Versuch: {pattern[:30]}...")

    text_lower = text.lower()
    for p in _INJECTION_PATTERNS:
        if p.lower() in text_lower:
            raise SanitizationError(f"Injection-Pattern erkannt: {p!r}")

    # Cosine-Check gegen Injection-Vektoren (Phase 6: MiniLM verfügbar)
    # Hier als Platzhalter — wird in Phase 6 aktiviert

    return text  # sauber
