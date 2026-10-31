# Plan 4 – Mittel-/Ostweg, Evaluation, README, Showcase, Präsentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mittelweg und Ostweg sind wie der Westweg planbar („3 Tage Ostweg ab Freudenstadt“); ein fester Testsatz mit 40–60 Fällen läuft per `make eval` gegen das echte Modell und liefert Zahlen zu den SMART-Zielen aus Spec §9; README, Showcase und Präsentation erfüllen die Capstone-Kriterien (Spec §2 Ziel 9).

**Architecture:** Mittel-/Ostweg sind reine Daten (`data/curated/trails.yaml`) plus Vokabular-Einträge; Import, Mehrtagesplanung und Karte sind schon generisch über `trails.kind = 'long_distance'`. Die Evaluation baut auf dem Smoke-Runner auf (`hikeall/smoke.py`: `load_cases`, `check`, `run_all`) und ergänzt Erwartungsarten, feste Wetterdaten, Kennzahlen und einen Markdown-Bericht in einem neuen Modul `hikeall/evaluation.py`. README/Präsentation sind Texte aus den echten Zahlen.

**Tech Stack:** wie Plan 3 (Python 3.12, uv, pytest, LangGraph, Supabase/PostGIS, Next.js/vitest). Keine neuen Abhängigkeiten.

**Spec:** `docs/superpowers/specs/2026-10-28-hike-all-about-design.md` (§2 Ziele 1, 5, 9; §4; §7 Fernwege; §8 Grounding Schritt 6; §9 Evaluation; §11 Ethik; §12 Woche 4). Vorgänger: `docs/superpowers/plans/2026-10-29-plan-03-mehrtagestour-konten-unterwegs.md` („Folgeplan: … inkl. volle Namensprüfung, Eingabeschutz-Grenzfälle“).

**Bewusste Schnitte [Claude, beim Review änderbar]:**
- **Englisch entfällt** (Spec §12: fällt zuerst weg).
- **Modellvergleich (Spec §9 „Fall 7“) ist Task 7 und optional**; er läuft nur, wenn Tasks 1–6 fertig sind.
- **Abgleich mit OSM** vergleicht Antwort (Karte/Plan) ↔ Datenbankwert ↔ aus der gespeicherten OSM-Linie neu gerechnete Länge. Höhenmeter nur Antwort ↔ Datenbank (OSM-Relationen haben selten einen Hm-Wert).
- **Schaffhausen (Ostweg-Ende) und Waldshut-Umgebung auf Schweizer Seite**: wie Basel außerhalb des BW-Extrakts → Unterkünfte/Haltestellen dort fehlen; als bekannte Lücke im README, nicht gelöst.

## Global Constraints

- Alle Regeln aus Plan 2/3 gelten weiter: keine erfundenen Zahlen/Routen, nie still lockern, Grounding, Limits (0,05 USD und 8 Werkzeugaufrufe je Nachricht), Tests ohne Netz und ohne Kosten, Protokoll ohne Nachrichtentexte.
- Etappendaten: nur Fakten (Ortsnamen, Reihenfolge, offizielle km) von öffentlichen Etappenseiten, **keine Texte kopiert**, Quelle mit `url`, `license`, `retrieved_at` in `trails.yaml` (Spec §7).
- **Erwartungen werden nie gelockert, um einen Fall grün zu machen** (gilt für Smoke und Eval). Ein roter Fall wird untersucht; ist der Code richtig und der Fall falsch formuliert, steht die Begründung als Kommentar am Fall.
- SMART-Ziele (Spec §9) wörtlich: **0 % erfundene Touren, ≤ 2 % nicht belegte Zahlen, 100 % offen benannte Unerfüllbarkeit, Recall@5 ≥ 0,8**.
- Wetterabhängige Eval-Fälle laufen mit gespeicherten Wetterdaten und festem „heute“ (Spec §9), nie live.
- Eval-Ergebnisse unter `docs/evaluation/` (Spec §9); Testsatz unter `data/eval/cases.yaml`.
- Sprache der App und Doku: Deutsch.

## Review Focus

