# Zweisprachig Teil B: Assistent – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der Assistent antwortet in der Sprache der Anfrage (`lang` aus der Chat-API, Standard `de`): Modellantworten, feste Sätze, Rückfragen, „Verstanden: …“, Abweichungstexte, Mehrtages- und Wetter-Notizen, Fehlermeldungen; die Zahlenprüfung versteht englische Zahlen; Merkmale haben englische Labels und Synonyme.

**Architecture:** `lang` fließt je Nachricht von `ChatRequest` über `run_chat(..., lang=)` in die LangGraph-Konfiguration (`configurable["lang"]`) und den Turn-State. Feste Texte liegen in `agent/texts.py` als `TEXTS: dict[Lang, Texts]` (eine dataclass je Sprache mit denselben Feldern); die deutschen Werte sind die heutigen Konstanten (unverändert, damit alle deutschen Tests gültig bleiben). Zahlen in Code-Sätzen über `numfmt.fmt(x, lang, decimals)`.

**Tech Stack:** Python, FastAPI, LangGraph, pytest; Web (Vitest) nur für die Anzeige englischer Backend-Texte.

**Spec:** `docs/superpowers/specs/2026-11-02-zweisprachig-design.md` (Entscheidungen 8–14).

**Branch:** `zweisprachig-b` von `main` nach dem Merge von Teil A.

## Global Constraints

- `Lang = Literal["en", "de"]`; ohne `lang` gilt `de` (API, `run_chat`, alle Helfer). Alle bestehenden deutschen Tests bleiben unverändert grün.
- Englisch: britisches Englisch, gleiche Fakten und Struktur wie Deutsch; Zahlen „11.6 km“, „1,200 m“, Uhrzeit „09:30“; Einheiten km, m (ascent/descent), h.
- Das Modell bekommt die Sprache als Anweisung im System-Prompt („Answer in English …“ / „Antworte auf Deutsch …“); die Daten an das Modell (`_search_data`, `_plan_data`) sind in der Sprache der Antwort formuliert.
- Code entscheidet und prüft, das Modell formuliert – auch auf Englisch; die Zahlenprüfung läuft in beiden Sprachen.
- Eingaben in beiden Sprachen werden verstanden, unabhängig von `lang`.
- Wissensquellen bleiben deutsch; englische Antworten nennen deutsche Quellentitel im Original.

## Review Focus

1. **Englische Antwort mit Zahlen** („The Feldbergsteig is 12.3 km long with 540 m of ascent.“) – die Zahlenprüfung erkennt die Zahlen als belegt, ersetzt nichts. Test in Task 4.
2. **Gemischte Sprache im Verlauf** – erste Nachricht `de`, Verfeinerung „shorter“ mit `en` → Antwort Englisch, Anfrage korrekt verfeinert. Test in Task 2.
3. **Englische Eingabe mit Zahlwörtern** („a round walk of about ten kilometres“, „two hours“) – die verstandene Anfrage behält die Werte (kein Verwerfen als „vom Modell erfunden“). Test in Task 4.
4. **Rückfrage auf Englisch und Antwort per Klick** – Option kommt als Ortsname zurück und wird aufgelöst wie heute. Test in Task 3.
5. **Fehler- und Grenztexte** (Rate-Limit, Budget, Dienst nicht erreichbar) auf Englisch. Test in Task 2.

---

### Task 1: `lang` durch API und Graph, Text-Modul, Zahlenformat

**Files:** Create `backend/src/hikeall/agent/texts.py`; Modify `api/chat.py` (an `run_chat` weitergeben), `agent/graph.py` (`run_chat(..., lang="de")`, `configurable["lang"]`, `State.lang` je Turn), `numfmt.py` (`fmt(x: float, lang: Lang, decimals: int = 1) -> str`, `de()` bleibt als Alias); Tests `test_texts.py`, `test_numfmt.py`, `test_api_chat.py`, `test_agent_graph.py`.
- `texts.py`: `@dataclass(frozen=True) class Texts` mit allen festen Sätzen aus `agent/prompts.py` (Antworten, Hinweise, Gruppen/Events, Fehler, Tool-Texte; System-Prompts bleiben in prompts.py, bekommen aber einen Sprach-Satz), `TEXTS = {"de": Texts(...heutige Werte...), "en": Texts(...)}`, `texts(lang) -> Texts`. `prompts.py` re-exportiert die deutschen Werte unter den alten Namen (kein Test bricht).
- [ ] Tests: `fmt(11.6,"en")=="11.6"`, `fmt(1200,"en",0)=="1,200"`, `fmt(11.6,"de")=="11,6"`; jedes `Texts`-Feld ist in `en` und `de` nicht leer und `en != de` (Ausnahmen explizit gelistet); API gibt `lang` an `run_chat` weiter; Graph mit `lang="en"` antwortet bei `other`-Intent mit `texts("en").other_reply`.
- [ ] Implement; `uv run pytest -q` – PASS; Commit `feat: Sprache der Anfrage im Assistenten`

### Task 2: Feste Sätze und Modell-Antworten in der Sprache

