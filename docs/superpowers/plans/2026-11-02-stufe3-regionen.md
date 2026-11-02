# Stufe 3: Bodensee und Pfälzerwald – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HikeAllAbout kennt neben dem Schwarzwald die Regionen Bodensee (DE, CH, AT) und Pfälzerwald (nur DE) mit Tagestouren nach denselben Qualitätsregeln, vier neuen Fernwanderwegen mit Etappen, Orten, Unterkünften, Fotos, Wissen und Tags; der Assistent und die Oberfläche sprechen von allen drei Regionen.

**Architecture:** Eine feste Regionsliste (`regions.py`) ersetzt `BLACK_FOREST_BBOX` überall, wo heute importiert oder geprüft wird. Scan und Importe laufen über alle Regionen und schreiben die Vereinigung (die Importe löschen heute, was nicht im neuen Satz ist). Die Ortsauflösung bekommt Gebietswörter für die drei Regionen; Orte in der Schweiz und Österreich lösen sich auf, sobald sie importiert sind.

**Tech Stack:** Python (uv, pytest, psycopg, Overpass, Copernicus-DEM), Supabase-Postgres/PostGIS (Migrationen mit `npx supabase migration up`, nie `db reset`), Next.js/Vitest.

**Spec:** `docs/superpowers/specs/2026-11-02-rollen-backend-regionen-wetter-design.md`, Abschnitt „Stufe 3“ und „Für alle Stufen“. Fernweg-Recherche: `docs/superpowers/specs/2026-11-02-stufe3-fernwege-recherche.md`.

**Branch:** `stufe3-regionen` von `main`.

## Entscheidungen von Ali (2026-11-02, nach der Recherche)

- **Die 127 HikeAi2-Routen bleiben weg.** Recherche: alle sind `network:type=node_network`-Abschnitte des Schwarzwaldvereins (1–4 km, Wegweiser zu Wegweiser), absichtlich gefiltert (`ingest/day_hikes.py`, Test `test_day_hikes.py:77`) und unter 5 km. Kein Fehler; der Spec-Punkt „Schwarzwald-Lücke schließen“ entfällt. Task 1 korrigiert die Spec.
- **Fernwege: alle vier** – Pfälzer Weinsteig, Pfälzer Waldpfad, Jubiläumsweg Bodenseekreis, SeeGang. Beim SeeGang sind die Etappen-km nicht offiziell; Quelle mit diesem Hinweis.

## Global Constraints

- Qualitätsregeln unverändert: Länge 5–30 km, keine Lücken im Verlauf, kein Fernweg (iwn/nwn) als Tagestour, kein Knotennetz-Abschnitt; Ort-zu-Ort-Verbindungen nur über die manuelle Spalte („Vorschlag Claude: …“), die Ali bestätigt.
- Regionen (Reihenfolge south, west, north, east): `black_forest` „Schwarzwald“ = heutige `BLACK_FOREST_BBOX` (47.55, 7.55, 48.95, 8.80), DE; `palatinate` „Pfälzerwald“ (48.95, 7.55, 49.75, 8.45), nur DE; `lake_constance` „Bodensee“ (47.40, 8.80, 47.95, 9.95), DE, CH, AT (west 8.80 statt 8.85 aus HikeAi2: Lücke zu Schwarzwald geschlossen, Hohentwiel/Singen).
- Bestehende Schwarzwald-Daten bleiben unverändert erhalten (gleiche IDs, gleiche Zahl Tagestouren aus dem Schwarzwald, gleiche Etappen).
- Nie `npx supabase db reset`. Vor dem ersten Import, der Daten löscht oder ersetzt, ein Dump nach `data/backups/` (gitignored).
- Quellen und Lizenzen wie bisher (OSM ODbL, Copernicus, Commons-Filter, Wikipedia/Wikivoyage CC BY-SA, Etappen „Fakten, keine Texte übernommen“).
- Oberfläche und Assistententexte deutsch; überall, wo heute „Schwarzwald“ als einziges Gebiet steht, stehen alle drei Regionen.

## Review Focus