1. **„Ostweg“ vs. „Westweg Ostvariante“:** „3 Tage Ostweg“ muss den Ostweg wählen, „Westweg Ost“ die Westweg-Ostvariante; keine Verwechslung über das Wort „Ost“ (Task 2, Test `test_ostweg_is_not_the_west_variant`).
2. **Startort auf einem Fernweg, der auch an einem anderen liegt** (Pforzheim ist Start aller drei): ohne Fernwegnamen wird nachgefragt, nicht geraten (Task 2, Test `test_pforzheim_without_trail_asks_which_trail`).
3. **Antwort nennt eine Tour, die in den Ergebnissen der Runde nicht vorkommt:** sichtbarer Hinweis und Zählung getrennt von Zahlen, nicht stilles Zählen (Task 3, Test `test_unknown_tour_name_gets_a_hint`).
4. **Eval-Fall, dessen Vorgänger (`continues`) fehlschlägt, oder Fall ohne Quelle bei Wissensfrage:** zählt als nicht bestanden und erscheint im Bericht, Lauf bricht nicht ab; Recall-Nenner zählt ihn mit (Task 4, Test `test_recall_counts_cases_without_sources_as_misses`).
5. **Wetter-Fixture deckt das angefragte Datum nicht ab:** Eval-Lauf meldet „keine Wetterdaten für <Datum>“ als Fehler des Falls statt live abzufragen (Task 4, Test `test_fixture_weather_never_goes_live`).

---

## Dateistruktur (neu oder geändert)

```
data/curated/trails.yaml                 # + mittelweg, ostweg (Relationen, Etappen, Quellen)
data/knowledge/sources.yaml              # + Wikipedia/Wikivoyage Mittelweg, Ostweg
data/eval/cases.yaml                     # Testsatz 40–60 Fälle
data/eval/weather.json                   # gespeicherte Open-Meteo-Tageswerte
backend/src/hikeall/tags/vocabulary.py   # TRAILS + mittelweg, ostweg
backend/src/hikeall/cli.py               # Westweg-Filter → kind = 'long_distance'; Befehl eval
backend/src/hikeall/agent/grounding.py   # Hinweis für nicht belegte Tournamen
backend/src/hikeall/agent/graph.py       # DoneEvent.unsupported_names
backend/src/hikeall/smoke.py             # neue Erwartungsarten in check()
backend/src/hikeall/evaluation.py        # Eval-Runner, Kennzahlen, Bericht, OSM-Abgleich
web/src/lib/chat.ts                      # done-Typ + unsupported_names
web/src/components/HomeStage.tsx, web/src/app/layout.tsx   # Text „Fernwege“ statt nur Westweg
docs/evaluation/                         # results-*.csv, bericht-*.md
docs/showcase/                           # Screenshots
README.md                                # Capstone-README
docs/presentation/                       # Gliederung + Sprechnotizen
Makefile                                 # eval
```

---

### Task 1: Mittelweg und Ostweg importieren

**Files:**
- Modify: `data/curated/trails.yaml`
- Modify: `backend/src/hikeall/cli.py` (`STAGE_COUNT_SQL` ~Z. 239–247, Fotobericht ~Z. 416–422)
- Test: `backend/tests/test_import_trails.py`

**Interfaces:**
- Produces: Trails `mittelweg` (Pforzheim → Waldshut) und `ostweg` (Pforzheim → Schaffhausen), `kind: long_distance`, mit Etappen in `stages`. Tasks 2, 4, 6 nutzen genau diese IDs.

- [ ] **Step 1: Daten erheben.** OSM-Relationen über Overpass suchen (`relation["route"="hiking"]["name"~"Mittelweg|Ostweg"](47.55,7.55,48.95,8.75); out tags;`), die Relationen wählen, die wie beim Westweg die Wege direkt tragen (nicht die Superroute), in Gehrichtung ordnen. Etappeneinteilung (Start, Ziel, offizielle km) von der Etappenseite des Schwarzwaldvereins oder Schwarzwald Tourismus übertragen; Koordinaten der Etappenorte aus OSM Nominatim. Für jede Quelle einen Eintrag unter `sources:` mit `url`, `license: Fakten, keine Texte übernommen`, `retrieved_at: <Abrufdatum>`. `km:` je Etappe setzen. Unsicherheiten als Kommentar oben in der Datei (wie beim Westweg).

