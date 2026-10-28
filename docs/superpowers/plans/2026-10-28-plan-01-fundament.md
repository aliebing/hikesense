# Plan 1 – Fundament: Daten im Schwarzwald + Panorama-Oberfläche

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Befehl startet Supabase, API und Web lokal; ein Import füllt die Datenbank mit Westweg (Etappen, Höhen), geprüften Tagestouren, Unterkünften und Commons-Bildern; die Web-App zeigt Layout A (Panorama-Bild, Chat-Hülle, Etappenkarten, aufklappbare Karte) mit echten Daten.

**Architecture:** Python-Paket `hikeall` (uv) enthält Import-Pipeline und eine FastAPI-App (in Plan 1 nur `/health`). Supabase (lokal per CLI) hält alle Daten in Postgres/PostGIS; Lesezugriff öffentlich über RLS. Next.js (App Router) liest direkt aus Supabase. Der Agent folgt in Plan 2.

**Tech Stack:** Python 3.12, uv, httpx, psycopg 3, pydantic, FastAPI, pytest + respx · Supabase CLI (`npx supabase`), PostGIS · Next.js 15, TypeScript, Tailwind, maplibre-gl, @supabase/supabase-js, vitest + Testing Library · Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-28-hike-all-about-design.md`

**Folgepläne (nicht hier):** Plan 2 Agent + Chat (Tagestouren, Bedingungen, Ausweichen, Grounding, ChromaDB-Wissen) · Plan 3 Mehrtagestour, Wetter, Regenvariante, Auth, gespeicherte Touren, Uploads, PWA „Unterwegs" · Plan 4 Mittel-/Ostweg, Evaluation, README, Ethik, Präsentation.

## Global Constraints

- Nur Schwarzwald. Import-Bounding-Box: `south=47.55, west=7.55, north=48.95, east=8.75`.
- Jede Daten-Zeile trägt `source_id` → Tabelle `sources(id, name, url, license, retrieved_at)`.
- Keine Daten von Komoot, AllTrails, Booking.com. Keine Texte von Etappenseiten kopieren, nur Fakten (Orte, km) mit Quell-Link.
- Die App fragt OSM/Overpass/Commons **nie zur Laufzeit** ab; nur die Import-Skripte tun das.
- Unterkünfte: OSM `tourism` ∈ {`hotel`, `guest_house`, `hostel`, `alpine_hut`, `wilderness_hut`, `chalet`, `apartment`, `camp_site`}, Import-Puffer **2 km** um jeden Weg.
- Bild ohne Urheber oder Lizenz wird nicht gespeichert. Attribution (Urheber, Lizenz, Link) wird überall angezeigt, wo das Bild erscheint.
- Karten-Attribution sichtbar: „© BKG (basemap.de) CC BY 4.0" und „© OpenStreetMap-Mitwirkende, ODbL".
- UI-Texte Deutsch.
- Tests laufen ohne Netz und ohne API-Kosten (HTTP über respx/Fixtures). DB-Tests sind mit `@pytest.mark.db` markiert und werden übersprungen, wenn `SUPABASE_DB_URL` nicht erreichbar ist.
- **Abweichung vom Spec, bewusst:** Höhen in Plan 1 aus Copernicus GLO-30 (Adapter aus HikeAI, Lizenz: frei mit Nennung „© DLR/ESA Copernicus"), hinter einer Schnittstelle `ElevationProvider`. Umstieg auf LGL-DGM ist ein eigener Schritt in Plan 4, falls Zeit bleibt.

## Review Focus

1. **OSM-Relation mit Lücken oder ungeordneten Teilstücken** (HikeAI kannte das): Der Import darf keine Sprünge quer übers Land als Weg speichern → Lücken > 200 m brechen den Import dieses Weges mit klarer Meldung ab (Task 3).
2. **Etappen-Endpunkt liegt weit neben dem Weg** (Tippfehler in Koordinaten): > 500 m Abstand → Import bricht mit Etappenname ab (Task 4).
3. **Wiederholter Import**: zweiter Lauf darf keine Duplikate erzeugen und keine manuell verworfenen Tagestouren wieder aufnehmen (Tasks 5, 6).
4. **Commons-Bild ohne Lizenzangabe** oder Overpass-Timeout/429: Bild wird übersprungen; Overpass wird mit Backoff erneut versucht, danach klarer Fehler statt halbem Import (Tasks 5, 8).
5. **Web ohne Daten oder ohne Supabase**: leere DB oder fehlende Env-Variablen zeigen eine verständliche Meldung, kein weißer Bildschirm; Weg ohne Bilder zeigt einen Farbverlauf statt kaputtem Hintergrund (Task 10).

---

## Dateistruktur

```
HikeAllAbout/
├── Makefile                      # up, down, import, test
├── docker-compose.yaml           # api, web (Supabase läuft über CLI)
├── .env.example
├── backend/
│   ├── pyproject.toml            # Paket hikeall, CLI-Einstieg "hikeall"
│   ├── Dockerfile
│   ├── src/hikeall/
│   │   ├── config.py             # Settings aus Env
│   │   ├── geo.py                # aus HikeAI kopiert + line_locate
│   │   ├── hiking_time.py        # aus HikeAI kopiert (DIN 33466)
│   │   ├── models.py             # pydantic: Trail, Stage, Lodging, Photo, Source
│   │   ├── adapters/http.py, overpass.py, dem.py, commons.py   # aus HikeAI kopiert
│   │   ├── ingest/assemble.py    # Teilstücke → eine geordnete Linie
│   │   ├── ingest/stages.py      # Linie in Etappen schneiden
│   │   ├── ingest/elevation.py   # Profil + Hm auf/ab
│   │   ├── ingest/trails.py      # Fernwege importieren
│   │   ├── ingest/day_hikes.py   # Kandidaten + Kuration
│   │   ├── ingest/lodgings.py    # Unterkünfte
│   │   ├── ingest/photos.py      # Commons-Bilder
│   │   ├── db.py                 # psycopg-Verbindung, Upserts
│   │   ├── cli.py                # hikeall import-trails|import-day-hikes|...
│   │   └── api/app.py            # FastAPI, /health
│   └── tests/ (+ tests/fixtures/*.json)
├── data/curated/
│   ├── trails.yaml               # Westweg: OSM-Relationen, Etappen, Quelle
│   └── day_hikes.csv             # Kurationsentscheidungen
├── supabase/                     # supabase init + migrations/
└── web/                          # Next.js
```

---

### Task 1: Gerüst Backend + übernommene Helfer

**Files:**
- Create: `backend/pyproject.toml`, `backend/src/hikeall/{__init__,config,geo,hiking_time,models}.py`, `backend/src/hikeall/adapters/{__init__,http,overpass,dem,commons}.py`, `.env.example`, `Makefile`
- Test: `backend/tests/test_geo.py`, `backend/tests/test_hiking_time.py`

**Interfaces:**
- Produces:
  - `geo.haversine_km(a: Point, b: Point) -> float`, `geo.path_length_km(segments) -> float` (aus `~/projects/HikeAi2/src/hikeai/domain/geo.py`), neu `geo.locate(line: list[Point], p: Point) -> tuple[int, float]` = (Index des nächsten Stützpunkts, Abstand in m).
  - `hiking_time.din33466(distance_km, ascent_m, descent_m) -> HikingTime` (aus `~/projects/HikeAi2/src/hikeai/domain/hiking_time.py`, `HikingTime` nach `models.py`).
  - `models.Source(id: str, name: str, url: str, license: str, retrieved_at: date)`.
  - `config.Settings` mit `supabase_db_url: str`, `overpass_url: str`, `dem_cache_dir: Path` (Default `data/dem`).
  - Adapter `OverpassClient`, `CopernicusDem`, `CommonsClient`, `make_http_client` unverändert aus HikeAI (`src/hikeai/adapters/`), Imports auf `hikeall` umgestellt.

- [ ] **Step 1:** Abhängigkeiten in `backend/pyproject.toml`: `httpx, pydantic, pydantic-settings, pyyaml, psycopg[binary], fastapi, uvicorn, tifffile, imagecodecs`; dev: `pytest, respx, ruff`. `[project.scripts] hikeall = "hikeall.cli:main"`. `uv sync` läuft durch.
- [ ] **Step 2: Tests schreiben** – HikeAI-Tests zu `geo` und `hiking_time` übernehmen (`~/projects/HikeAi2/tests/` nach passenden Dateien suchen) plus:

```python
def test_locate_returns_nearest_vertex_and_distance_m():
    line = [(48.0, 8.0), (48.0, 8.01), (48.0, 8.02)]
    idx, dist_m = locate(line, (48.0005, 8.0101))
    assert idx == 1
    assert 50 < dist_m < 60
```

- [ ] **Step 3:** `uv run pytest -q` → FAIL (Module fehlen). Dann Dateien kopieren/anpassen, `locate` implementieren (linear über Stützpunkte, Haversine).
- [ ] **Step 4:** `uv run pytest -q` → PASS; `uv run ruff check` sauber.
- [ ] **Step 5:** `.env.example` mit `SUPABASE_URL=http://127.0.0.1:54321`, `SUPABASE_ANON_KEY=`, `SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`, `OPENROUTER_API_KEY=`. `Makefile` mit Zielen `test` (`cd backend && uv run pytest -q`). Commit `chore: backend skeleton with helpers from HikeAI`.

### Task 2: Supabase-Schema

**Files:**
- Create: `supabase/` via `npx supabase init`, `supabase/migrations/20261028000001_schema.sql`, `backend/src/hikeall/db.py`
- Test: `backend/tests/test_schema.py` (`@pytest.mark.db`), `backend/tests/conftest.py`

**Interfaces:**
- Produces Tabellen (alle Geometrien SRID 4326):
  - `sources(id text pk, name text, url text, license text, retrieved_at date)`
  - `trails(id text pk, name text, kind text check in ('long_distance','day_hike'), roundtrip boolean, osm_relation_id bigint, length_km numeric, ascent_m int, descent_m int, profile jsonb, geom geometry(LineString,4326), source_id text fk)`
  - `stages(id text pk, trail_id text fk, seq int, name text, start_name text, end_name text, length_km numeric, ascent_m int, descent_m int, profile jsonb, geom geometry(LineString,4326), source_id text fk, unique(trail_id, seq))`
  - `lodgings(id bigint pk /* OSM node/way id, ways negativ */, name text, kind text, website text, geom geometry(Point,4326), source_id text fk)`
  - `trail_lodgings(trail_id text fk, lodging_id bigint fk, dist_m int, along_km numeric, pk(trail_id, lodging_id))`
  - `photos(id bigserial pk, trail_id text fk, stage_id text null fk, source text check in ('commons','upload'), url text, thumb_url text, author text not null, license text not null, license_url text, page_url text, geom geometry(Point,4326), owner uuid null, unique(trail_id, url))`
  - `profile` = JSON-Array `[[km, höhe_m], …]`, max. 300 Punkte.
  - RLS: auf allen Tabellen aktiviert; Policy `select` für `anon` und `authenticated` auf allen außer `photos` mit `source='upload'` (die bleiben in Plan 1 ungenutzt).
- Produces `db.connect(url: str) -> psycopg.Connection`, `db.upsert_source(conn, Source) -> None`.

- [ ] **Step 1: Test schreiben**

```python
@pytest.mark.db
def test_schema_has_tables_and_postgis(conn):
    names = {r[0] for r in conn.execute(
        "select table_name from information_schema.tables where table_schema='public'")}
    assert {"sources","trails","stages","lodgings","trail_lodgings","photos"} <= names
    assert conn.execute("select postgis_version()").fetchone()[0]

