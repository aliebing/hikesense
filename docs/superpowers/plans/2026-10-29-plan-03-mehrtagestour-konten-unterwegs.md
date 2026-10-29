# Plan 3 – Mehrtagestour mit Wetter, Konten, eigene Fotos, „Unterwegs“, Gruppen und Läufe

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** „3 Tage Westweg ab Hausach, ~15 km/Tag, ab 12. Juni“ ergibt einen Plan mit Tagesetappen, die jeweils an einer Unterkunft ≤ 1 km vom Weg enden, mit Ankunftszeit, Wetter (≤ 14 Tage) und Regenvariante; „Tag 3 kürzer“ ändert nur Tag 3 und die Folgetage. Angemeldete Nutzer speichern Pläne, laden eigene Fotos (ohne Ortsdaten) hoch und sehen auf dem Handy ihre Position auf der Etappe mit Restkilometern. Der Chat nennt Wander-/Laufgruppen in der Nähe (verlinkte Liste mit Prüfdatum) und sucht offizielle Läufe live im Web – jede Angabe mit Quelle, sonst „nicht angegeben“.

**Architecture:** Mehrtagesplanung ist reiner Code (`agent/multiday.py`, Dynamische Programmierung über Unterkünfte entlang der Linie, `trail_lodgings.along_km`), das Modell formuliert nur. Wetter kommt live von Open-Meteo (kein Schlüssel). Die API prüft das Supabase-JWT; der Browser spricht für Anmeldung, gespeicherte Pläne und Fotos direkt mit Supabase (RLS). Die Laufsuche nutzt das OpenRouter-Web-Plugin (Engine Exa) für Treffer, liest höchstens 3 Seiten selbst und übernimmt ein Feld nur, wenn ein wörtliches Zitat dafür auf der Seite steht. „Unterwegs“ rechnet die Position nur im Browser.

**Tech Stack:** wie Plan 2, dazu: PyJWT (HS256 + JWKS), beautifulsoup4 (Seitentext), protego (robots.txt) · Web: Supabase Auth im Browser (`@supabase/supabase-js`, Sitzung im localStorage), Web-App-Manifest + minimaler Service Worker, Browser-Geolocation, Canvas-Neukodierung für Fotos.

**Spec:** `docs/superpowers/specs/2026-10-28-hike-all-about-design.md` (§2 Ziele 1, 4, 6, 7, 8; §5; §8 `plan_multiday`, `get_weather`, Regenvariante, Wetter-Horizont, Plan speichern; §10; §11) · **Eingaben:** `docs/superpowers/notes/2026-10-29-plan-02-inputs-from-hikeai.md` (Punkte 6, 7), `docs/superpowers/notes/2026-10-29-laufveranstaltungen-datenquellen.md` (§2, §6) · **Übernommen aus Plan 2:** Wikivoyage-Rauschen, Rate-Limit-Schlüssel aufräumen.

**Folgeplan (nicht hier):** Plan 4 – Mittel-/Ostweg, Evaluation mit Testset (inkl. volle Namensprüfung, Eingabeschutz-Grenzfälle), README-Showcase, Ethik-Abschnitt, Screenshots/Video, Präsentation.

**Bewusste Schnitte [Claude, beim Review änderbar]:**
- **Regenvariante ohne OpenRouteService:** Spec §12 erlaubt den Wegfall („dann nur kürzere Etappe“). Hier: bei Regen endet der Tag zu Fuß am letzten Bahnhof/Haltepunkt vor der Unterkunft (POI `station` ≤ 300 m vom Weg), Rest „mit Bus/Bahn – Fahrplan selbst prüfen“. Keine erfundenen Fahrzeiten.
- **Nur Westweg** (West- und Ostvariante) für Mehrtagestouren; Mittel-/Ostweg in Plan 4.
- **„Halbpension“ und ähnliche Unterkunftswünsche** sind in OSM nicht verlässlich getaggt → „nicht prüfbar: Halbpension“, nie geraten.
- **Speichern auf Knopfdruck („Merken“)** statt automatisch nach jeder Antwort (Spec §8.7): der Gesprächszustand bleibt wie in Plan 2 im Checkpointer; in Supabase landet nur, was der Nutzer merkt – weniger Datenhaltung, klarer für den Nutzer.

## Global Constraints

