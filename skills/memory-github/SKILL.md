<!-- ~/.nanobot/workspace/skills/memory-github/SKILL.md -->
# Memory Search

Bevor du eine Frage beantwortest die Wissen über das Setup, Entscheidungen
oder vergangene Events erfordert:

1. exec: python3 ~/.nanobot/scripts/memory_search.py "<deine_query>" --top 8
2. Nutze die zurückgegebenen Snippets als Kontext
3. Für heutige Ereignisse zusätzlich:
   grep -i "<query>" ~/.nanobot/workspace/memory/HISTORY.md | tail -20

Falls das erste Ergebnis unvollständig wirkt:
4. Folgeanfrage: memory_search.py "<spezifischere_query>" --top 5
   → Multi-Hop: bis zu 3 Suchschritte, dann antworten

Bei Fehlern oder Problemen:
5. exec: cat ~/.nanobot/workspace/ALERTS.md

Rekonsolidierung — Gedächtnis beim Abruf aktualisieren:
6. Wenn ein Snippet veraltet oder falsch erscheint:
   exec python3 ~/.nanobot/scripts/memory_write_current.py "<key>" "<wert>"
   Nur bei sicherem Widerspruch — niemals spekulativ.

Schreiben:
- Neue dauerhafte Fakten:
  exec python3 ~/.nanobot/scripts/memory_write_current.py "<key>" "<value>"
- Entscheidungen mit Tradeoffs:
  exec python3 ~/.nanobot/scripts/memory_write_adr.py "<titel>"
- Zukünftige Reminder:
  exec python3 ~/.nanobot/scripts/memory_write_upcoming.py "<YYYY-MM-DD>" "<aufgabe>"

Schreibe NICHT bei:
- Temporären Werten oder Zwischenergebnissen
- Unverifizierten Behauptungen
- Fragen oder Hypothesen
- Werten die sich in dieser Session noch ändern können