@pytest.mark.db
def test_anon_can_read_trails(conn):
    conn.execute("set role anon")
    conn.execute("select count(*) from trails")  # darf nicht werfen
```

`conftest.py`: Fixture `conn` verbindet mit `SUPABASE_DB_URL`, überspringt bei Verbindungsfehler, rollt jede Transaktion zurück.
- [ ] **Step 2:** `npx supabase start` und `uv run pytest -m db -q` → FAIL (Tabellen fehlen).
- [ ] **Step 3:** Migration schreiben (`create extension if not exists postgis;` zuerst), `npx supabase db reset`.
- [ ] **Step 4:** `uv run pytest -m db -q` → PASS. Makefile-Ziele `up` (`npx supabase start && docker compose up -d`) und `down`.
- [ ] **Step 5:** Commit `feat: supabase schema for trails, stages, lodgings, photos`.

### Task 3: Teilstücke einer OSM-Relation zu einer Linie verbinden

**Files:**
- Create: `backend/src/hikeall/ingest/assemble.py`
- Test: `backend/tests/test_assemble.py`

**Interfaces:**
- Produces `assemble(segments: list[list[Point]], max_gap_m: float = 200) -> list[Point]`; wirft `GapError(gap_m: float, at: Point)` wenn zwei Teilstücke nicht verbindbar sind.

Algorithmus (vom Test nicht vollständig festgelegt):
```
start = Teilstück, dessen Anfangs- oder Endpunkt am weitesten von allen anderen Endpunkten entfernt ist
kette = start (ggf. umgedreht, sodass das freie Ende vorn liegt)
solange Teilstücke übrig:
    nimm das Teilstück, dessen Anfang ODER Ende dem Kettenende am nächsten ist
    falls Abstand > max_gap_m: GapError
    ggf. umdrehen, anhängen (doppelten Verbindungspunkt weglassen)
