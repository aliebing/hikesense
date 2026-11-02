# Stufe 4: Wetter-Tagesfinder – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bei Anfragen wie „Feldberg-Wanderung bei schönem Wetter“ oder „wenn es schneit“ nennt die App aus der 14-Tage-Vorhersage die Tage, die zum Wetterwunsch passen – mit Werten, ehrlich, wenn keiner passt; für Mehrtagestouren einen Zeitraum, an dem alle Etappentage passen.

**Architecture:** `HikeRequest` bekommt `weather_wish` (vom Modell erkannt, vom Code gegen die Wörter der Nachricht geprüft). Ein neues Werkzeug `forecast_range(points, today)` holt die Vorhersage für heute bis +14 Tage in einer Open-Meteo-Anfrage (jetzt mit Schneefall). Feste Schwellen in `agent/weather.py` entscheiden je Tag „passt / passt nicht“. Der Graph schickt ein `WeatherDaysEvent` an die Web-App und hängt einen vom Code geschriebenen Satz an die Antwort; der Log bekommt den Block für das Admin-Backend.

**Tech Stack:** Python/FastAPI/LangGraph/pytest, Open-Meteo; Next.js/Vitest; zweisprachig (en/de) wie die übrige App.

**Spec:** `docs/superpowers/specs/2026-11-02-rollen-backend-regionen-wetter-design.md`, Abschnitt „Stufe 4“ und „Für alle Stufen“; Sprache: `docs/superpowers/specs/2026-11-02-zweisprachig-design.md`.

**Branch:** `stufe4-wetter` von `main` (Worktree `/home/ali/projects/HikeAllAbout-wetter`).

## Global Constraints

- Horizont: heute bis heute + 14 Tage (`HORIZON_DAYS = 14`), nie darüber; keine Klimastatistik, keine Warnungen.
- Nie geschätzt, Vorhersage nie erfunden; alle Zahlen kommen aus Open-Meteo und laufen durch die Zahlenprüfung bzw. stehen in vom Code geschriebenen Sätzen.
- Schwellen (Claudes Entscheidung, im Code dokumentiert, Konstanten in `agent/weather.py`):
  - `fine` („schönes Wetter“, „sonnig“, „gutes Wetter“; en „nice/fine/good/sunny weather“): Wettercode 0–3 (klar bis bedeckt, kein Nebel/Niederschlag), Niederschlag ≤ 0,5 mm, Niederschlagswahrscheinlichkeit ≤ 30 %.
  - `dry` („trocken“, „kein Regen“, „ohne Regen“; en „dry“, „no rain“): Niederschlag ≤ 1,0 mm und Wahrscheinlichkeit ≤ 40 %.
  - `snow` („Schnee“, „wenn es schneit“, „verschneit“; en „snow“, „snowy“, „when it snows“): Schneefall ≥ 1,0 cm oder Wettercode 71–77, 85, 86.
- Sprache wie überall: Texte in der Sprache der Anfrage, deutsche Ausgaben unverändert für alte Anfragen ohne Wetterwunsch.
- Die Vorhersage gilt für einen Punkt: Tagestour = Startort (Gebiet: Mitte der Box); Mehrtagestour = Tagesziel jeder Etappe.
- Bestehendes bleibt: ein Datum ohne Wetterwunsch verhält sich wie heute.

## Review Focus

1. **Wetterwunsch, den der Nutzer nicht geschrieben hat** – vom Modell erfundener Wunsch wird verworfen (wie R27). Test in Task 2.
2. **Kein passender Tag** – Satz „In den nächsten 14 Tagen passt kein Tag zu ‚schönes Wetter‘; am besten: …“ mit den 3 besten Tagen und Werten. Test in Task 3.
3. **Datum + Wetterwunsch** („Samstag bei Sonne“) – der Tag wird geprüft; passt er nicht, kommt das ehrlich plus die passenden Tage. Test in Task 3.
4. **Wetterdienst nicht erreichbar** – Touren kommen trotzdem, Satz „Wetter gerade nicht abrufbar“, kein Absturz. Test in Task 3.
5. **Mehrtagestour ohne passenden Zeitraum** – ehrlich, bester Zeitraum mit Anzahl passender Tage. Test in Task 4.

---

### Task 1: Vorhersage-Zeitraum, Schneefall, Schwellen

**Files:** `backend/src/hikeall/adapters/open_meteo.py` (`DAILY_FIELDS` + `snowfall_sum`, `DayWeather.snowfall_cm: float | None = None`), `backend/src/hikeall/agent/weather.py`, `backend/src/hikeall/agent/tools.py` (`forecast_range` in `AgentTools`/`DbTools`), Tests `test_weather.py`, `adapters/…`.