- Alle Regeln aus Plan 2 gelten weiter (keine erfundenen Zahlen/Routen, nie still lockern, „unbekannt“ erfüllt nichts, Grounding, Limits, Protokoll ohne Nachrichtentexte, Tests ohne Netz und ohne Kosten).
- **Konten:** `/chat` nur mit gültigem Supabase-Access-Token (`Authorization: Bearer …`). Rate-Limit **je Nutzer-ID**: 10/Minute, 100/Tag. An das Modell und ins Protokoll gehen weder E-Mail noch Nutzer-ID (im Protokoll nur ein gekürzter SHA-256 der ID, 12 Zeichen).
- **Mehrtagestour (Spec §8):** Tagesziel = Unterkunft **≤ 1000 m** vom Weg; nur wenn es keine gibt, Ausweichen bis **2000 m** mit Zuweg (hin am Ankunftstag, zurück am Folgetag) addiert und offen benannt; sonst Lücke benennen. Toleranzband Tagesstrecke: **±20 %** um das Ziel. Standard-Tagesziel ohne Angabe: **15 km**; Standard-Startzeit **09:00**; Ankunft = Start + DIN-33466-Zeit, **ohne Pausen** (so beschriftet).
- **Wetter (Spec §8):** Open-Meteo-Vorhersage nur für Tage **≤ 14 Tage** ab heute; sonst „noch keine Vorhersage“. Quelle „Open-Meteo.com (CC BY 4.0)“ sichtbar. Regentag = Niederschlagswahrscheinlichkeit **≥ 60 %** oder Niederschlagssumme **≥ 5 mm**.
- **Fotos (Spec §11):** Uploads privat (nur Eigentümer), EXIF/GPS **vor** dem Hochladen im Browser entfernt (Neukodierung als JPEG über Canvas), höchstens **10 MB** Eingabe, längste Seite **2560 px**, nur JPEG/PNG/WebP.
- **Standort (Spec §11):** bleibt im Browser; wird weder gesendet noch gespeichert. Keine Aufzeichnung, keine Hintergrundortung.
- **Gruppen:** nur Name, Art, Ort, Link, Quelle, Prüfdatum; keine Personen, keine Termine. Anzeige „Stand: <Prüfdatum>“; Einträge mit Prüfdatum älter als **180 Tage** als „veraltet“ markiert.
- **Läufe (Notiz Punkt 7):** nichts wird gespeichert (kein DB-Eintrag, kein Datei-Cache). Kein Abruf von `laufen.de`, `marathon.de`, `d-u-v.org`, `ultra-marathon.org`, `ladv.de`, `hdsports.org` (weder Suche noch Seitenabruf). Höchstens **3** Seiten je Anfrage, `robots.txt` beachten, eigener User-Agent (`HIKEALL_USER_AGENT`), **10 s** Zeitlimit, **1 MB** je Seite. Jedes Feld (Name, Datum, Ort, Distanzen, Anmeldelink, Anmeldeschluss, Startgebühr) nur mit wörtlichem Zitat von der Seite, sonst „nicht angegeben“. Läufe mit Datum in der Vergangenheit werden nicht gezeigt. Hinweis „Angaben ohne Gewähr – bitte beim Veranstalter prüfen“.
- Websuche: OpenRouter-Plugin `{"id": "web", "engine": "exa", "max_results": 5, "exclude_domains": [...]}` (0,007 USD je Suche laut OpenRouter-Doku); Kosten zählen ins Budget je Nachricht (0,05 USD).
- **Spec-Änderung (vom Nutzer entschieden, Notiz Punkt 6):** §3 „Keine Community-Funktionen“ erhält den Zusatz „Ausnahme: eine von Hand gepflegte, verlinkte Gruppenliste mit Prüfdatum“ (Task 11).

## Review Focus

1. **Startort liegt nicht am Weg oder der Plan läuft über das Wegende hinaus** („5 Tage Westweg ab Kandern“): ehrliche Meldung („ab Kandern bleiben 28 km bis Basel – 2 Tage bei ~15 km“), kein erfundener Tag (Task 5, Test `test_plan_stops_at_trail_end`).
2. **Token abgelaufen mitten im Gespräch:** Chat zeigt „Bitte erneut anmelden“, Eingabe bleibt erhalten, kein Absturz (Tasks 1/2, Tests `test_expired_token_401`, `shows re-login on 401`).
3. **Laufseite nennt ein Feld nicht oder widersprüchlich** (Gebühr nur im PDF, zwei Daten): Feld „nicht angegeben“ statt geraten; Zitat muss wörtlich vorkommen (Task 12, Test `test_field_without_quote_is_not_given`).
4. **Foto ist HEIC, zu groß oder kein Bild; Foto enthält GPS-EXIF:** verständliche Ablehnung bzw. hochgeladene Datei ohne EXIF (Task 9, Tests `rejects heic and oversized`, `strips exif before upload`).
5. **Ortung verweigert, nicht verfügbar oder weit weg vom Weg:** klare Meldung („Standortfreigabe verweigert“ / „Du bist 1,2 km vom Weg entfernt“), keine Restkilometer erfunden (Task 10, Tests `denied permission message`, `off-route over 200 m`).

---

## Dateistruktur (neu oder geändert)

```
backend/src/hikeall/
├── auth.py                     # Supabase-JWT prüfen (HS256-Secret oder JWKS)
├── rate_limit.py               # Schlüssel = Nutzer, Aufräumen untätiger Schlüssel
├── adapters/open_meteo.py      # Vorhersage (aus HikeAI tools/weather.py, domain/weather.py)
├── agent/weather.py            # DayWeather, Horizont, Regentag
├── agent/multiday.py           # plan_multiday (rein + DB-Lader), change_day
├── agent/request.py            # HikeRequest + Mehrtages-Felder, Intents events/groups
├── agent/understand.py         # Fernweg/Tage/Tagesziel/Datum verstehen
├── agent/graph.py              # Knoten multiday, groups, events; PlanEvent, EventsEvent, GroupsEvent
├── agent/events.py             # Websuche, Seitenabruf, Felder mit Zitat prüfen
├── adapters/web_search.py      # OpenRouter-Web-Plugin (Exa) hinter Protocol
├── adapters/page_fetch.py      # robots.txt, Größen-/Zeitlimit, HTML→Text
├── ingest/groups.py            # data/curated/groups.csv → Tabelle groups
└── knowledge/corpus.py         # Wikivoyage-Rauschen entfernen
data/curated/groups.csv
data/events/calendars.yaml      # Rückfall-Links (B)
supabase/migrations/20261030*.sql   # saved_plans, photos-Uploads + Storage, groups
web/src/lib/auth.ts, web/src/lib/geo.ts, web/src/lib/photo.ts, web/src/lib/plans.ts
web/src/app/anmelden/page.tsx, web/src/app/meine-plaene/page.tsx, web/src/app/unterwegs/page.tsx
web/src/components/{PlanDays,EventCards,GroupList,PhotoUpload,Unterwegs}.tsx
web/public/manifest.webmanifest, web/public/sw.js, web/public/icons/*
```