1. **Gebietswort gegen gleichnamigen Ort** – „Wanderung am Bodensee“ trifft das Gebiet Bodensee (Region-Box), nicht den See-Ort mit 15-km-Radius um die Seemitte, und löst keine Rückfrage aus. Test in Task 5.
2. **Route über die Grenze nach Frankreich** im Pfälzerwald – wird verworfen mit Grund „führt nach Frankreich“; Routen in CH/AT am Bodensee bleiben erlaubt. Test in Task 2.
3. **Import einer Region löscht die anderen nicht** – Orte, Unterkünfte, POIs bleiben für alle Regionen erhalten, auch wenn nur der Schwarzwald aus der PBF kommt. Test in Task 3.
4. **Schweizer/österreichischer Ort als Start** („Rundtour ab Stein am Rhein“, „ab Bregenz“) – löst sich auf und findet Touren, sobald die Orte importiert sind. Test in Task 5 (Fake) und Smoke in Task 8.
5. **Bestehende Schwarzwald-Kandidaten in der CSV** – behalten ihre manuellen Entscheidungen; die neue Spalte `region` wird für sie `black_forest`. Test in Task 2.

---

### Task 1: Regionsmodell

**Files:**
- Create: `backend/src/hikeall/regions.py`, `backend/tests/test_regions.py`
- Create: `supabase/migrations/20261103000001_trail_region.sql`
- Modify: `backend/src/hikeall/ingest/trails.py` (`check_in_region`), `backend/src/hikeall/db.py` (Trail-Upsert mit `region`), `backend/src/hikeall/errors.py` (Text)
- Modify: `docs/superpowers/specs/2026-11-02-rollen-backend-regionen-wetter-design.md` (Stufe 3: Punkt „Schwarzwald-Lücke schließen“ durch Alis Entscheidung ersetzen; Fernweg-Auswahl der vier Wege eintragen)
- Modify: `.gitignore` (`data/backups/`)

**Interfaces:**
- Produces (`regions.py`):
  - `@dataclass(frozen=True) class Region: id: str; name: str; bbox: BBox; countries: tuple[str, ...]; exclude: tuple[tuple[str, str, str], ...]` – `exclude` = Gebiete (OSM-Area-Schlüssel, Wert, Grund), in die eine Tagestour der Region nicht führen darf (Pfälzerwald: `ISO3166-1=FR` „führt nach Frankreich“, `ISO3166-2=DE-BW` „liegt in Baden-Württemberg, nicht im Pfälzerwald“, `ISO3166-2=DE-HE` „liegt in Hessen, nicht im Pfälzerwald“; sonst leer).
  - `REGIONS: tuple[Region, ...]` mit den drei Regionen aus Global Constraints (Pfälzerwald mit den drei `exclude`-Gebieten).
  - `RegionId = Literal["black_forest", "palatinate", "lake_constance"]`
  - `get_region(region_id: str) -> Region` (KeyError bei Unbekanntem)
  - `region_of_line(points: Sequence[tuple[float, float]]) -> Region | None` – die erste Region, deren Box alle Punkte (lat, lon) enthält.
  - `REGION_NAMES = "Schwarzwald, Bodensee und Pfälzerwald"` und `REGION_PHRASE = "im Schwarzwald, am Bodensee (mit Schweizer und österreichischem Ufer) und im Pfälzerwald"` für Texte.
  - `BLACK_FOREST_BBOX` bleibt in `models.py` als Alias auf die Box der Region `black_forest` (bestehende Tests).
- `check_in_region(line, context) -> Region` – liefert die Region, deren Box die ganze Linie enthält; sonst `OutsideRegionError` mit „liegt in keiner Region vollständig“.
- Migration: `alter table trails add column region text not null default 'black_forest' check (region in ('black_forest','palatinate','lake_constance'))`; Default danach entfernen (`alter column region drop default`), damit neue Zeilen die Region explizit setzen. Trail-Upsert (Fernweg und Tagestour) schreibt `region`.