**Interfaces:**
- `WeatherWish = Literal["fine", "dry", "snow"]` (in `agent/weather.py`).
- Konstanten `FINE_MAX_MM = 0.5`, `FINE_MAX_PROB = 30`, `FINE_CODES = {0,1,2,3}`, `DRY_MAX_MM = 1.0`, `DRY_MAX_PROB = 40`, `SNOW_MIN_CM = 1.0`, `SNOW_CODES = {71,73,75,77,85,86}`.
- `matches(w: DayWeather, wish: WeatherWish) -> bool | None` – None, wenn ein nötiger Wert fehlt.
- `score(w: DayWeather, wish: WeatherWish) -> float` – für „beste Tage“, höher = besser (fine/dry: weniger Niederschlag und Wahrscheinlichkeit; snow: mehr Schnee).
- `forecast_range(client, points: list[tuple[float, float]], today: date) -> list[list[DayWeather]] | NoForecast` – eine Anfrage `daily_many(points, today, today + 14 Tage)`, 1-h-Cache wie `weather_for`; Fehler → `no_forecast("unavailable")`.
- `AgentTools.forecast_range(points, today)` (DbTools: Open-Meteo-Client wie `weather_days`).
- [ ] Tests: `matches` für jede Schwelle an der Grenze (0,5 mm / 0,6 mm; 30 % / 31 %; Code 3 / 45; Schnee 1,0 / 0,9 cm; Code 73), fehlende Werte → None; `score`-Ordnung; `forecast_range` mit Fake-Client (eine Anfrage für mehrere Punkte, 15 Tage, Cache-Treffer ohne zweite Anfrage, Fehler → NoForecast); Parser liest `snowfall_sum`.
- [ ] Implement; `uv run pytest -q` – PASS; Commit `feat: Vorhersage-Zeitraum mit Schneefall und Wetter-Schwellen`

### Task 2: Wetterwunsch verstehen

**Files:** `agent/request.py` (`RawRequest.weather_wish`, `HikeRequest.weather_wish: WeatherWish | None = None`), `agent/understand.py` (Prompt-Feld, Prüfung gegen die Nachricht, Merge bei Verfeinerung, Echo), `agent/texts.py`/Echo-Wörter, Tests `test_understand.py`.
- Wörter (beide Sprachen, unabhängig von `lang`): fine: „schön(es|em)? wetter“, „sonnig“, „sonne“, „gutes wetter“, „nice/fine/good/sunny weather“, „sunshine“, „sunny“; dry: „trocken“, „kein(en)? regen“, „ohne regen“, „dry“, „no rain“, „without rain“; snow: „schnee“, „schneit“, „verschneit“, „snow“, „snowy“, „when it snows“. Ein vom Modell gesetzter Wunsch ohne passendes Wort wird verworfen (`discarded_model_numbers += 1`).
- Echo: „Wetter: schön / trocken / Schnee“ bzw. „weather: fine / dry / snow“.
- Verfeinerung übernimmt den Wunsch; „egal welches Wetter“/„any weather“ löscht ihn.
- [ ] Tests: „Feldberg bei schönem Wetter“ → fine; „when it snows near Feldberg“ → snow; Modell setzt fine bei „Rundweg Titisee 10 km“ → verworfen; Verfeinerung „kürzer“ behält den Wunsch; „egal welches Wetter“ löscht ihn; Echo beide Sprachen.
- [ ] Implement; Run – PASS; Commit `feat: Wetterwunsch verstehen`

### Task 3: Tagesfinder für Tagestouren

**Files:** `agent/graph.py` (Suche: nach den Karten, wenn `weather_wish`), `agent/texts.py` (Sätze), `chatlog.py` (`weather_days: dict | None = None` im Log), Tests `test_agent_graph.py`.