---

### Task 1: API nur mit Anmeldung, Rate-Limit je Nutzer

**Files:**
- Create: `backend/src/hikeall/auth.py`
- Modify: `backend/src/hikeall/api/chat.py`, `backend/src/hikeall/rate_limit.py`, `backend/src/hikeall/config.py`, `backend/src/hikeall/chatlog.py`, `.env.example`, `backend/pyproject.toml` (PyJWT[crypto])
- Test: `backend/tests/test_auth.py`, `backend/tests/test_api_chat.py`, `backend/tests/test_rate_limit.py`

**Interfaces:**
- Produces:
  - Settings: `supabase_jwt_secret: str | None = None`, `supabase_url: str | None = None` (für JWKS `{supabase_url}/auth/v1/.well-known/jwks.json`).
  - `verify_token(token: str, settings) -> AuthUser(user_id: str)`; HS256 mit Secret, ES256/RS256 über JWKS (PyJWKClient, gecacht); Audience `authenticated`; Fehler → `AuthError(reason: Literal["missing", "expired", "invalid"])`.
  - `/chat`: ohne/ungültiges Token → `401` + JSON `{"detail": "Bitte anmelden."}` bzw. bei `expired` `{"detail": "Sitzung abgelaufen – bitte erneut anmelden."}`. Rate-Limit-Schlüssel = `user_id`.
  - `RateLimiter.acquire(key)` (Parameter umbenannt von `ip`) und `prune(now)`: entfernt Schlüssel ohne Treffer in den letzten 24 h; wird bei jedem `acquire` höchstens einmal pro Minute aufgerufen.
  - `ChatLogEntry.user_hash: str | None` = erste 12 Zeichen von `sha256(user_id)`.
  - `/health` meldet zusätzlich `auth: bool` (Secret oder URL gesetzt).

- [ ] **Step 1: Tests**

```python
def test_valid_hs256_token(settings_with_secret): assert verify_token(make_token(sub="u1"), s).user_id == "u1"
def test_expired_token_401(client): r = client.post("/chat", headers=bearer(expired), json=...); assert r.status_code == 401 and "erneut anmelden" in r.json()["detail"]
def test_missing_token_401(client): ...
def test_wrong_audience_rejected(): ...
def test_rate_limit_per_user_not_ip(client): # 11. Anfrage von u1 → 429, u2 weiterhin 200
def test_prune_drops_idle_keys(fake_clock): ...
def test_log_has_user_hash_not_id(tmp_path): ...  # kein "u1" im Log, 12-stelliger Hash
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren (Rate-Limit vor dem Graph, nach der Token-Prüfung). **Step 4:** PASS (volle Suite, ruff).
- [ ] **Step 5: Echter Check:** Mit einem lokal angelegten Testnutzer (`npx supabase` Auth, E-Mail+Passwort) ein Token holen und `/chat` aufrufen; Algorithmus des echten Tokens (`alg` im Header) im Bericht nennen.
- [ ] **Step 6:** Commit `feat: chat requires a Supabase session, rate limit per user`.

### Task 2: Anmeldung im Web, Chat mit Token

**Files:**
- Create: `web/src/lib/auth.ts`, `web/src/app/anmelden/page.tsx`, `web/src/components/AccountMenu.tsx`
- Modify: `web/src/lib/chat.ts`, `web/src/components/ChatShell.tsx`, `web/src/app/layout.tsx`, `.env.example` (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- Test: `web/src/lib/auth.test.ts`, `web/src/components/ChatShell.test.tsx`, `web/src/app/anmelden/page.test.tsx`

**Interfaces:**
- Consumes: `/chat` mit `Authorization` (Task 1).
- Produces: `getBrowserSupabase(): SupabaseClient` (Singleton, `persistSession: true`); `useSession(): { session, loading }`; `signIn(email, password)`, `signUp(email, password)`, `signOut()` mit deutschen Fehlermeldungen (`Invalid login credentials` → „E-Mail oder Passwort falsch“). `streamChat` erhält `accessToken`; 401 → Ereignis `{type: "auth", message}`.
- ChatShell: ohne Sitzung statt Eingabe der Hinweis „Zum Planen bitte anmelden“ mit Link `/anmelden`; bei `auth`-Ereignis „Sitzung abgelaufen – bitte erneut anmelden“, die getippte Nachricht bleibt im Feld.
- Tourseiten und Startseite bleiben ohne Anmeldung lesbar.

- [ ] **Step 1: Tests**

```ts
it("shows login hint without session", ...)
it("sends bearer token", ...)            // fetch-Mock prüft Header
it("shows re-login on 401 and keeps the draft", ...)
it("maps supabase error to German", ...)
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS (`npm test`, `npx tsc --noEmit`, `npm run lint`).
- [ ] **Step 5:** Commit `feat: sign-in page and authenticated chat`.

### Task 3: Gespeicherte Pläne

**Files:**
- Create: `supabase/migrations/20261030000001_saved_plans.sql`, `web/src/lib/plans.ts`, `web/src/app/meine-plaene/page.tsx`
- Modify: `web/src/components/TourResultCard.tsx`, `web/src/components/AccountMenu.tsx`
- Test: `backend/tests/test_saved_plans_rls.py` (`@pytest.mark.db`), `web/src/lib/plans.test.ts`, `web/src/app/meine-plaene/page.test.tsx`