- [ ] **Step 2: Failing test** in `test_import_trails.py`:

```python
@pytest.mark.parametrize("tid,start,end", [("mittelweg", "Pforzheim", "Waldshut"), ("ostweg", "Pforzheim", "Schaffhausen")])
def test_curated_trail_chains_its_stages(tid, start, end):
    spec = {t.id: t for t in load_trail_specs(TRAILS_YAML)}[tid]
    assert spec.kind == "long_distance"
    assert spec.stages[0].start.name == start and spec.stages[-1].end.name == end
    for a, b in zip(spec.stages, spec.stages[1:]):
        assert a.end == b.start and b.seq == a.seq + 1
    assert all(s.km for s in spec.stages)
```

(`load_trail_specs` aus `hikeall.ingest.stages`, `TRAILS_YAML` aus `hikeall.cli`; Feldnamen der Etappen wie im vorhandenen `TrailSpec`.)

- [ ] **Step 3: Test laufen lassen** – `cd backend && uv run pytest tests/test_import_trails.py -q` → FAIL (`KeyError: 'mittelweg'`), nach Step 1 PASS.

- [ ] **Step 4: Westweg-Filter verallgemeinern.** `STAGE_COUNT_SQL`: `where s.trail_id like 'westweg%%'` → Join auf `trails` mit `t.kind = 'long_distance'`; Ausgabe „Fernweg-Etappen: …“. Fotobericht: Fernwege über die Trail-IDs mit `kind = 'long_distance'` statt `startswith("westweg")`. Bestehende Tests der Befehle anpassen, sodass ein `mittelweg`-Eintrag als Fernweg gezählt wird.

- [ ] **Step 5: Echter Import** – `make import` (oder nur `uv run hikeall import-trails`, `import-lodgings`, `import-photos`). Erwartet: beide Wege ohne `GapError`; jede Etappen-km-Abweichung > 5 % steht als Warnung in der Ausgabe und wird in `trails.yaml` kommentiert (nicht weggedrückt). Etappen ohne Unterkunft ≤ 1 km stehen in der Warnliste – übernehmen in die README-Lücken (Task 6).

- [ ] **Step 6:** `make test lint` grün. Commit: `feat: Mittelweg und Ostweg als Fernwege`.

### Task 2: Chat kennt Mittel- und Ostweg

**Files:**
- Modify: `backend/src/hikeall/tags/vocabulary.py` (`TRAILS`)
- Modify: `backend/src/hikeall/agent/understand.py` (nur falls Tests es verlangen; `_resolve_trail`, `_check_multiday_start`)
- Modify: `data/knowledge/sources.yaml`, `data/smoke/prompts.yaml`
- Modify: `web/src/components/HomeStage.tsx:16`, `web/src/app/layout.tsx:8`
- Test: `backend/tests/test_understand.py`, `backend/tests/test_tags.py`

**Interfaces:**
- Consumes: Trail-IDs `mittelweg`, `ostweg` (Task 1).
- Produces: Tags `trail:mittelweg` (Label „Mittelweg“), `trail:ostweg` (Label „Ostweg“), keine Synonyme mit „West“.

- [ ] **Step 1: Failing tests** in `test_understand.py` (Muster der vorhandenen `_resolve_trail`-Tests nutzen):
  - `test_ostweg_is_not_the_west_variant`: „3 Tage Ostweg ab Freudenstadt“ → `trail_id == "ostweg"`, `trail_assumed is False`; „3 Tage Westweg Ost ab Hausach“ → `"westweg-ost"`.
  - `test_mittelweg_resolves`: „Mittelweg ab Pforzheim, 4 Tage“ → `"mittelweg"`, `trail_assumed is False`.
  - `test_pforzheim_without_trail_asks_which_trail`: „3 Tage ab Pforzheim“ → `Clarify` mit Optionen, die „Mittelweg“, „Ostweg“ und „Westweg“ enthalten.
  - `test_unknown_trail_lists_all_four`: „3 Tage Kandelhöhenweg“ → Rückfrage, Optionen = alle vier Fernweg-Labels.
  - In `test_tags.py`: `test_trail_tags_cover_all_long_distance_trails` – die `trail_id` aller Trail-Tags = `{"westweg-west", "westweg-ost", "mittelweg", "ostweg"}`.