```

- [ ] **Step 1: Tests**

```python
def test_reversed_and_shuffled_segments_become_one_line():
    a = [(48.0, 8.00), (48.0, 8.01)]
    b = [(48.0, 8.02), (48.0, 8.01)]   # umgedreht
    c = [(48.0, 8.02), (48.0, 8.03)]
    line = assemble([c, a, b])
    assert line in ([(48.0, 8.00), (48.0, 8.01), (48.0, 8.02), (48.0, 8.03)],
                    [(48.0, 8.03), (48.0, 8.02), (48.0, 8.01), (48.0, 8.00)])

def test_gap_over_limit_raises():
    with pytest.raises(GapError) as e:
        assemble([[(48.0, 8.00), (48.0, 8.01)], [(48.0, 8.02), (48.0, 8.03)]])  # ~740 m Lücke
    assert e.value.gap_m > 700
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: assemble OSM relation segments into one ordered line`.

### Task 4: Etappen schneiden + Höhen

**Files:**
- Create: `backend/src/hikeall/ingest/stages.py`, `backend/src/hikeall/ingest/elevation.py`, `data/curated/trails.yaml`
- Test: `backend/tests/test_stages.py`, `backend/tests/test_elevation.py`

**Interfaces:**
- Consumes: `geo.locate`, `geo.path_length_km`, `CopernicusDem.elevations(points) -> list[float | None]`.
- Produces:
  - `models.StageSpec(seq: int, start_name: str, end_name: str, start: Point, end: Point)`; `models.TrailSpec(id: str, name: str, kind: str, osm_relation_ids: list[int], source: Source, stages: list[StageSpec])`.
  - `load_trail_specs(path: Path) -> list[TrailSpec]`.
  - `cut_stages(line: list[Point], specs: list[StageSpec], max_offset_m: float = 500) -> list[list[Point]]`; wirft `StageOffsetError(seq, start_name|end_name, offset_m)`.
  - `elevation_stats(line: list[Point], provider: ElevationProvider, step_m: float = 50) -> ElevationStats(ascent_m: int, descent_m: int, profile: list[tuple[float, float]])`; `ElevationProvider` = Protocol mit `elevations(points) -> list[float | None]`.

Hm-Berechnung: Linie alle 50 m neu abtasten, Höhen holen, gleitender Mittelwert über 5 Punkte, dann nur Anstiege/Abstiege > 0 summieren. Fehlende Höhen (`None`) → `ElevationStats` wirft `ValueError` (nie raten, wie in HikeAI). Profil auf ≤ 300 Punkte ausdünnen.

`trails.yaml`: Einträge `westweg-west` und `westweg-ost` (Pforzheim–Basel, Westvariante und Ostvariante). OSM-Relation-IDs per Overpass (`relation["route"="hiking"]["name"~"Westweg"]` in der Bounding-Box) ermitteln und eintragen. Etappen (seq, Start-/Zielort mit Koordinate des Ortskerns oder Etappenstarts) aus der öffentlichen Etappeneinteilung übertragen; Quelle = diese Seite mit URL, Lizenz `Fakten, keine Texte übernommen`, plus Source `osm` (ODbL) für die Geometrie. Beide Quellen im YAML.

- [ ] **Step 1: Tests**

```python
LINE = [(48.0, 8.0 + i * 0.001) for i in range(101)]   # ~7,4 km Gerade