**Files:** `agent/graph.py` (alle Stellen, die prompts-Konstanten oder Inline-Deutsch nutzen: guard/reply/clarify/search/groups/events/multiday/react/answer/ground), `agent/prompts.py` (System-Prompts: Sprachanweisung je `lang`; `_search_data`/`_plan_data`-Beschriftungen je Sprache), `api/chat.py` (Rate-Limit-, Fehlertexte nach `lang`), `guard.py` (Antworttexte), Tests.
- [ ] Tests (Fake-Gateway): Feldberg-Flow mit `lang="en"` → Antwort-Prompt enthält „English“, Ausweich-Satz und `NO_TOURS_HINT` englisch; Verfeinerung „shorter“ in `en` nach deutscher Erstnachricht; Rate-Limit-Text englisch; Budget-/Unavailable-Fehler englisch; alle bestehenden Tests unverändert grün.
- [ ] Implement; Run – PASS; Commit `feat: feste Sätze und Antworten auf Englisch`

### Task 3: Verstanden, Rückfragen, Abweichungen

**Files:** `agent/understand.py` (`echo(req, vocab, lang)`, Rückfragen, `_KIND_NAMES`, `_join_or`, `DAYS_QUESTION` je Sprache), `agent/constraints.py` (`_LABEL`, `format_deviation(r, lang)`, `_reason(..., lang)`, Bound-Text `_range(k, lang)` – `check(..., lang)` / `select(..., lang)`), `agent/explain.py` (Notiz in der Sprache), `agent/tools.py` (`search_day_hikes(req, lang)` falls nötig), `tags/vocabulary.py` (Label je Sprache für Echo), Tests.
- [ ] Tests: `echo` englisch („Understood: round walk near Feldberg-Ort · length 8.5–11.5 km · max. 300 m ascent“); Rückfrage „Did you mean „Feldberg (village)“, …?“ mit Optionen = Ortsnamen; Klick auf Option löst auf; `format_deviation` englisch („11.6 km instead of at most 11.5 km“, „not a round walk“); Ausweich-Satz englisch („No tour meets all your wishes because …“); Knapp-daneben-Satz englisch („Near miss: …“).
- [ ] Implement; Run – PASS; Commit `feat: Verstanden, Rückfragen und Abweichungen auf Englisch`

### Task 4: Englische Zahlen prüfen und verstehen, Merkmale englisch

**Files:** `agent/grounding.py` (Zahlen mit Punkt-Dezimal und Komma-Tausender, englische Einheiten- und Zahlwörter, „to“/„and“ für Bereiche – aktiv bei `lang="en"`), `agent/understand.py` (`_written`/`_scan` erkennen englische Zahlwörter one…twelve, „half an hour“, „hours“, englische Monatsnamen und Datumsformen), `agent/events.py` (englische Monatsnamen), `data/tags/features.yaml` (`label_en`, `synonyms_en`), `tags/vocabulary.py` (Suche über beide Synonymlisten, `label(tag_id, lang)`), Tests.
- [ ] Tests: Grounding `lang="en"`: „12.3 km“ und „1,200 m“ belegt, „15.0 km“ unbelegt → „?“; deutsche Grounding-Tests unverändert; understand: „a round walk of about ten kilometres near Titisee“ → Länge ~10 behalten; „two hours“ → Dauer 2 h behalten; „on 12 March“ → Datum; Vokabular: „inn“ → `feature:einkehr`, „viewpoint“ → `feature:aussicht`; `label("feature:einkehr","en")` englisch.
- [ ] Implement; Run – PASS; Commit `feat: englische Zahlen und Merkmale`

### Task 5: Mehrtages-, Wetter-, Gruppen- und Event-Texte

**Files:** `agent/multiday.py` (Notizen, `gap`, `RAIN_NOTE`, `_fmt` mit `lang`), `agent/weather.py`, `adapters/open_meteo.py` (`weather_text(code, lang)`), `agent/events.py`, `api/admin.py` nur falls Texte an Nutzer gehen (sonst unverändert, Spec 15), Tests.
- [ ] Tests: Mehrtagesplan `lang="en"` → Notizen/Lücken/Regenvariante englisch, Zahlen englisch; Wettertext englisch („light rain“); Gruppen- und Event-Antworttexte englisch.
- [ ] Implement; Run – PASS; Commit `feat: Mehrtages-, Wetter-, Gruppen- und Event-Texte auf Englisch`

### Task 6: Smoke, Prüfung, README

- [ ] `data/smoke/prompts.yaml`: drei englische Anfragen mit `lang: en` („A round walk near Titisee, about 10 km“, „3 days on the Westweg from Hausach“, „What does the Schwarzwaldverein do?“), Smoke-Code schickt `lang` mit; Smoke laufen lassen (`make smoke`, wenige Cent), Ergebnis festhalten.
- [ ] Live: API + Web starten, auf Englisch eine Suche, eine Rückfrage, einen Mehrtagesplan durchspielen (Playwright-Screenshots wie in Teil A), auf Deutsch dieselbe Suche – keine Mischsprache außer Eigennamen und deutschen Quellentiteln.
- [ ] README: Sprache ergänzen (Teil B fertig). Commit `docs: Assistent zweisprachig`