- [ ] **Step 2:** `uv run pytest tests/test_understand.py tests/test_tags.py -q` → FAIL.

- [ ] **Step 3:** `TRAILS` um zwei Einträge erweitern; `_trail_echo` bleibt für Nicht-Westweg beim reinen Label. Nur wenn ein Test weiter rot ist, `_resolve_trail` anpassen (Wortgrenzen, nicht Teilstrings).

- [ ] **Step 4:** Tests grün.

- [ ] **Step 5: Wissen & Texte.** `sources.yaml`: `{site: de.wikipedia.org, title: Mittelweg (Schwarzwald)}`, `{site: de.wikipedia.org, title: Ostweg (Schwarzwald)}` und je Wikivoyage-Artikel, **nur wenn er existiert** (sonst Kommentar „kein Wikivoyage-Artikel, geprüft am …“); genaue Artikeltitel beim Abruf prüfen. `make knowledge`. Startseiten-/Meta-Text: „Fernweg-Etappen (Westweg, Mittelweg, Ostweg) und Tagestouren …“. Web-Tests, die den alten Text prüfen, nachziehen.

- [ ] **Step 6: Smoke-Fall** in `data/smoke/prompts.yaml`: `11-ostweg-3-tage` „3 Tage Ostweg ab Freudenstadt, ~15 km pro Tag“ mit `plan_days: 3`, `plan_lodgings_near: true`, `plan_band_or_named: true`. Den Startort vorher prüfen: muss ≤ 2 km vom Ostweg liegen und sich auflösen; sonst einen Etappenort wählen, der es tut. `make smoke` → alle Fälle ok, Ergebnis-CSV einchecken.

- [ ] **Step 7:** `make test lint`. Commit: `feat: Chat plant auf Mittel- und Ostweg`.

### Task 3: Nicht belegte Tournamen sichtbar machen

**Files:**
- Modify: `backend/src/hikeall/agent/grounding.py` (`grounding_check`, neue Konstante `NAME_HINT`)
- Modify: `backend/src/hikeall/agent/graph.py` (`DoneEvent` ~Z. 251, Zählung ~Z. 1152–1154)
- Modify: `web/src/lib/chat.ts:189`, `web/src/lib/__fixtures__/chat-streams.json` falls der Vertragstest das verlangt
- Test: `backend/tests/test_grounding.py`, `backend/tests/test_agent_graph.py`, `backend/tests/test_contract.py`

**Interfaces:**
- Produces: `DoneEvent.unsupported: int` = **nur Zahlen** (Bedeutungsänderung!), `DoneEvent.unsupported_names: list[str] = []`. `GroundingResult` unverändert in der Form; `text` endet bei nicht belegten Namen mit `NAME_HINT`.
- `NAME_HINT = "Hinweis: {names} kommt in den Suchergebnissen dieser Antwort nicht vor – bitte nicht als Vorschlag verstehen."` (bei mehreren Namen kommagetrennt, „kommen“).

- [ ] **Step 1: Failing tests:**
  - `test_unknown_tour_name_gets_a_hint`: Antwort nennt „Feldbergsteig“, Evidence nennt nur „Hochfirstrunde“, `tour_names` enthält beide → `result.unsupported_names == ["Feldbergsteig"]`, `result.text` endet mit dem Hinweis, Name bleibt im Text (nicht ersetzt), `result.unsupported == []`.
  - `test_known_names_get_no_hint`: Name in Evidence → kein Hinweis.
  - Graph-Test: `done.unsupported` zählt nur Zahlen, `done.unsupported_names` die Namen.