def test_cut_stages_splits_at_nearest_points():
    specs = [StageSpec(1, "A", "B", (48.0, 8.0), (48.0, 8.05)),
             StageSpec(2, "B", "C", (48.0, 8.05), (48.0, 8.1))]
    parts = cut_stages(LINE, specs)
    assert len(parts) == 2 and parts[0][-1] == parts[1][0] == (48.0, 8.05)

def test_stage_endpoint_far_from_line_raises():
    specs = [StageSpec(1, "A", "Irgendwo", (48.0, 8.0), (48.1, 8.05))]  # ~11 km daneben
    with pytest.raises(StageOffsetError, match="Irgendwo"):
        cut_stages(LINE, specs)

class Ramp:  # steigt 1 m je 10 m Strecke
    def elevations(self, pts): return [ (p[1] - 8.0) * 7400 for p in pts ]

def test_elevation_stats_on_ramp():
    s = elevation_stats(LINE, Ramp())
    assert 700 <= s.ascent_m <= 760 and s.descent_m == 0 and len(s.profile) <= 300

def test_missing_elevation_raises():
    class Hole:
        def elevations(self, pts): return [None] * len(pts)
    with pytest.raises(ValueError):
        elevation_stats(LINE, Hole())

def test_trails_yaml_is_complete():
    specs = load_trail_specs(Path("../data/curated/trails.yaml"))
    ids = {t.id for t in specs}
    assert {"westweg-west", "westweg-ost"} <= ids
    for t in specs:
        assert t.osm_relation_ids and t.source.url and t.stages
        assert [s.seq for s in t.stages] == list(range(1, len(t.stages) + 1))
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren und `trails.yaml` füllen. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: cut trails into official stages and compute elevation`.

### Task 5: Fernwege importieren

**Files:**
- Create: `backend/src/hikeall/ingest/trails.py`, `backend/src/hikeall/cli.py`, `backend/tests/fixtures/overpass_relation_small.json`
- Modify: `backend/src/hikeall/db.py`
- Test: `backend/tests/test_import_trails.py`

**Interfaces:**
- Consumes: `OverpassClient.run(query) -> dict`, `assemble`, `cut_stages`, `elevation_stats`, `load_trail_specs`, `db.upsert_source`.
- Produces:
  - `relation_segments(data: dict) -> list[list[Point]]` (Overpass-JSON mit `out geom` → Teilstücke; Logik aus HikeAI `ingest/routes.py::_parse_relation` übernehmen).
  - `import_trail(conn, spec: TrailSpec, overpass: OverpassClient, dem: ElevationProvider) -> ImportReport(trail_id, length_km, stages: int)`; Upsert in `trails` und `stages` (`on conflict do update`), Stage-IDs `"{trail_id}-{seq:02d}"`.
  - CLI: `hikeall import-trails [--only ID]` gibt je Weg eine Zeile `westweg-west: 285.3 km, 12 Etappen` aus; bei `GapError`/`StageOffsetError` Meldung mit Weg-ID und Exit-Code 1.

- [ ] **Step 1: Tests** (respx liefert das Fixture; `Ramp` aus Task 4 nach `tests/conftest.py` verschieben, damit beide Tests ihn nutzen)

```python
@pytest.mark.db
def test_import_trail_writes_trail_and_stages(conn, small_spec, overpass_fixture):
    rep = import_trail(conn, small_spec, overpass_fixture, Ramp())
    assert rep.stages == len(small_spec.stages)
    row = conn.execute("select length_km, source_id from trails where id=%s", [small_spec.id]).fetchone()
    assert row[0] > 0 and row[1]