**Interfaces:**
- Produces:
  - Tabelle `saved_plans(id uuid pk default gen_random_uuid(), user_id uuid not null default auth.uid() references auth.users on delete cascade, kind text check (kind in ('day_hike','multiday')), title text not null, payload jsonb not null, created_at timestamptz default now())`; RLS: select/insert/delete nur `user_id = auth.uid()`; kein Zugriff für `anon`.
  - `payload`: für `day_hike` die `TourCard` (Plan 2), für `multiday` der `MultidayPlan` (Task 5) – genau das JSON aus dem Ergebnis-Ereignis, keine neu berechneten Zahlen.
  - `savePlan(kind, title, payload)`, `listPlans()`, `deletePlan(id)` in `plans.ts`.
  - Taste „Merken“ auf Tourkarten und auf dem Mehrtagesplan (Task 8) nur mit Sitzung; Seite `/meine-plaene` listet Titel, Art, Datum, Link zur Tour bzw. Plananzeige.

- [ ] **Step 1: Tests**

```python
@pytest.mark.db
def test_other_user_cannot_read_plan(conn): ...   # set_config('request.jwt.claims', …) als zwei Nutzer
@pytest.mark.db
def test_anon_cannot_read_plans(conn): ...
```
```ts
it("saves the card payload unchanged", ...)
it("lists and deletes own plans", ...)
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: save plans per user`.

### Task 4: Wetter (Open-Meteo)

**Files:**
- Create: `backend/src/hikeall/adapters/open_meteo.py`, `backend/src/hikeall/agent/weather.py`, `backend/tests/fixtures/open_meteo_daily.json`
- Test: `backend/tests/test_weather.py`

**Interfaces:**
- Produces:
  - `OpenMeteoClient(http).daily(lat, lon, start: date, end: date) -> list[DayWeather]`; Felder `daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max`, `timezone=Europe/Berlin`. Aus HikeAI `tools/weather.py` + `domain/weather.py` übernehmen (Wettercode → deutscher Text).
  - `DayWeather(date, code: int | None, text: str | None, t_min_c, t_max_c, precip_mm, precip_prob_pct, source_id="open-meteo")` – fehlende Werte bleiben `None`.
  - `weather_for(client, lat, lon, day: date, today: date) -> DayWeather | NoForecast(reason="Noch keine Vorhersage (mehr als 14 Tage)")`; Tage in der Vergangenheit → `NoForecast(reason="Datum liegt in der Vergangenheit")`.
  - `is_rain_day(w: DayWeather) -> bool | None` (≥ 60 % oder ≥ 5 mm; `None`, wenn beides fehlt).
  - In-Memory-Cache je (lat/lon auf 2 Stellen, Datum) für **1 h**; Netzfehler → `NoForecast(reason="Wetterdienst nicht erreichbar")`, nie geschätzt.
  - Quelle `open-meteo` in `sources` (Name „Open-Meteo.com“, Lizenz „CC BY 4.0“, URL `https://open-meteo.com/`), per `upsert_source` beim API-Start.

- [ ] **Step 1: Tests** (respx + Fixture): `test_day_15_has_no_forecast`, `test_missing_values_stay_none`, `test_rain_day_threshold` (59 %/4,9 mm → False, 60 % → True), `test_network_error_is_no_forecast`, `test_cache_hits_once`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: Open-Meteo forecast with 14-day horizon`.

### Task 5: Mehrtagesplanung (Code)

**Files:**
- Create: `backend/src/hikeall/agent/multiday.py`
- Test: `backend/tests/test_multiday.py`

**Interfaces:**
- Consumes: `trails` (Linie, `profile`), `trail_lodgings` (`dist_m`, `along_km`), `trail_pois` (Bahnhöfe), `hiking_time.din33466`.
- Produces:
  - `Stop(lodging_id, name, kind, website, along_km, dist_m)`; `DayPlan(day: int, date: date | None, start_km, end_km, walk_km, access_km, length_km, ascent_m, descent_m, duration_h, start_time: time, arrival: time, stop: Stop | None, gap: str | None, within_band: bool)`; `MultidayPlan(trail_id, trail_name, target_km, days: list[DayPlan], notes: list[str], source_ids: list[str])`.
  - `plan_multiday(stops: list[Stop], profile, trail_len_km, start_km, days: int, target_km=15.0, start_date=None, start_time=time(9)) -> MultidayPlan` – rein, deterministisch:
    - Kandidaten je Tag: Unterkünfte mit `along_km` > Tagesstart; zuerst nur `dist_m ≤ 1000`; gibt es im Band ±20 % keine, dann `≤ 2000` (Zuweg = `dist_m/1000` am Ankunftstag **und** am Folgetag addiert, Note „Unterkunft X liegt 1,4 km abseits – Zuweg eingerechnet“); gibt es auch dann keine im Band, nimmt die DP die nächstbeste ≤ 1000 m und setzt `within_band=False` + `gap="Keine Unterkunft ≤ 1 km zwischen km A und km B"`.
    - Ziel der DP: Summe von `(length_km − target_km)²` minimal über alle Tage; Gleichstand → kleinere `dist_m`, dann kleinere `lodging_id`.
    - Letzter Tag endet an einer Unterkunft; erreicht der Weg vorher sein Ende, endet der Plan am Wegende (`stop=None`) und `notes` erhält „Ab <Start> bleiben X km bis <Ende> – N Tag(e) bei ~T km“; es werden **keine** zusätzlichen Tage erfunden.
    - Hm aus `profile` (Abschnitt zwischen `start_km` und `end_km`, linear interpoliert); `duration_h` = `din33466(length_km, ascent, descent).hours`; `arrival` = `start_time + duration_h`.
  - `change_day(plan, day: int, change: Literal["shorter", "longer"], stops, profile, trail_len_km) -> MultidayPlan`: Tage `< day` bleiben **unverändert**; Tag `day` endet an der nächst früheren (bzw. späteren) Unterkunft, die die Strecke um **mindestens 2 km** ändert; Folgetage werden mit demselben Ziel neu geplant, Anzahl der Tage bleibt gleich (reicht der Weg nicht, Note wie oben).
  - `rain_variant(day_plan, stations: list[StationOnTrail]) -> RainVariant | None`: letzter Bahnhof/Haltepunkt mit `along_km` zwischen Tagesstart und Tagesziel (≥ 3 km nach Start); `RainVariant(station_name, walk_km, ascent_m, duration_h, note="Weiter mit Bus/Bahn zur Unterkunft – Fahrplan bitte selbst prüfen.")`; keiner → `None` („Keine Haltestelle am Weg – Regenvariante nicht möglich“).
  - `load_trail_for_multiday(conn, trail_id) -> (stops, stations, profile, trail_len_km, name, source_ids)`.
  - `start_km_for(conn, trail_id, lat, lon) -> float | None` – Lot auf die Linie; > 2 km vom Weg → `None`.

- [ ] **Step 1: Tests** (reine Funktionen mit synthetischen Unterkünften, plus `@pytest.mark.db` für den Lader)

```python
def test_days_end_at_lodging_within_1km(): ...
def test_uses_2km_lodging_only_if_none_in_band_and_adds_access_twice(): ...
def test_gap_named_when_no_lodging(): ...
def test_plan_stops_at_trail_end():
    p = plan_multiday(stops, profile, trail_len_km=300, start_km=272, days=5)
    assert len(p.days) == 2 and p.days[-1].stop is None and "bleiben 28 km" in p.notes[0]