- [ ] **Step 1: Backup** – `mkdir -p data/backups && docker exec supabase_db_HikeAllAbout pg_dump -U postgres -n public --data-only > data/backups/2026-11-03-vor-stufe3.sql`; Datei > 1 MB prüfen.
- [ ] **Step 2: Failing tests** in `test_regions.py`: `get_region("palatinate").bbox.south == 48.95`; `region_of_line([(48.0, 8.0), (48.1, 8.1)]).id == "black_forest"`; `region_of_line([(47.66, 8.86)]).id == "lake_constance"` (Stein am Rhein); `region_of_line([(48.0, 8.0), (49.3, 7.9)]) is None`; `check_in_region` liefert Region bzw. wirft; DB-Test: Spalte `trails.region` existiert, alle bestehenden Zeilen `black_forest`, ungültiger Wert verletzt den Check.
- [ ] **Step 3: Run** `cd backend && uv run pytest tests/test_regions.py -q` – FAIL.
- [ ] **Step 4: Implement**, Migration anwenden (`npx supabase migration up`), Spec-Abschnitt anpassen.
- [ ] **Step 5: Run** `uv run pytest -q` – PASS.
- [ ] **Step 6: Commit** `feat: Regionen Schwarzwald, Bodensee, Pfälzerwald`

---

### Task 2: Tagestour-Scan und -Import je Region

**Files:**
- Modify: `backend/src/hikeall/ingest/day_hikes.py`, `backend/src/hikeall/cli.py` (`scan_day_hikes`, `import_day_hikes_cmd`)
- Modify: `data/curated/day_hikes.csv` (Spalte `region` nach `osm_relation_id`, bestehende Zeilen `black_forest` – per Code beim nächsten Schreiben, nicht von Hand)
- Test: `backend/tests/test_day_hikes.py`

**Interfaces:**
- Consumes: `REGIONS`, `Region`, `region_of_line`, `check_in_region` (Task 1).
- Produces:
  - `scan(overpass, regions: Sequence[Region]) -> ScanResult` – kachelt jede Region wie heute (0,35°), Kandidaten dedupliziert nach Relation; jeder Kandidat bekommt `region: str | None`.
  - Regel „verlässt die Schwarzwald-Box“ wird: Linie liegt in keiner Region vollständig → `rejected`, Grund `"liegt in keiner Region vollständig"`; sonst `region = region_of_line(...).id`.
  - Neue Regel nach der Boxprüfung, nur für Regionen mit `exclude`: `foreign_relations(overpass, relation_ids: list[int], key: str, value: str) -> set[int]` (eine Overpass-Abfrage je Region und Gebiet mit `area["key"="value"]` und den Ways der Relationen; Relationen mit mindestens einem Way im Ausland) → `rejected`, Grund je Gebiet aus `exclude` (z. B. `"führt nach Frankreich"`). Außerdem verwirft `auto_decision` jede Relation, die in `data/curated/trails.yaml` unter `osm_relation_ids` steht (Gruppen flach), mit Grund `"Etappe eines Fernwegs"`. `trim_to_stages` läuft nur bei Specs mit `trim: true` (nur die vier neuen Fernwege).
  - CSV: Spalte `region`; `read_candidates` liest alte Dateien ohne Spalte (Region dann `black_forest`, wenn die Zeile schon da war); manuelle Spalten bleiben wie heute erhalten.
  - `import_day_hikes` setzt `trails.region` aus dem Kandidaten.
  - CLI: `scan-day-hikes` und `import-day-hikes` ohne neue Pflichtargumente; optional `--region <id>` beim Scan, das nur diese Region neu scannt und die Zeilen der anderen Regionen unverändert lässt. Ausgabe je Region: Kandidaten, automatisch accepted.

- [ ] **Step 1: Failing tests** (Fake-Overpass wie im bestehenden Modul):
  - `test_scan_assigns_region` – je eine Relation in Schwarzwald-, Pfalz- und Bodensee-Box → Regionen `black_forest`, `palatinate`, `lake_constance`.
  - `test_route_in_no_region_rejected` – Linie von 48,5/8,0 nach 49,3/7,9 → `rejected`, `"liegt in keiner Region vollständig"`.
  - `test_palatinate_route_into_france_rejected` – Fake meldet Relation als im Ausland → `rejected`, `"führt nach Frankreich"`; eine Bodensee-Relation mit Punkten in CH bleibt `accepted` (keine Auslandsabfrage für `lake_constance`).
  - `test_old_csv_without_region_keeps_manual_decisions` – alte CSV-Zeile mit `manual_decision=rejected` → nach Scan und Schreiben `region=black_forest`, manuelle Spalten unverändert.
  - `test_scan_single_region_keeps_other_rows` – `--region palatinate` lässt Schwarzwald-Zeilen unverändert.
  - `test_import_sets_trail_region` (DB-Test wie bestehend).
  - Der bestehende Knotennetz-Test bleibt unverändert grün.