- [ ] **Step 2:** `uv run pytest tests/test_grounding.py tests/test_agent_graph.py -q` → FAIL.
- [ ] **Step 3:** Implementieren. In `smoke.run_case` zählen unbelegte Namen weiter als Fehler des Falls: `res.unsupported_names += done.unsupported_names`, Fehlertext „N unbelegte Tournamen: …“; CSV bekommt Spalte `unsupported_names`.
- [ ] **Step 4:** Backend- und Web-Tests grün (`make test`). README-Satz „Tournamen … werden bisher nur gezählt, nicht entfernt“ ersetzen durch das neue Verhalten.
- [ ] **Step 5:** Commit: `feat: Hinweis bei nicht belegten Tournamen`.

### Task 4: Eval-Runner mit Kennzahlen und Bericht

**Files:**
- Create: `backend/src/hikeall/evaluation.py`
- Modify: `backend/src/hikeall/smoke.py` (`EXPECT_KINDS`, `check`)
- Modify: `backend/src/hikeall/cli.py` (Befehl `eval`), `Makefile` (`eval`)
- Create: `data/eval/weather.json`
- Test: `backend/tests/test_evaluation.py`, `backend/tests/test_smoke.py`

**Interfaces:**
- Consumes: `smoke.load_cases`, `smoke.check`, `smoke.run_all`, `smoke.authorize`, `api.chat.default_deps_factory`, `DoneEvent.unsupported_names` (Task 3), `numbers_in_text` (grounding).
- Produces:
  - Fall-Feld `group:` in `cases.yaml`, einer von `erfuellbar | unerfuellbar | mehrtag | aenderung | wissen | eingabeschutz | gruppen_laeufe` (Loader: Pflicht in Eval, optional in Smoke).
  - Neue Erwartungsarten in `check`: `sources_include: [str, …]` (jeder String ist Teilstring von `id` oder `url` einer Quelle unter den ersten 5 des `sources`-Ereignisses), `reply_contains: [str, …]` (alle als Teilstring im Antworttext, Groß-/Kleinschreibung egal), `unsatisfiable_named: true` (`results.fallback_reason` gesetzt **und** Antworttext beginnt mit „Keine Tour erfüllt alle Wünsche“).
  - `FixtureWeather(path: Path)` mit derselben Methode wie `OpenMeteoClient.daily(lat, lon, start, end) -> list[DayWeather]`; fehlt ein Datum: `HikeAllError("keine Wetterdaten für <Datum>")`.
  - `EVAL_TODAY = date(2026, 11, 2)` (Wetter-Fixture deckt 2026-11-02 bis 2026-11-16 ab).
  - `@dataclass Metrics`: `cases`, `passed`, `by_group: dict[str, tuple[int, int]]`, `numbers_total`, `numbers_unsupported`, `unknown_tours` (Tour-IDs in Karten/Plänen, die nicht in `trails` stehen), `names_unsupported`, `unsat_cases`, `unsat_named`, `recall_cases`, `recall_hits`, `cost_usd`.
  - `compute_metrics(results: list[EvalResult]) -> Metrics`, `write_report(path: Path, metrics: Metrics, results, model: str, osm: list[OsmRow]) -> None`, `evaluate(deps_factory, cases_path, out_dir, today) -> int`.
  - `EvalResult` = `CaseResult` + `group: str` + `all_events: list[list[ChatEvent]]` (alle Runden, für Kennzahlen).