@pytest.mark.db
def test_reimport_is_idempotent(conn, small_spec, overpass_fixture):
    import_trail(conn, small_spec, overpass_fixture, Ramp())
    import_trail(conn, small_spec, overpass_fixture, Ramp())
    assert conn.execute("select count(*) from stages where trail_id=%s", [small_spec.id]).fetchone()[0] \
        == len(small_spec.stages)
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5: Echter Lauf:** `uv run hikeall import-trails` gegen lokale Supabase. Erwartet: beide Westweg-Varianten importiert, Länge je Variante zwischen 250 und 300 km (offizielle Angabe ~285 km), keine Ausnahme. Abweichungen > 5 % zur offiziellen Etappenlänge in der Ausgabe als Warnung auflisten (diese Liste ist später Teil des OSM-Abgleichs in der Evaluation).
- [ ] **Step 6:** Commit `feat: import Westweg with stages and elevation`.

### Task 6: Tagestouren-Kandidaten und Kuration

**Files:**
- Create: `backend/src/hikeall/ingest/day_hikes.py`, `data/curated/day_hikes.csv`
- Modify: `backend/src/hikeall/cli.py`
- Test: `backend/tests/test_day_hikes.py`

**Interfaces:**
- Produces:
  - `auto_decision(name: str | None, length_km: float, gap_error: bool, network: str | None) -> tuple[str, str]` → (`accepted`|`rejected`, Grund). Regeln: ohne Name → `rejected, "kein Name"`; Lücke → `"Lücken im Verlauf"`; `length_km` < 5 oder > 30 → `"Länge außerhalb 5–30 km"`; `network` = `iwn`/`nwn` (Fernweg) → `"Fernweg, kein Tagesziel"`; sonst `accepted, "automatisch"`.
  - CSV-Spalten: `osm_relation_id,name,length_km,roundtrip,auto_decision,auto_reason,manual_decision,manual_reason`. `manual_decision` (leer|`accepted`|`rejected`) gewinnt immer.
  - `hikeall scan-day-hikes`: Overpass in Kacheln (HikeAI `ingest/routes.py::tiles`) über die Bounding-Box, schreibt/ergänzt CSV; bestehende `manual_*`-Spalten bleiben unverändert.
  - `hikeall import-day-hikes`: importiert alle Zeilen mit Endentscheidung `accepted` als `trails` mit `kind='day_hike'`, Höhen über `elevation_stats`, `roundtrip` aus OSM-Tag oder Start-Ende-Abstand < 300 m.

- [ ] **Step 1: Tests**