- [ ] **Step 2: Run** `uv run pytest tests/test_day_hikes.py -q` – FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` – PASS.
- [ ] **Step 5: Commit** `feat: Tagestour-Scan und -Import für alle Regionen`

---

### Task 3: Orte, POIs und Unterkünfte für alle Regionen

**Files:**
- Modify: `backend/src/hikeall/cli.py` (`import_places_cmd`, `import_lodgings_cmd`), `Makefile` (`places`-Ziel), ggf. `backend/src/hikeall/ingest/places.py`, `ingest/lodgings.py`
- Test: `backend/tests/test_places.py`, `backend/tests/test_lodgings.py`, `backend/tests/test_cli.py` (neu, falls nötig)

**Interfaces:**
- Consumes: `REGIONS` (Task 1).
- Produces:
  - `collect_places(overpass, regions, pbf: Path | None) -> tuple[list[Place], list[Poi]]` – Schwarzwald aus der PBF, wenn `--pbf` angegeben (heutiger Weg), alle anderen Regionen per Overpass (`fetch_places`/`fetch_pois` mit der Regionsbox); Vereinigung dedupliziert nach OSM-ID. `import_places` danach **einmal** mit der Vereinigung (heute löscht es Orte, die nicht im Satz sind).
  - `collect_lodgings(overpass, regions) -> list[Lodging]` – `fetch_lodgings` je Regionsbox, Vereinigung dedupliziert; `import_lodgings` einmal.
  - Ausgabe der CLI je Region: Anzahl Orte/POIs/Unterkünfte aus OSM.
  - `make places` bleibt ein Aufruf (PBF für den Schwarzwald, Overpass für den Rest); keine neuen PBF-Downloads.

- [ ] **Step 1: Failing tests**
  - `test_collect_places_unions_regions_and_dedupes` – Fake-Overpass liefert je Region Orte, ein Ort doppelt → Vereinigung ohne Doppel; mit `pbf` wird für `black_forest` die PBF gelesen (Fake `read_elements`) und Overpass nur für die beiden anderen Regionen gefragt.
  - `test_collect_lodgings_unions_regions`.
  - `test_import_places_keeps_all_regions` (DB-Test) – Import der Vereinigung aus zwei Regionen, danach Orte beider Regionen vorhanden.
- [ ] **Step 2: Run** – FAIL. **Step 3: Implement.** **Step 4: Run** `uv run pytest -q` – PASS.
- [ ] **Step 5: Commit** `feat: Orte und Unterkünfte für alle Regionen`

---

### Task 4: Vier neue Fernwanderwege

**Files:**
- Modify: `data/curated/trails.yaml` (Quellen und Wege `pfaelzer-weinsteig`, `pfaelzer-waldpfad`, `jubilaeumsweg-bodenseekreis`, `seegang`), `backend/src/hikeall/tags/vocabulary.py` (`TRAILS`), ggf. `backend/src/hikeall/ingest/trails.py`/`stages.py`
- Test: `backend/tests/test_import_trails.py`, `backend/tests/test_tags.py`

**Interfaces:**
- Consumes: `check_in_region` → Region (Task 1); Trail-Upsert mit `region`.
- Daten (aus der Recherche-Datei, verbatim übernehmen, Etappenorte als Koordinaten der Ortsmitte per Nominatim bzw. Etappen-Endknoten der OSM-Relation wie bei den bestehenden Wegen, mit Kommentar im YAML):
  - **Pfälzer Weinsteig** – `osm_relation_ids` = die 11 Etappenrelationen der Superroute 15761992 in Gehrichtung (8124459, 2504578–2504582, 3286359–3286362, 3286358; Reihenfolge an der Superroute prüfen), 11 Etappen mit `km` von pfalz.de; Quelle `https://www.pfalz.de/de/route/pfaelzer-weinsteig`; Zuweg-Relationen nicht aufnehmen.
  - **Pfälzer Waldpfad** – Relation 1650025; 8 Etappen Schopp–Johanniskreuz–Heltersberg–Rodalben–Merzalben–Hauenstein–Dahn–Erlenbach–Schweigen-Rechtenbach mit `km`; Quelle `https://www.pfalz.de/de/route/pfaelzer-waldpfad`. Der OSM-Weg beginnt in Kaiserslautern: der Teil vor Schopp gehört nicht zum Weg (Weglänge = Summe der Etappen); falls der Import das nicht kann, `ingest/trails.py` so erweitern, dass die Linie am Start der ersten und am Ende der letzten Etappe abgeschnitten wird, mit Test.
  - **Jubiläumsweg Bodenseekreis** – Relation 157307; 6 Etappen Kressbronn–Neukirch–Meckenbeuren–Markdorf–Heiligenberg–Owingen–Überlingen (km „ca.“ aus der Quelle); Quelle `https://www.bodenseekreis.de/landkreis-tourismus/wandern/jubilaeumsweg/`. Die ~60-m-Lücke liegt unter `MAX_GAP_M = 200`.
  - **SeeGang** – Relation 12925238; 4 Etappen Konstanz–Wallhausen–Bodman–Sipplingen–Überlingen mit km 18,4 / 18,9 / 7,4 / 10,9; Quellen seen.de (Endpunkte) und wildganz.com (km); im Quellen-Namen: „Etappen-km nicht offiziell bestätigt“.
  - `TRAILS` im Vokabular: je Weg Tag `trail:<id>`, Label wie oben, Synonyme (z. B. „Weinsteig“, „Waldpfad“, „Jubiläumsweg“, „Premiumweg SeeGang“).