- [ ] **Step 1: Failing tests** in `test_evaluation.py` (Fake-Deps wie in `test_smoke.py`, kein Netz):
  - `test_recall_counts_cases_without_sources_as_misses`: zwei Wissensfälle mit `sources_include`, einer ohne `sources`-Ereignis → `recall_cases == 2`, `recall_hits == 1`.
  - `test_number_rate`: Antworttexte mit 10 Zahlen, davon `done.unsupported == 1` → `numbers_total == 10`, `numbers_unsupported == 1` (Nenner = `len(numbers_in_text(text))` + `unsupported`, weil ersetzte Zahlen als „?“ im Text stehen).
  - `test_unsat_named`: Fall der Gruppe `unerfuellbar` mit Fallback und korrektem Satzanfang zählt in `unsat_named`; ohne Satzanfang nicht.
  - `test_unknown_tour_counts_ids_not_in_db`: Karte mit `trail_id="erfunden-1"` bei bekannter ID-Menge `{"a"}` → `unknown_tours == 1`.
  - `test_fixture_weather_never_goes_live`: `FixtureWeather.daily` für ein Datum außerhalb der Datei wirft `HikeAllError` mit „keine Wetterdaten für“; der Fall wird nicht bestanden, der Lauf läuft weiter.
  - `test_report_lists_smart_targets`: `write_report` schreibt eine Tabelle mit den vier Zielen aus Global Constraints, Ist-Wert und „erreicht“/„nicht erreicht“, je Gruppe bestanden/gesamt, Modellname, Datum, Gesamtkosten, und je nicht bestandenem Fall die Fehler.
  - In `test_smoke.py`: je ein Test für `sources_include`, `reply_contains`, `unsatisfiable_named`; Loader lehnt unbekannte `group` ab.
- [ ] **Step 2:** `uv run pytest tests/test_evaluation.py tests/test_smoke.py -q` → FAIL.
- [ ] **Step 3: Implementieren.** `evaluate` baut Deps über `default_deps_factory`, ersetzt danach `deps.tools`' Wetter-Client durch `FixtureWeather(data/eval/weather.json)` und `deps.today` durch `lambda: EVAL_TODAY` (wenn `DbTools` den Client nicht austauschbar macht: optionalen Parameter in der Factory ergänzen, nicht privat patchen). `unknown_tours` per `select id from trails`. Ausgaben: `docs/evaluation/results-<Datum>-<Modell-slug>.csv` (Spalten wie Smoke + `group`, `unsupported_names`) und `docs/evaluation/bericht-<Datum>-<Modell-slug>.md`. Exit 1, wenn ein Fall nicht bestanden ist. `weather.json`: einmal echte Open-Meteo-Tageswerte für die Etappenorte der Eval-Mehrtagesfälle holen (Skript-Ausgabe einchecken, Quelle „Open-Meteo.com (CC BY 4.0)“ und Abrufdatum im JSON), mindestens ein Regentag (≥ 60 % oder ≥ 5 mm) darin, damit die Regenvariante geprüft wird.
- [ ] **Step 4:** Tests grün. `cli.py`: `hikeall eval [--cases PATH]`, meldet sich wie Smoke als Testkonto an. `Makefile`: `eval:` → `cd backend && uv run hikeall eval`.
- [ ] **Step 5:** `make test lint`. Commit: `feat: Eval-Runner mit Kennzahlen und Bericht`.

### Task 5: Abgleich mit OSM

**Files:**
- Modify: `backend/src/hikeall/evaluation.py`
- Test: `backend/tests/test_evaluation.py`

**Interfaces:**
- Consumes: `EvalResult.all_events` (Task 4).
- Produces: `@dataclass OsmRow(trail_id: str, answer_km: float, db_km: float, line_km: float, answer_hm: int | None, db_hm: int | None)`; `osm_rows(results, lookup: Callable[[str], tuple[float, float, int | None]]) -> list[OsmRow]` (lookup → `db_km`, `line_km`, `db_hm`); `OSM_TOLERANCE = 0.02`. `line_km` = `ST_Length(geom::geography)/1000` der gespeicherten OSM-Linie; Fernweg-Tage vergleichen `day.length_km` mit der Länge des Linienausschnitts zwischen den Tageskilometern (inkl. Zuweg getrennt ausgewiesen).

- [ ] **Step 1: Failing tests:** `test_osm_rows_flag_deviation_over_two_percent` (Karte 12,0 km, DB 12,0, Linie 12,5 → Zeile markiert), `test_osm_rows_once_per_trail` (dieselbe Tour in drei Fällen → eine Zeile), `test_report_has_osm_section` (Bericht enthält Abschnitt „Abgleich mit OSM“ mit Anzahl verglichener Touren und Abweichungen > 2 %).
- [ ] **Step 2:** FAIL → implementieren (`lookup` in `evaluate` als SQL über `trails`/`stages`) → PASS.
- [ ] **Step 3:** Commit: `feat: Eval vergleicht Antwort, Datenbank und OSM-Linie`.