```python
@pytest.mark.parametrize("args,expected", [
    ((None, 12, False, "lwn"), "rejected"),
    (("Rundweg A", 12, True, "lwn"), "rejected"),
    (("Rundweg A", 3.9, False, "lwn"), "rejected"),
    (("Westweg", 285, False, "iwn"), "rejected"),
    (("Rundweg A", 12, False, "lwn"), "accepted"),
])
def test_auto_decision(args, expected):
    assert auto_decision(*args)[0] == expected

def test_rescan_keeps_manual_decisions(tmp_path):
    csv = tmp_path / "d.csv"
    write_candidates(csv, [Candidate(1, "A", 10, True, "accepted", "automatisch")])
    set_manual(csv, 1, "rejected", "Weg gesperrt")
    write_candidates(csv, [Candidate(1, "A", 10.2, True, "accepted", "automatisch")])
    assert final_decision(read_candidates(csv)[0]) == ("rejected", "Weg gesperrt")
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5: Echter Lauf + Durchsicht von Hand:** `scan-day-hikes`, dann CSV durchsehen und `manual_decision` setzen, bis **50–150** Touren `accepted` sind, möglichst verteilt (Nord-, Mittel-, Südschwarzwald, mindestens 10 Rundwege < 400 Hm für spätere Evaluationsfälle). `import-day-hikes` läuft fehlerfrei.
- [ ] **Step 6:** Commit `feat: scan, curate and import day hikes`.

### Task 7: Unterkünfte

**Files:**
- Create: `backend/src/hikeall/ingest/lodgings.py`
- Modify: `backend/src/hikeall/cli.py`
- Test: `backend/tests/test_lodgings.py`

**Interfaces:**
- Produces:
  - `link_trail_lodgings(conn) -> int` (füllt `trail_lodgings` per SQL neu, gibt Zeilenzahl zurück).
  - `parse_lodgings(data: dict) -> list[Lodging]` (Nodes und Ways mit `out center`; Way-IDs negativ; nur die `tourism`-Werte aus Global Constraints; ohne `name` verworfen; `website` aus `website` oder `contact:website`).
  - `hikeall import-lodgings`: Upsert in `lodgings`, danach SQL füllt `trail_lodgings` für alle Paare mit Abstand ≤ 2000 m: `dist_m = ST_Distance(geography)`, `along_km = ST_LineLocatePoint(trail.geom, l.geom) * trail.length_km`.

- [ ] **Step 1: Tests**

```python
def test_parse_lodgings_keeps_named_relevant_kinds():
    data = {"elements": [
        {"type": "node", "id": 1, "lat": 48, "lon": 8, "tags": {"tourism": "guest_house", "name": "Pension A"}},
        {"type": "way", "id": 2, "center": {"lat": 48, "lon": 8}, "tags": {"tourism": "hotel", "name": "Hotel B", "contact:website": "https://b.de"}},
        {"type": "node", "id": 3, "lat": 48, "lon": 8, "tags": {"tourism": "museum", "name": "Museum"}},
        {"type": "node", "id": 4, "lat": 48, "lon": 8, "tags": {"tourism": "hotel"}},
    ]}
    ls = parse_lodgings(data)
    assert [(l.id, l.website) for l in ls] == [(1, None), (-2, "https://b.de")]

@pytest.mark.db
def test_trail_lodgings_within_2km(conn, trail_on_line_48_8):
    # Fixture: Weg entlang lat 48.0 von lon 8.00 bis 8.10, length_km 7.4
    insert_lodging(conn, id=101, lat=48.009, lon=8.05)   # ~1 km nördlich
    insert_lodging(conn, id=102, lat=48.027, lon=8.05)   # ~3 km nördlich
    link_trail_lodgings(conn)
    rows = conn.execute("select lodging_id, dist_m from trail_lodgings").fetchall()
    assert [r[0] for r in rows] == [101] and 900 < rows[0][1] < 1100
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5: Echter Lauf:** Ausgabe nennt Zahl der Unterkünfte und je Westweg-Etappe die Zahl mit `dist_m ≤ 1000`. Etappen mit 0 werden als Warnung gelistet (wichtig für Plan 3).
- [ ] **Step 6:** Commit `feat: import lodgings near trails`.

### Task 8: Commons-Bilder

**Files:**
- Create: `backend/src/hikeall/ingest/photos.py`
- Modify: `backend/src/hikeall/cli.py`
- Test: `backend/tests/test_photos.py`

**Interfaces:**
- Consumes: `CommonsClient.geosearch(lat, lon, radius_m, limit) -> list[str]`, `CommonsClient.image_infos(titles, width) -> list[ImageInfo]` (HikeAI).
- Produces:
  - `sample_points(line: list[Point], every_km: float) -> list[Point]` (Start, dann alle `every_km`).
  - `select_photos(infos: list[ImageInfo], limit: int) -> list[Photo]`: verwirft Bilder ohne Urheber oder Lizenz, Duplikate (gleiche URL) und Hochformat schmaler als 1,2:1 (Querformat für den Panorama-Hintergrund); Qualitätsfilter aus HikeAI `ingest/photo_quality.py` wiederverwenden, falls passend.
  - `hikeall import-photos`: Fernweg-Etappen: Punkte alle 3 km, Radius 1000 m, bis 8 Bilder je Etappe; Tagestouren: alle 2 km, bis 5 Bilder je Tour. Upsert über `unique(trail_id, url)`. Breite 1600 px für `url`, 400 px für `thumb_url`.