def test_change_day_keeps_earlier_days(): ...
def test_arrival_is_start_plus_din_time(): ...
def test_rain_variant_ends_at_station_or_none(): ...
@pytest.mark.db
def test_real_westweg_hausach_3_days(conn): ...   # 3 Tage, jede Unterkunft ≤ 1000 m oder offen benannt
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: deterministic multi-day planning on the Westweg`.

### Task 6: Mehrtageswünsche verstehen

**Files:**
- Modify: `backend/src/hikeall/agent/request.py`, `backend/src/hikeall/agent/understand.py`, `backend/src/hikeall/tags/vocabulary.py`
- Test: `backend/tests/test_understand.py`

**Interfaces:**
- Produces:
  - `HikeRequest` neu: `trail_id: str | None`, `days: int | None` (1–14), `day_km: float | None` (Tagesziel), `start_date: date | None`, `start_time: time | None`, `day_change: DayChange(day: int, change: Literal["shorter","longer"]) | None`. Intents neu: `"events"`, `"groups"`.
  - Fernweg-Tags im Vokabular: `trail:westweg-west` („Westweg“, „Westweg Westvariante“), `trail:westweg-ost` („Westweg Ostvariante“). Nur „Westweg“ → `westweg-west`, im „Verstanden“ als „Westweg (Westvariante – Ostvariante möglich)“.
  - Mehrtägig ohne Startort → `Clarify("Wo soll die Mehrtagestour starten?", Etappenorte des Westwegs)`; Startort > 2 km vom Weg → `Clarify("<Ort> liegt nicht am Westweg. Ab welchem Etappenort?", …)`; ohne Tage → `Clarify("Wie viele Tage?")`.
  - Datum: Zahlen/Monatsnamen aus der Nachricht, relativ zu „heute“ (Parameter `today`); R27 aus Plan 2 gilt auch hier (Datum nur, wenn es in der Nachricht steht).
  - „Tag 3 kürzer/länger“ → `intent="change"`, `day_change`; ohne vorherigen Mehrtagesplan → Clarify wie in Plan 2.
  - Unterkunftswünsche ohne Tag (z. B. „Halbpension“, „mit Sauna“) → `unmatched`.
  - Fragen nach Läufen („Halbmarathon im Juni bei Freiburg“) → `intent="events"` mit Ort/Monat/Distanzen in `question`; nach Gruppen („Lauftreff in Freiburg“) → `intent="groups"`.

- [ ] **Step 1: Tests:** `test_three_days_westweg_from_hausach`, `test_bare_westweg_is_west_variant_and_echo_says_so`, `test_start_off_trail_asks`, `test_day_change_needs_previous_plan`, `test_halbpension_unmatched`, `test_events_intent`, `test_groups_intent`, `test_date_only_if_written` (alle mit `FakeGateway`).
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: understand multi-day, event and group requests`.

### Task 7: Mehrtagesplan im Agenten, mit Wetter und Regenvariante

**Files:**
- Modify: `backend/src/hikeall/agent/graph.py`, `backend/src/hikeall/agent/tools.py`, `backend/src/hikeall/agent/prompts.py`, `backend/src/hikeall/agent/grounding.py`
- Test: `backend/tests/test_agent_graph.py`