### Task 6: Testsatz, Lauf und Bericht

**Files:**
- Create: `data/eval/cases.yaml`
- Create: `docs/evaluation/results-*.csv`, `docs/evaluation/bericht-*.md`, `docs/evaluation/README.md`

**Interfaces:**
- Consumes: alles aus Tasks 1–5.

- [ ] **Step 1: Fälle schreiben (Ziel ~50).** Verteilung:

| Gruppe | Anzahl | Prüfung (Erwartungsarten) |
|---|---|---|
| erfuellbar | 12 | `min_results`, `all_constraints_ok`; je 2–3 Laufrunden mit `activity: run`, `no_pace` |
| unerfuellbar | 8 | `unsatisfiable_named`, `fallback_single_violation` (Feldberg-Fall über `answer_option_containing`) |
| mehrtag | 9 | je 3 für Westweg, Mittelweg, Ostweg: `plan_days`, `plan_lodgings_near`, `plan_band_or_named`; 2 davon mit Datum im Fixture-Zeitraum (Wetter, Regenvariante) |
| aenderung | 5 | `continues` + `days_unchanged`, `day_shorter` („Tag 2 kürzer“, „Tag 3 länger“ – für „länger“ ggf. Erwartungsart `day_longer` analog ergänzen) |
| wissen | 10 | `sources_include` (erwartete Quelle), `reply_contains` (Sollantwort-Kernbegriffe, z. B. „rote Raute“) |
| eingabeschutz | 5 | Injection-Varianten, themenfremd („Rezept für Apfelkuchen“ → `reply: other`), `no_model_calls` wo der Guard vor dem Modell greift |
| gruppen_laeufe | 3 | `min_groups`, `no_groups`, `events_quoted` |

Jeder Startort, jede Wissensquelle und jede Unerfüllbarkeit wird vor dem Eintragen gegen die Datenbank/den Index geprüft (ein Fall darf nicht an fehlenden Daten statt am Agenten scheitern). Erfüllbare Fälle so wählen, dass die Datenbank Treffer hat (SQL-Abfrage als Kommentar am Fall).

- [ ] **Step 2: Lauf** – `make eval`. Rote Fälle einzeln untersuchen (superpowers:systematic-debugging); Code-Fehler mit Test beheben, eigener Commit je Fehler. **Erwartung nie lockern.** Lauf wiederholen, bis jeder rote Fall entweder behoben oder im Bericht mit Ursache als bekannte Schwäche steht.
- [ ] **Step 3: Bericht ergänzen.** `docs/evaluation/README.md`: wie der Lauf funktioniert, Testsatz-Gruppen, wie die Kennzahlen gerechnet werden (Nenner!), Link zum aktuellen Bericht, Interpretation (was die Zahlen zeigen und was nicht: ein Modell, ein Lauf, kein Konfidenzintervall), Kosten.
- [ ] **Step 4:** Commit: `eval: Testsatz und erster Bericht`.

### Task 7 (optional): Modell-/Temperaturvergleich

Nur wenn Tasks 1–6 erledigt sind und vor 2026-11-18.

**Files:** `backend/src/hikeall/config.py` (`hikeall_temperature: float | None = None`), `backend/src/hikeall/llm/gateway.py`, `backend/src/hikeall/cli.py` (`eval --model M --temperature T`), `docs/evaluation/vergleich.md`. Test: `test_llm.py::test_temperature_is_sent_when_set`, `test_evaluation.py::test_eval_cli_overrides_model`.

- [ ] Test → FAIL → Umsetzung (Temperatur nur senden, wenn gesetzt) → PASS → 2–3 Läufe (z. B. `openai/gpt-4o-mini` T=0 und T=0,7, ein zweites günstiges Modell) → Tabelle Kennzahlen × Lauf mit Kosten in `vergleich.md`. Commit: `eval: Modellvergleich`.

### Task 8: Capstone-README, Ethik und Showcase