- [ ] **Step 1: Tests**

```python
def test_sample_points_every_km():
    pts = sample_points(LINE, every_km=2)          # LINE ~7,4 km aus Task 4
    assert len(pts) == 4 and pts[0] == LINE[0]

def test_select_photos_drops_missing_license_and_portrait():
    infos = [info(url="a", author="X", license="CC BY-SA 4.0", w=1600, h=900),
             info(url="b", author="", license="CC BY 4.0", w=1600, h=900),
             info(url="c", author="Y", license=None, w=1600, h=900),
             info(url="d", author="Z", license="CC0", w=900, h=1600),
             info(url="a", author="X", license="CC BY-SA 4.0", w=1600, h=900)]
    assert [p.url for p in select_photos(infos, limit=8)] == ["a"]
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren (respx-Fixture für einen Geosearch- und einen ImageInfo-Aufruf). **Step 4:** PASS.
- [ ] **Step 5: Echter Lauf:** Ausgabe: Bilder je Weg; Wege/Etappen ohne Bild als Liste.
- [ ] **Step 6:** Commit `feat: import Wikimedia Commons photos with attribution`.

### Task 9: API, Docker Compose, Start mit einem Befehl

**Files:**
- Create: `backend/src/hikeall/api/app.py`, `backend/Dockerfile`, `docker-compose.yaml`
- Modify: `Makefile`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `GET /health` → `{"status": "ok", "db": true|false}` (db = `select 1` gelingt). Port **8000**. Web-Port **3000**.
- Compose: Dienste `api` (uvicorn, Code als Volume für Reload) und `web` (`npm run dev`, Volume). Beide mit `extra_hosts: ["host.docker.internal:host-gateway"]`; in Containern zeigt `SUPABASE_DB_URL`/`SUPABASE_URL` auf `host.docker.internal`. Werte aus `.env`.
- Makefile: `up` (`npx supabase start` + `docker compose up -d --build`), `down`, `import` (alle Import-Befehle in Reihenfolge trails → day-hikes → lodgings → photos), `test` (Backend + Web).

- [ ] **Step 1: Test** `test_health_reports_db_false_without_db` (Settings mit unerreichbarer URL → `200`, `{"status":"ok","db":false}`).
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS.
- [ ] **Step 5:** `make up` → `curl -s localhost:8000/health` liefert `"db": true`.
- [ ] **Step 6:** Commit `chore: docker compose and one-command start`.

### Task 10: Web – Layout A mit echten Daten

**Files:**
- Create: `web/` via `npx create-next-app@15 web --ts --tailwind --app --eslint --src-dir --no-import-alias`, dann `web/src/lib/supabase.ts`, `web/src/lib/data.ts`, `web/src/lib/format.ts`, `web/src/components/{Panorama,ChatShell,StageCards,PhotoSwitcher,Attribution}.tsx`, `web/src/app/page.tsx`, `web/src/app/t/[trailId]/page.tsx`
- Test: `web/src/lib/format.test.ts`, `web/src/components/PhotoSwitcher.test.tsx`, `web/src/app/page.test.tsx` (vitest + Testing Library)

**Interfaces:**
- Consumes: Supabase-Tabellen aus Task 2 (anon key).
- Produces:
  - `data.ts`: `getTrails(): Promise<TrailSummary[]>`, `getTrail(id: string): Promise<TrailDetail | null>` (inkl. `stages` und `photos`), Typen `TrailSummary { id, name, kind, length_km, ascent_m }`, `TrailDetail = TrailSummary & { stages: Stage[]; photos: Photo[]; geom: GeoJSON.LineString }`, `Stage { id, seq, start_name, end_name, length_km, ascent_m, descent_m, geom }`, `Photo { url, thumb_url, author, license, license_url, page_url }`. Geometrie per Supabase-RPC oder View `trails_geojson` (in neuer Migration) als GeoJSON.
  - `format.ts`: `km(n) → "14,8 km"`, `hm(n) → "↑ 720 m"`, `duration(hours) → "5:10 h"`; Gehzeit im Web = gleiche DIN-Formel wie Backend (`din33466Hours(km, up, down)`), Test gegen HikeAI-Beispielwerte.
  - Seiten: `/` zeigt die Westweg-Varianten und eine Auswahl Tagestouren als Bildkarten über dem Panorama; `/t/[trailId]` = Layout A für einen Weg: Hintergrund = aktuelles Foto, oben links Titel „Hike all about", links das Chat-Fenster (Eingabe deaktiviert, Platzhalter „Der Planungs-Chat kommt bald"), unten Etappenkarten (Fernweg) bzw. eine Karte (Tagestour) mit km, Hm, Gehzeit; Pfeile/Vorschaubilder wechseln das Hintergrundbild; Attribution des aktuellen Fotos unten rechts.
  - Gestaltung wie Entwurf A (siehe Spec §10): Schwarzwaldgrün `#2f5d3a`, Papierweiß `#f4f1ea`, Serifenschrift für Titel, halbtransparentes Chat-Fenster mit Weichzeichner.