- Mehrtagesplanung, Unterkünfte und Regenvarianten funktionieren unverändert für die neuen Wege (keine Sonderfälle).

- [ ] **Step 1: Failing tests** – `test_tags.py`: die vier `trail:`-Tags existieren und „Weinsteig“ löst auf `trail:pfaelzer-weinsteig`; `test_import_trails.py`: `load_trail_specs` liest die vier Wege mit 11/8/6/4 Etappen, alle Etappen haben `km`; Test für das Abschneiden vor der ersten Etappe (synthetische Linie), falls Code geändert wird.
- [ ] **Step 2: Run** – FAIL. **Step 3: Implement** (YAML, Vokabular, ggf. Abschneiden).
- [ ] **Step 4: Import ausführen** – `cd backend && uv run hikeall import-trails --only <id>` für jeden der vier Wege; Abweichungen > 5 % zwischen OSM-Linie und offiziellen km wie bei Mittelweg/Ostweg als Kommentar im YAML festhalten, nicht verstecken. Erwartet: jeder Weg importiert, `trails.region` = `palatinate` bzw. `lake_constance`, Schwarzwald-Wege unverändert.
- [ ] **Step 5: Run** `uv run pytest -q` – PASS.
- [ ] **Step 6: Commit** `feat: Fernwege Pfälzer Weinsteig, Pfälzer Waldpfad, Jubiläumsweg, SeeGang`

---

### Task 5: Assistent kennt alle drei Regionen

**Files:**
- Modify: `backend/src/hikeall/tags/vocabulary.py` (Gebiets-Tags), `backend/src/hikeall/guard.py`, `backend/src/hikeall/agent/prompts.py`, `backend/src/hikeall/agent/understand.py`, `backend/src/hikeall/agent/tools.py` (Beschreibung `search_knowledge`), `backend/src/hikeall/adapters/http.py` (falls der User-Agent-Text das Gebiet nennt: neutral „Wanderassistent“)
- Test: `backend/tests/test_tags.py`, `test_understand.py`, `test_guard.py`, `test_agent_graph.py`, `test_smoke.py` (Textstellen anpassen)