**Files:**
- Modify: `README.md` (vorhandene Abschnitte bleiben, werden umsortiert)
- Create: `docs/showcase/*.png`

- [ ] **Step 1: Nutzer-Prüfungen (nur Ali).** Vor Screenshots erledigen bzw. bestätigen: 24 Gruppen in `data/curated/groups.csv` von Hand prüfen (`geprüft` setzen, `make groups`), ein echtes Foto hochladen, „Unterwegs“ auf dem Handy über `cloudflared` testen. Ergebnis als Häkchen in diesem Plan.
- [ ] **Step 2: Screenshots** der laufenden App (Chrome-Automatisierung, Desktop 1440 px + Handy 390 px): Startseite, Chat mit Tagestouren, unerfüllbarer Wunsch mit Ausweichtouren, Mehrtagesplan mit Wetter, Routenseite mit Karte und Fotos, Wissensfrage mit Quelle, „Unterwegs“. Ablage `docs/showcase/NN-name.png`. Video nimmt Ali selbst auf (Link in README).
- [ ] **Step 3: README-Aufbau** (oben nach unten): Titel + ein Satz; **Showcase** (Video-Link, 3 Screenshots); Problem (Spec §1 kurz, Alis 3-Tage-Planung, HikeAI-Kritik); Was die App kann (Ziele 1–8, je ein Satz); Wie es funktioniert (Mermaid-Diagramm: Web → API → LangGraph-Knoten verstehen → Tools → Bedingungsprüfung → Antwort → Grounding; Supabase, Chroma); Daten und Lizenzen (Tabelle Spec §7 mit tatsächlichen Mengen aus der DB); **Evaluation** (SMART-Ziele mit Ist-Werten aus dem Bericht, Link); **Ethik und Datenschutz** (Spec §11 vollständig + Grenzen: keine Zimmerverfügbarkeit, OSM veraltet, Bias zu gut kartierten Gebieten, Modell kann trotz Grounding falsch formulieren, Läufe ohne Gewähr, KI-Kosten); Schnellstart/Betrieb (bestehende Abschnitte); Bekannte Lücken (Basel, Schaffhausen, Startorte, Lauftreffs, Ergebnisse aus Task 1 Step 5).
- [ ] **Step 4:** Alle Zahlen im README stammen aus Bericht oder DB-Abfrage (Abfrage als HTML-Kommentar daneben). Links prüfen. Commit: `docs: Capstone-README mit Showcase, Evaluation und Ethik`.

### Task 9: Präsentation (10 min, 6 Punkte)

**Files:** Create `docs/presentation/gliederung.md` (Quelle der Folien, mit Sprechnotizen und Zeit je Punkt).

- [ ] **Step 1: Gliederung** in sechs Punkten: (1) Problem – Alis Tage an Vorbereitung, HikeAI-Kritik; (2) Lösung und Demo-Ablauf (Video/Live: Unerfüllbarer Wunsch → Ausweichtouren → 3 Tage Ostweg → „Tag 3 kürzer“ → Unterwegs); (3) Architektur (Agent, Tools, Code prüft Bedingungen, Grounding); (4) Daten und Herkunft; (5) Evaluation – SMART-Ziele mit Ist-Werten, ein ehrlicher Fehlschlag; (6) Ethik, Grenzen, nächste Schritte. Je Punkt Minuten (Summe 10).
- [ ] **Step 2: Folien** aus der Gliederung erzeugen (Format mit Ali klären: Folien-Artifact mit PDF/PPTX-Export oder `.pptx`); Zahlen nur aus dem Eval-Bericht, Screenshots aus `docs/showcase/`.
- [ ] **Step 3:** Probelauf mit Uhr; Commit: `docs: Präsentation`.

---

## Reihenfolge und Zeit

Task 1 → 2 (Daten vor Chat) · Task 3 unabhängig, vor Task 4 · Task 4 → 5 → 6 · Task 8 nach 6 (Zahlen) · Task 9 nach 8. Ziel: Tasks 1–6 bis 2026-11-12, README/Showcase bis 2026-11-19, Präsentation bis 2026-11-23 (Abgabe ca. 2026-11-25).