- [ ] **Step 1: Tests**

```ts
test("format", () => {
  expect(km(14.83)).toBe("14,8 km"); expect(hm(720)).toBe("↑ 720 m"); expect(duration(5.17)).toBe("5:10 h");
});
test("PhotoSwitcher cycles and shows attribution", async () => {
  render(<PhotoSwitcher photos={[p("a","Anna"), p("b","Ben")]} />);
  expect(screen.getByText(/Anna/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Nächstes Bild" }));
  expect(screen.getByText(/Ben/)).toBeInTheDocument();
});
test("PhotoSwitcher without photos renders gradient fallback", () => {
  render(<PhotoSwitcher photos={[]} />);
  expect(screen.getByTestId("panorama-fallback")).toBeInTheDocument();
});
test("home shows a clear message when data cannot be loaded", async () => {
  mockGetTrails.mockRejectedValue(new Error("no supabase"));
  render(await Home());
  expect(screen.getByText(/Daten konnten nicht geladen werden/)).toBeInTheDocument();
});
```

- [ ] **Step 2:** `npm test` → FAIL. **Step 3:** implementieren. **Step 4:** `npm test` → PASS, `npm run build` ohne Fehler.
- [ ] **Step 5:** Im Browser `localhost:3000/t/westweg-west` prüfen: Hintergrundbild wechselt, Etappenkarten zeigen echte Zahlen, Attribution sichtbar; Handybreite (390 px) ohne horizontales Scrollen.
- [ ] **Step 6:** Commit `feat: panorama layout with trails, stages and photos`.

### Task 11: Karte

**Files:**
- Create: `web/src/components/MapPanel.tsx`, `web/src/lib/map.ts`
- Modify: `web/src/app/t/[trailId]/page.tsx`
- Test: `web/src/lib/map.test.ts`

**Interfaces:**
- Consumes: `TrailDetail` aus Task 10; Unterkünfte über `getLodgings(trailId): Promise<LodgingOnTrail[]>` (`{ id, name, kind, website, dist_m, along_km, lon, lat }`, neu in `data.ts`).
- Produces:
  - `map.ts`: `BASEMAP_STYLE = "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/styles/bm_web_col.json"` (vor Umsetzung mit `curl -sI` prüfen; bei Fehler OSM-Rasterkacheln als Fallback-Style), `trailToFeatures(detail) → GeoJSON.FeatureCollection` (eine Linie je Etappe mit `seq`, Punkte für Etappengrenzen), `bboxOf(geom) → [w,s,e,n]`.
  - `MapPanel` (nur clientseitig, `dynamic(..., { ssr: false })`): Taste „🗺 Karte" öffnet ein Overlay über dem Panorama; Etappen abwechselnd in zwei Rottönen, Etappengrenzen als Punkte, Unterkünfte ≤ 1 km als 🛏-Marker mit Popup (Name, Abstand, Website-Link); Karte zoomt auf den Weg; Attribution aus Global Constraints sichtbar.

- [ ] **Step 1: Tests**

```ts
test("trailToFeatures makes one line per stage and boundary points", () => {
  const fc = trailToFeatures(detailWithStages(3));
  expect(fc.features.filter(f => f.geometry.type === "LineString")).toHaveLength(3);
  expect(fc.features.filter(f => f.geometry.type === "Point")).toHaveLength(4);
});
test("bboxOf", () => {
  expect(bboxOf({ type: "LineString", coordinates: [[8, 48], [8.2, 47.9]] })).toEqual([8, 47.9, 8.2, 48]);
});
```

- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS, `npm run build` ok.
- [ ] **Step 5:** Im Browser: Karte öffnet/schließt, Westweg vollständig ohne Sprünge, Unterkunfts-Popups mit Link, Attribution sichtbar.
- [ ] **Step 6:** Kurze `README.md` (nur: was es ist, `cp .env.example .env`, `make up`, `make import`, `make test`; die Capstone-README folgt in Plan 4). Commit `feat: map with basemap.de, stages and lodgings`.