**Interfaces:**
- `WeatherDaysEvent(type="weather_days", wish: WeatherWish, place: str, days: list[WeatherDay], best_only: bool, note: str | None)`; `WeatherDay = {date, match: bool | None, weather: DayWeather}` (Wetter in der Sprache lokalisiert).
- Ablauf: Punkt = Startort (Gebiet: Mitte der Box); `forecast_range([punkt], today)`; passende Tage = `matches is True`; ohne Datum: alle passenden Tage (höchstens 7, chronologisch); keiner passt → `best_only=True` mit den 3 besten nach `score`. Mit Datum: dieser Tag zuerst (passt/passt nicht), dazu bis zu 5 weitere passende Tage. Datum außerhalb des Horizonts → bestehender NoForecast-Satz plus passende Tage im Horizont.
- Satz (Code, nach der Antwort, nie vom Modell): de „Passende Tage für ‚schönes Wetter‘ am Feldberg: Mi 5.11. (klar, 2–11 °C, 0 mm), Do 6.11. (…).“ / „In den nächsten 14 Tagen passt kein Tag zu ‚Schnee‘ am Feldberg; am ehesten: …“; en entsprechend („Days that fit ‘fine weather’ near Feldberg: Wed 5 Nov (clear, 2–11 °C, 0 mm) …“, „No day in the next 14 days fits ‘snow’ near Feldberg; closest: …“). Wetterdienst weg → „Wetter gerade nicht abrufbar.“ / „Weather currently unavailable.“
- Die Modell-Daten bekommen die passenden Tage (damit das Modell sie nennen darf); alle Zahlen kommen in die Evidenz.
- Log: `weather_days = {wish, place, days: [{date, match, code, t_min_c, t_max_c, precip_mm, precip_prob_pct, snowfall_cm}], best_only}`.
- [ ] Tests (Fake-Tools mit fester Vorhersage): passende Tage gelistet (Event + Satz, de und en); kein passender Tag → beste 3 + ehrlicher Satz; Datum + Wunsch, Tag passt nicht → Satz sagt das + Alternativen; Wetterdienst weg → Touren + Satz, kein Fehler; ohne Wunsch unverändert (bestehende Tests grün); Log-Feld gesetzt; Zahlen im Satz bleiben nach der Zahlenprüfung unverändert.
- [ ] Implement; Run – PASS; Commit `feat: Wetter-Tagesfinder für Tagestouren`

### Task 4: Zeitraum für Mehrtagestouren

**Files:** `agent/graph.py` (multiday), `agent/weather.py` (`best_windows`), Tests.
- `best_windows(per_day: list[list[DayWeather]], days: int, wish) -> list[Window]`: Startdatum s (heute … heute+14−days+1); Tag i nutzt die Vorhersage am Tagesziel i am Datum s+i; `Window = {start: date, fits: int, days: int}`; sortiert nach `fits` absteigend, dann früher.
- Ablauf: Wunsch gesetzt, kein Startdatum → Plan ohne Datum wie heute, Tagesziele via `day_end_points`, `forecast_range(tagesziele, today)`, beste Fenster; gibt es ein Fenster mit `fits == days`, wird der Plan mit dessen Startdatum datiert (damit Wetter je Tag erscheint) und der Satz nennt die passenden Starttage (bis 3); sonst ehrlicher Satz mit dem besten Fenster („höchstens 2 von 3 Tagen passen, ab Fr 7.11.“), Plan bleibt ohne Datum. Mit Startdatum: wie heute, plus Satz, ob die Tage passen.
- [ ] Tests: Fenster gefunden → Plan datiert, Satz nennt Starttage; kein volles Fenster → ehrlicher Satz mit bestem Fenster; mit Startdatum → Prüfsatz; de und en.
- [ ] Implement; Run – PASS; Commit `feat: Wetter-Zeitraum für Mehrtagestouren`

### Task 5: Anzeige in der Web-App und im Admin-Backend

**Files:** `web/src/lib/chat.ts` (Event-Typ), `web/src/lib/chatState.ts`, neue `web/src/components/WeatherDays.tsx` (Liste der Tage: Wochentag + Datum, Symbol/Wort, Temperatur, Niederschlag mm/%, Schnee cm, ✓ passend), Einbindung in `ChatMessages.tsx`, Katalogtexte en/de, `components/admin/SearchDetail.tsx` (Block „Wetter-Tagesfinder“ aus `weather_days`), `web/src/lib/admin.ts` Typ, Contract-Fixtures/Tests (`backend/tests/test_contract.py`, `web/src/lib/contract.test.tsx`).
- [ ] Tests: WeatherDays rendert passende Tage mit ✓ und Werten (en/de-Format), „best only“-Hinweis; Chat zeigt das Event; Admin zeigt den Block; Contract-Fixture enthält ein `weather_days`-Event.
- [ ] Implement; `npx vitest run && npx tsc --noEmit` – PASS; Commit `feat: Wetter-Tagesfinder in Chat und Backend`

### Task 6: Smoke, Prüfung, README

- [ ] `data/smoke/prompts.yaml`: „Feldberg-Wanderung bei schönem Wetter“, „Rundweg am Titisee wenn es schneit“, „A round walk near Titisee in fine weather“ (lang en), „3 Tage Westweg ab Hausach bei trockenem Wetter“; Smoke laufen lassen (wenige Cent), Ergebnis festhalten (die Tage hängen vom echten Wetter ab – geprüft wird Form, nicht Inhalt).
- [ ] Live im Browser (wie Teil B Task 6, Ports 8002/3102): eine Anfrage je Wunsch, Screenshot.
- [ ] README: Abschnitt Wetter-Tagesfinder mit den Schwellen.
- [ ] Commit `docs: Wetter-Tagesfinder`