**Interfaces:**
- Consumes: Tasks 4–6.
- Produces:
  - `AgentTools` neu: `plan_multiday(req) -> MultidayPlan`, `change_day(plan, day_change) -> MultidayPlan`, `weather(lat, lon, day) -> DayWeather | NoForecast`, `rain_variant(plan, day) -> RainVariant | None`; `DbTools` implementiert sie (Open-Meteo-Client injiziert).
  - `PlanEvent(type="plan", plan: MultidayPlan, weather: dict[int, DayWeather | NoForecast], rain: dict[int, RainVariant | None], labels)` – Regenvariante nur für Regentage (`is_rain_day` True); auf Nachfrage („Regenvariante für Tag 2“) für jeden Tag.
  - Der letzte Plan liegt im Thread-Zustand; `change` mit `day_change` arbeitet darauf (Spec §8.7).
  - Antwort: Code stellt voran: Lücken, Zuwege, Wegende-Notiz, „Zeiten ohne Pausen“; das Modell formuliert nur aus `PlanEvent`-Daten. Grounding-Evidenz: alle Zahlen aus Plan, Wetter, Regenvariante; Temperaturen (°C) und Prozent als Einheiten erkannt.
  - Quellen-Ereignis: OSM (Weg, Unterkünfte), Schwarzwald-Tourismus-Etappen, Open-Meteo.
  - Die Plan-2-Antwort „Mehrtagestouren plane ich bald …“ entfällt.

- [ ] **Step 1: Tests** (FakeGateway, Fake-Tools): `test_multiday_flow_events_in_order` (understood → plan → token… → sources → done), `test_day_change_keeps_earlier_days_across_turns`, `test_rain_day_gets_variant`, `test_no_forecast_beyond_14_days_is_stated`, `test_invented_temperature_removed`, `test_gap_sentence_prefixed_by_code`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: multi-day plans with weather and rain variant in the agent`.

### Task 8: Mehrtagesplan im Web

**Files:**
- Create: `web/src/components/PlanDays.tsx`, `web/src/app/plan/page.tsx` (Anzeige eines gespeicherten Plans aus `saved_plans`)
- Modify: `web/src/lib/chat.ts` (Typen `PlanEvent`), `web/src/components/ChatMessages.tsx`, `web/src/components/MapPanel.tsx`
- Test: `web/src/components/PlanDays.test.tsx`, `web/src/lib/chat.test.ts` (Vertragstest mit Backend-Fixture wie Plan 2)

**Interfaces:**
- Produces: Tageskarten (Spec §10): „Tag N · Datum“, Strecke Start → Unterkunft, km, Hm, Zeit + Ankunft („ohne Pausen“), Unterkunft (Name, Art, Abstand zum Weg, Website-Link oder Suche „<Name> <Ort>“), Wetter (Text, min/max °C, Regen % / mm, Quelle Open-Meteo) oder „Noch keine Vorhersage“; Lücke/Zuweg als Hinweis; Regenvariante aufklappbar. Karte zeigt die Tagesabschnitte in abwechselnden Farben mit Unterkunftsmarkern. „Merken“ (Task 3). Fehlende Zahl → „unbekannt“.

- [ ] **Step 1: Tests:** `renders days with arrival and 'ohne Pausen'`, `shows gap note`, `shows 'Noch keine Vorhersage'`, `rain variant collapsible`, `contract fixture parses`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS (`npm test`, tsc, lint).
- [ ] **Step 5:** Commit `feat: multi-day plan cards and map`.

### Task 9: Eigene Fotos hochladen

**Files:**
- Create: `supabase/migrations/20261030000002_uploads.sql`, `web/src/lib/photo.ts`, `web/src/components/PhotoUpload.tsx`
- Modify: `web/src/components/PhotoSwitcher.tsx`, `web/src/app/t/[trailId]/page.tsx`, `web/src/lib/data.ts`
- Test: `backend/tests/test_uploads_rls.py` (`@pytest.mark.db`), `web/src/lib/photo.test.ts`, `web/src/components/PhotoUpload.test.tsx`

**Interfaces:**
- Produces:
  - Storage-Bucket `uploads` (privat); Policies: Lesen/Schreiben/Löschen nur unter Pfad `<auth.uid()>/…`. Tabelle `photos`: Policy `photos_owner` (select/insert/delete für `source='upload' and owner = auth.uid()`), `owner` default `auth.uid()`; `author` = „Eigenes Foto“, `license` = „privat“.
  - `prepareUpload(file: File) -> Promise<Blob>`: Typprüfung (JPEG/PNG/WebP; HEIC → „HEIC wird nicht unterstützt – bitte als JPEG exportieren“), > 10 MB → „Foto ist größer als 10 MB“; Neukodierung über Canvas als JPEG (Qualität 0.85, längste Seite ≤ 2560 px) – entfernt EXIF.
  - Upload-Pfad `<user_id>/<trail_id>/<uuid>.jpg`; Anzeige über signierte URLs (1 h); eigene Fotos erscheinen nur für den Eigentümer im PhotoSwitcher und können als Hintergrund gewählt und gelöscht werden.

- [ ] **Step 1: Tests**

```ts
it("strips exif before upload", ...)   // JPEG-Fixture mit GPS-EXIF → Ergebnis enthält kein APP1/Exif
it("rejects heic and oversized", ...)
it("upload button only with session", ...)
```
```python
@pytest.mark.db
def test_other_user_cannot_see_upload(conn): ...
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5: Echter Check:** angemeldet ein Foto mit GPS-EXIF hochladen, die gespeicherte Datei herunterladen und mit `exiftool` bzw. Python prüfen: keine GPS-Tags (Ergebnis im Bericht).
- [ ] **Step 6:** Commit `feat: private photo uploads without location data`.

### Task 10: PWA und „Unterwegs“