**Interfaces:**
- Consumes: `REGIONS`, `REGION_NAMES`, `REGION_PHRASE` (Task 1).
- Produces:
  - Gebiets-Tags für die Regionen: `area:schwarzwald` „Schwarzwald“, `area:pfaelzerwald` „Pfälzerwald“ (Synonyme „Pfälzer Wald“, „Pfalz“), `area:bodensee` „Bodensee“ (Synonyme „am Bodensee“, „Schwäbisches Meer“), jeweils mit der Regionsbox; die bestehenden `area:nord/mitte/sued` bleiben (Schwarzwald-Teile).
  - Ein Ort (`place:*`), dessen gefaltetes Label gleich einem Regionsnamen ist (z. B. der See „Bodensee“), wird beim Aufbau des Vokabulars übergangen; das Gebiet gewinnt, keine Rückfrage.
  - Alle Texte in Guard/Prompts/understand, die das Gebiet nennen, nutzen `REGION_PHRASE`/`REGION_NAMES` statt „Schwarzwald“ (Liste der Stellen: guard.py:8, prompts.py:6/21/28/95/98, understand.py:58/63/651, tools.py:717). Wo ein Text Schwarzwald-spezifisch richtig ist (z. B. „Südschwarzwald“), bleibt er.
- [ ] **Step 1: Failing tests**
  - `test_tags.py::test_region_area_tags` – „Bodensee“, „Pfälzer Wald“, „Schwarzwald“ lösen auf die drei Area-Tags mit den Regionsboxen.
  - `test_tags.py::test_place_named_like_region_is_skipped` – Vokabular aus einer Orte-Tabelle mit See „Bodensee“ → kein `place:`-Tag „Bodensee“, Suche ergibt `area:bodensee`.
  - `test_understand.py::test_bodensee_is_area_without_clarify` – Fake-Gateway liefert `start_text="Bodensee"` → `HikeRequest.start.kind == "area"`, Box = Bodensee.
  - `test_understand.py::test_swiss_place_resolves` – Vokabular mit Ort „Stein am Rhein“ (47.66, 8.86) → Start ist dieser Ort.
  - `test_guard.py` / Prompt-Tests: Ablehnungstext für Themen außerhalb nennt „Schwarzwald, Bodensee und Pfälzerwald“.
- [ ] **Step 2: Run** – FAIL. **Step 3: Implement.** **Step 4: Run** `uv run pytest -q` – PASS.
- [ ] **Step 5: Commit** `feat: Assistent für Schwarzwald, Bodensee und Pfälzerwald`

---

### Task 6: Web-Texte und Karte

**Files:**
- Modify: `web/src/components/HomeStage.tsx`, `web/src/app/layout.tsx`, `web/src/lib/planView.ts`, `web/src/components/MapPanel.tsx`, zugehörige Tests

**Interfaces:**
- Überschrift der Startseite „Wandern im Schwarzwald, am Bodensee und im Pfälzerwald“; `layout.tsx` Titel/Beschreibung entsprechend; `planView.ts` Standardort der Unterkunftssuche ist der Etappenort des Tages bzw. der Startort des Plans, sonst der Wegname – nie fest „Schwarzwald“; `MapPanel` Standardausschnitt umfasst alle drei Regionen (Mitte [8.7, 48.55], Zoom 6.5).
- [ ] **Step 1: Failing tests** – HomeStage zeigt die neue Überschrift; planView-Link für einen Pfalz-Plan enthält nicht „Schwarzwald“.
- [ ] **Step 2: Run** `cd web && npx vitest run` – FAIL. **Step 3: Implement.** **Step 4: Run** `npx vitest run && npx tsc --noEmit` – PASS.
- [ ] **Step 5: Commit** `feat: Startseite und Karte für drei Regionen`

---

### Task 7: Wissen zu den neuen Regionen

**Files:**
- Modify: `data/knowledge/sources.yaml`
- Test: `backend/tests/test_knowledge.py` (nur falls ein Test die Artikelliste festschreibt)