**Files:**
- Create: `web/public/manifest.webmanifest`, `web/public/sw.js`, `web/public/icons/icon-192.png`, `icon-512.png`, `web/src/lib/geo.ts`, `web/src/app/unterwegs/page.tsx`, `web/src/components/Unterwegs.tsx`
- Modify: `web/src/app/layout.tsx` (Manifest, Theme-Farbe, SW-Registrierung), `README.md` (Abschnitt „Auf dem Handy (HTTPS-Tunnel)“ mit `cloudflared tunnel --url http://localhost:3000`)
- Test: `web/src/lib/geo.test.ts`, `web/src/components/Unterwegs.test.tsx`

**Interfaces:**
- Produces:
  - `progressOnLine(line: [lat, lon][], pos: {lat, lon}) -> { alongKm, distToLineM, remainingKm }` (Lot auf nächstes Segment, Haversine).
  - `etaFromProfile(remainingKm, remainingAscentM, remainingDescentM, now: Date) -> Date` (DIN 33466 wie Backend, ohne Pausen).
  - `/unterwegs?trail=<id>` bzw. `?plan=<savedPlanId>&day=<n>`: Taste „Unterwegs starten“ → `navigator.geolocation.watchPosition` (nur solange die Seite offen ist; `clearWatch` beim Verlassen); zeigt Position auf der Karte, Restkilometer, Ankunft. > **200 m** vom Weg → „Du bist X km vom Weg entfernt – Restkilometer erst wieder am Weg“. Verweigert → „Standortfreigabe verweigert – in den Browser-Einstellungen erlauben“; nicht verfügbar/Zeitüberschreitung eigene Meldungen. Kein `fetch` mit Position (Test prüft das).
  - Service Worker cacht nur die App-Hülle (kein Kartenmaterial, keine API-Antworten), damit die App installierbar ist.

- [ ] **Step 1: Tests:** `progress on straight line`, `off-route over 200 m`, `eta uses DIN`, `denied permission message`, `never sends position` (fetch-Spy), `clears watch on unmount`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: installable PWA with on-the-trail view`.

### Task 11: Gruppenliste

**Files:**
- Create: `data/curated/groups.csv`, `supabase/migrations/20261030000003_groups.sql`, `backend/src/hikeall/ingest/groups.py`, `web/src/components/GroupList.tsx`
- Modify: `backend/src/hikeall/cli.py` (`import-groups`), `Makefile` (`groups`), `backend/src/hikeall/agent/tools.py`, `backend/src/hikeall/agent/graph.py`, `web/src/app/t/[trailId]/page.tsx`, `docs/superpowers/specs/2026-10-28-hike-all-about-design.md` (§3, siehe Global Constraints)
- Test: `backend/tests/test_groups.py`, `web/src/components/GroupList.test.tsx`

**Interfaces:**
- Produces:
  - CSV-Spalten: `id,name,kind,place,lat,lon,url,source_url,checked_at,status,note`; `kind` ∈ `wanderverein|lauftreff|alpenverein|sonstige`; `status` ∈ `vorschlag|geprüft`.
  - Inhalt: 20–40 Gruppen im Schwarzwald (Schwarzwaldverein-Ortsgruppen, Lauftreffs, DAV-Sektionen), vom Implementierer **nur aus der eigenen Seite der Gruppe** übernommen: `url` antwortet mit HTTP 200 und der Name steht auf der Seite (Prüfung als Skript im Bericht); `status=vorschlag`, `note` beginnt mit „Vorschlag Claude:“ – der Nutzer prüft sie (wie die Tagestouren in Plan 1). Koordinate = Ortsmitte aus `places`, nicht geraten.
  - Tabelle `groups` (öffentlich lesbar, RLS select für anon/authenticated); `import_groups(conn, rows)` validiert Pflichtfelder und Art.
  - `find_groups(lat, lon, radius_km=25, kind=None) -> list[GroupBrief(name, kind, place, url, checked_at, stale: bool, dist_km)]` (≤ 10, nach Abstand); `stale` = Prüfdatum älter als 180 Tage.
  - Intent `groups` → `GroupsEvent(groups, checked_note="Stand: <ältestes Prüfdatum>")`; Antwort ohne Termine, ohne Personen. Tourseite zeigt „Gruppen in der Nähe“.

- [ ] **Step 1: Tests:** `test_csv_rejects_unknown_kind`, `test_stale_after_180_days`, `test_find_groups_sorted_by_distance` (db), `test_groups_intent_flow`; web `shows Stand and marks veraltet`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren, Liste erstellen. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: curated list of hiking and running groups nearby`.

### Task 12: Offizielle Läufe live suchen

**Files:**
- Create: `backend/src/hikeall/adapters/web_search.py`, `backend/src/hikeall/adapters/page_fetch.py`, `backend/src/hikeall/agent/events.py`, `data/events/calendars.yaml`, `web/src/components/EventCards.tsx`
- Modify: `backend/src/hikeall/agent/graph.py`, `backend/src/hikeall/agent/tools.py`, `backend/pyproject.toml` (beautifulsoup4, protego)
- Test: `backend/tests/test_events.py`, `backend/tests/fixtures/race_page_*.html`, `web/src/components/EventCards.test.tsx`