- [ ] **Step 1:** Artikel ergänzen (de.wikipedia.org): Bodensee, Pfälzerwald, Pfälzer Weinsteig, Pfälzer Waldpfad, Biosphärenreservat Pfälzerwald-Nordvogesen, Überlingen, Lindau (Bodensee), Pfänder, Hohentwiel, Trifels; Wikivoyage: Bodensee, Pfälzerwald. Fehlt ein Artikel, einen Kommentar „kein Artikel, geprüft am …“ wie beim Mittelweg.
- [ ] **Step 2:** Bestehende Tests anpassen, falls nötig; `uv run pytest tests/test_knowledge.py -q` – PASS.
- [ ] **Step 3: Commit** `feat: Wissensquellen Bodensee und Pfälzerwald`

---

### Task 8: Datenlauf, Kuration, Smoke, README

**Files:**
- Modify: `data/curated/day_hikes.csv` (Scan-Ergebnis + Claudes Vorschläge für die neuen Regionen), `README.md`
- Create: `docs/superpowers/plans/2026-11-02-stufe3-datenlauf.md` (Protokoll mit Zahlen)

- [ ] **Step 1: Scan** – `cd backend && uv run hikeall scan-day-hikes`; Zahlen je Region ins Protokoll. Schwarzwald-Zeilen: gleiche Relationen und Entscheidungen wie vorher, außer: Spalte `region` ist neu, Zeilen mit auto_reason „verlässt die Schwarzwald-Box“ lauten jetzt „liegt in keiner Region vollständig“ (einige können in eine andere Region wechseln). Etappenrelationen der Fernwege werden automatisch verworfen („Etappe eines Fernwegs“).
- [ ] **Step 2: Kuration** – für jede in Pfalz/Bodensee automatisch akzeptierte Route prüfen (Name, Rundweg, Länge, Lage), wie bei den 255 Schwarzwald-Vorschlägen: offensichtliche Ort-zu-Ort-Verbindungen, Zubringer, Doppelungen mit einem Fernweg → `manual_decision=rejected`, `manual_reason="Vorschlag Claude: …"`. Alles andere bleibt automatisch. Zahl der Vorschläge ins Protokoll. Ali prüft später (offener Punkt im Bericht).
- [ ] **Step 3: Importe** in dieser Reihenfolge: `import-day-hikes`, Waldpfad mit `import-trails --only pfaelzer-waldpfad` importieren, `make places` (bzw. `import-places --pbf …`), `import-lodgings`, `build-tags`, `import-photos`, `prune-photos`, `build-knowledge`. Jede Ausgabe mit Zahlen ins Protokoll; Fehler nicht übergehen. Braucht der DEM neue Kacheln (N47/E009, N49/E007, N49/E008) und bremst `max_tiles=4`, den Wert für den Lauf anheben. Overpass-Fehler (429/504): mit Pause wiederholen, nicht Regionen auslassen. Danach Zählung je Region (`select region, kind, count(*) from trails group by 1,2`), Orte/Unterkünfte je Regionsbox; Schwarzwald-Zahlen vorher/nachher vergleichen (Tagestouren 122, Fernwege 4, Etappen 46 unverändert).
- [ ] **Step 4: Smoke** – API starten (`uv run uvicorn hikeall.api.app:app --port 8000`), mit dem lokalen Admin (`admin@hikeall.local`) diese Anfragen stellen und Ergebnis ins Protokoll: „Rundtour am Bodensee 10 bis 15 km“, „Wanderung ab Stein am Rhein“, „Rundweg im Pfälzerwald mit Einkehr“, „3 Tage Pfälzer Waldpfad ab Johanniskreuz“, „SeeGang in 2 Tagen ab Konstanz“, „Rundtour Feldberg (Schwarzwald) 15 km“ (Regression). Erwartet: Touren aus der richtigen Region, Mehrtagespläne mit Unterkünften, Schwarzwald unverändert. Danach API beenden.
- [ ] **Step 5: README** – Regionen, Fernwege (jetzt 8), Zahlen, Datenquellen (Overpass für Pfalz/Bodensee, PBF nur Schwarzwald), Hinweis auf offene manuelle Prüfung der Vorschläge.
- [ ] **Step 6: Run** `cd backend && uv run pytest -q`, `cd web && npx vitest run` – PASS.
- [ ] **Step 7: Commit** `feat: Daten Bodensee und Pfälzerwald, README`