**Interfaces:**
- Produces:
  - `WebSearch` Protocol `search(query: str, k: int = 5) -> list[SearchHit(url, title)]`; `OpenRouterWebSearch(gateway)`: ein Aufruf mit Plugin `{"id": "web", "engine": "exa", "max_results": 5, "exclude_domains": BLOCKED_DOMAINS}`, Treffer aus `message.annotations[].url_citation`; Kosten über `record_usage`.
  - `BLOCKED_DOMAINS = ["laufen.de", "marathon.de", "d-u-v.org", "ultra-marathon.org", "ladv.de", "hdsports.org"]` – zusätzlich im Code gefiltert (auch Subdomains).
  - `fetch_page(http, url) -> PageText(url, text, fetched_at)`; `robots.txt` per protego (Disallow → übersprungen, Grund im Bericht); nur `text/html`; > 1 MB oder > 10 s → übersprungen. HTML → Text mit beautifulsoup4 (Skripte/Styles entfernt, Leerraum normalisiert).
  - `extract_race(gw, page) -> RaceInfo`: strukturierte Ausgabe mit `Field(value: str | None, quote: str | None)` je Feld `name, date, place, distances, registration_url, registration_deadline, fee`; `verify(race, page) -> RaceInfo`: ein Feld bleibt nur, wenn `quote` (Leerraum-normalisiert, Groß/klein egal) im Seitentext steht und der Wert im Zitat vorkommt (Daten: gleicher Tag nach Parse; Links: URL steht im HTML der Seite); sonst `value=None` → Anzeige „nicht angegeben“.
  - `find_events(query, today) -> EventsResult(events: list[VerifiedRace], fallback: list[CalendarLink], searched_at)`: höchstens 3 Seiten; Läufe ohne verifiziertes Datum oder mit Datum < `today` werden nicht gezeigt; keine Läufe → `fallback` aus `data/events/calendars.yaml` (BLV „Veranstaltungstermine“ `https://www.blv-online.de/laeufe/veranstaltungstermine`, WLV `https://www.wlv-sport.de/home/breitensport/laufveranstaltungen/veranstaltungstermine`, Schwarzwald Tourismus `https://www.schwarzwald-tourismus.info/veranstaltungen`, laufen.de-Laufkalender `https://www.laufen.de/laufkalender` – nur als Link).
  - Intent `events` → `EventsEvent(events, fallback, note="Angaben ohne Gewähr – bitte beim Veranstalter prüfen. Gesucht am <Datum>.")`; jede Angabe im Web mit Link zur Quellseite; nichts wird gespeichert.

- [ ] **Step 1: Tests** (Fake-Suche, respx-Seiten, FakeGateway)

```python
def test_field_without_quote_is_not_given(): ...          # Gebühr ohne Zitat → None
def test_quote_must_occur_on_page(): ...                  # erfundenes Zitat → None
def test_blocked_domains_never_fetched(respx_mock): ...   # auch www.laufen.de, sub.hdsports.org
def test_robots_disallow_skips_page(respx_mock): ...
def test_past_events_hidden(): ...
def test_no_results_gives_calendar_links(): ...
def test_at_most_three_pages_fetched(respx_mock): ...
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5: Echter Lauf** (kostet < 0,05 USD): „Halbmarathon im nächsten Frühjahr bei Freiburg“ – Bericht: gefundene URLs, verifizierte Felder, „nicht angegeben“-Felder, Kosten.
- [ ] **Step 6:** Commit `feat: live search for official running events with quoted sources`.

### Task 13: Wikivoyage-Rauschen, Durchstich und Doku

**Files:**
- Modify: `backend/src/hikeall/knowledge/corpus.py`, `data/smoke/prompts.yaml`, `backend/src/hikeall/smoke.py`, `README.md`
- Test: `backend/tests/test_knowledge.py`, `backend/tests/test_smoke.py`

**Interfaces:**
- Produces:
  - Wikivoyage-Abschnitte ohne Telefonnummern (`Tel.`, `+49 …`), Koordinaten (`47.9, 8.1`-Paare, `lat=`/`long=`) und Listing-Reste; Test mit echtem Ausschnitt-Fixture; Index neu bauen.
  - Testnutzer: `make smoke-user` legt lokal `smoke@hikeall.local` mit Passwort aus `HIKEALL_SMOKE_PASSWORD` (`.env`, nicht eingecheckt; Platzhalter in `.env.example`) über die lokale Supabase-Auth an; der Smoke-Lauf meldet sich damit an und ruft den Graphen mit derselben Prüfung wie `/chat` auf.
  - Smoke-Fälle: (7) „3 Tage Westweg ab Hausach, ~15 km pro Tag“ → `plan` mit 3 Tagen, jede Unterkunft ≤ 1000 m oder Lücke/Zuweg benannt, Tagesstrecken im Band oder `within_band=False` benannt; (8) Folgerunde „Tag 3 kürzer“ → Tage 1–2 unverändert, Tag 3 kürzer; (9) „Lauftreff in Freiburg“ → ≥ 1 Gruppe mit Prüfdatum; (10) „Halbmarathon im Frühjahr bei Freiburg“ → Läufe mit Quelle **oder** Kalender-Links, nie ein Feld ohne Zitat. Alle bisherigen Fälle 1–6 bleiben unverändert (Fall 6 erwartet jetzt einen Plan statt des Hinweises – Erwartung wird auf „plan mit 3 Tagen“ umgestellt, im Bericht begründet).
  - README: Abschnitte „Konto anlegen“, „Mehrtagestour“, „Auf dem Handy (HTTPS-Tunnel)“, „Gruppen und Läufe“ (Quellenpflicht, keine Speicherung, ausgeschlossene Portale).
- [ ] **Step 1:** Tests für Rauschfilter und neue Smoke-Erwartungen. **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5: Echter Lauf:** `make smoke` – alle Fälle ok, 0 unbelegte Zahlen, Gesamtkosten < 0,15 USD; CSV committen. Fällt ein Fall durch: Ursache im Bericht, Erwartung nicht lockern.
- [ ] **Step 6:** Commit `feat: smoke cases for multi-day, groups and events; docs`.
