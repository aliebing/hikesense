# Plan 5 – Dunkelgrünes Layout, Kacheln auf der Startseite, Tourseite mit Karte

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nach einer Chat-Antwort stehen die Vorschläge als klickbare Kacheln direkt auf der Startseite. Die Tourseite ist dunkelgrün, ohne Fotohintergrund, mit eingebetteter Karte und allen Daten zur Tour in hellen Blöcken.

**Architecture:** Nur Web (`web/`) und eine neue Lese-View in Supabase (`trail_pois_geo`). Backend, Agent und Chat-Ereignisse bleiben unverändert. Ein gemeinsamer Rahmen `PageFrame` ersetzt `Panorama`. `PhotoSwitcher` wird vom Vollbild-Hintergrund zu einem begrenzten Bild mit Vorschaubildern. `MapPanel` bekommt eine eingebettete Darstellung mit Einkehr- und Aussichtspunkten. Die Beschreibung der Tour baut reiner Code aus Daten (`lib/tour.ts`).

**Tech Stack:** Next.js 15, React 19, Tailwind 4, MapLibre, Supabase (PostgREST), vitest + testing-library.

**Spec:** `docs/superpowers/specs/2026-11-01-dunkelgruen-kacheln-design.md`

**Bewusste Schnitte [Claude, beim Review änderbar]:**
- `/plan` ohne `id` zeigt den Plan aus dem Chat (ChatProvider). Mit `id` bleibt es der gemerkte Plan. Beide zeigen die Karte oben.
- Fotos auf der Tourseite: großes Bild mit Vorschaubildern darunter (Raster), Upload und Löschen eigener Fotos wie bisher. Kein Vollbild-Hintergrund mehr irgendwo.
- Startseite: Foto rechts neben Titel und Chat (ab `md`), auf dem Handy darunter. Kein Text auf dem Bild, der Nachweis steht unter dem Bild.
- Einkehr und Aussicht erscheinen als Liste **und** als Kartenmarker.
- Der Chat auf der Tourseite liegt als aufklappbarer Block zwischen Kopf und Karte (im Fluss, nicht fixiert), damit er die Karte nie verdeckt.

## Global Constraints

- Keine Änderung an `backend/`, an Chat-Ereignissen, Agent oder Evaluation. Einzige DB-Änderung: neue View `trail_pois_geo` (nur lesen, `security_invoker = true`, `grant select … to anon, authenticated`).
- Farben nur aus `globals.css`: Grund `--color-wald-dunkel` #1f3f27, Blöcke `--color-papier` #f4f1ea, Akzent `--color-wald` #2f5d3a; Hinweise Amber. Ein zweiter Grünton für Flächen auf dunklem Grund ist erlaubt (`#284a32`, als `--color-wald-flaeche`).
- Kein Text auf Fotos, keine `drop-shadow`-Klassen mehr. Fließtext-Kontrast mindestens 4,5:1 (helle Schrift auf `wald-dunkel` oder dunkle Schrift auf `papier`).
- Jede Zahl in Beschreibung, Listen und Legenden stammt aus der Datenbank. Fehlende Werte werden weggelassen oder als „unbekannt“ bzw. `–` angezeigt, nie als 0.
- Ein Block ohne Daten fällt weg (nie „0 Unterkünfte“). Ein Block, der nicht lädt, zeigt einen kurzen Hinweis; der Rest der Seite bleibt.
- POI-Auswahl, überall gleich: alle Zeilen aus `trail_pois` des Wegs mit `kind ≠ 'station'`. Einkehr = `food` + `hut`, Aussicht = `viewpoint` + `peak`, dazu `waterfall`.
- Texte der Oberfläche auf Deutsch, Code-Kommentare auf Englisch (wie im Repo).
- Prüfen vor jedem Commit: `cd web && npm test && npm run lint && npx tsc --noEmit`.

## Review Focus

1. **Handy-Breite (375 px):** Startseite mit Chat und Kacheln untereinander, keine horizontale Scrollleiste, „Merken“ und Kachel-Klick beide bedienbar. → Test in Aufgabe 6 (Klassen der Spalten) plus Sichtprüfung in Aufgabe 8.
2. **Tour ohne POIs, ohne Unterkünfte, ohne Profil, ohne Tags** (viele Tagestouren): Beschreibung ohne „Unterwegs …“-Satz, Blöcke fallen weg, keine „0“. → Tests in Aufgaben 1 und 4.
3. **Geteilter Tour-Link ohne Chat-Verlauf:** keine Wunsch-Häkchen, kein Fehler, Zurück-Link „← Startseite“. → Tests in Aufgabe 4.
4. **Chat-Plan ohne Karte** (Weg lädt nicht): `/plan` zeigt die Tage trotzdem. → Test in Aufgabe 7.
5. **Alte Links** `/vorschlaege` und `?von=vorschlaege`: Weiterleitung auf `/` bzw. gleicher Zurück-Link wie `von=chat`. → Tests in Aufgaben 4 und 5.

---

### Task 1: Daten für Einkehr, Aussicht, Merkmale, Belag und die Beschreibung

**Files:**
- Create: `supabase/migrations/20261101000001_trail_pois_geo.sql`
- Modify: `web/src/lib/data.ts` (Typen `TrailPoi`, `TrailDetail.surface_shares`, `getTrailPois`, `getTrailTags`, `getTrail` lädt `surface_shares`)
- Create: `web/src/lib/tour.ts`
- Test: `web/src/lib/tour.test.ts`, `web/src/lib/data.test.ts` (erweitern, falls vorhanden, sonst neu)

**Interfaces:**
- Produces:
  - `type TrailPoi = { id: number; name: string | null; kind: "food" | "hut" | "viewpoint" | "peak" | "waterfall"; dist_m: number | null; along_km: number | null; lon: number; lat: number }`
  - `getTrailPois(trailId: string): Promise<TrailPoi[]>` – View `trail_pois_geo`, `kind <> station`, sortiert nach `along_km` (nulls last), dann `id`.
  - `getTrailTags(trailId: string): Promise<string[]>` – `trail_tags.tag_id` des Wegs, sortiert.
  - `TrailDetail.surface_shares: Record<string, number> | null` (aus `trails.surface_shares`; nur endliche Zahlen ≥ 0, sonst `null`).
  - In `lib/tour.ts`:
    - `POI_KIND: Record<TrailPoi["kind"], { icon: string; label: string; group: "einkehr" | "aussicht" | "wasserfall" }>` mit food ☕ „Einkehr“, hut 🏠 „Hütte“, viewpoint 👁 „Aussicht“, peak ⛰ „Gipfel“, waterfall 💧 „Wasserfall“.
    - `TAG_LABEL: Record<string, string>` = die 9 Einträge aus `data/tags/features.yaml` (z. B. `"feature:rundweg": "Rundweg"`, `"surface:wenig_asphalt": "Wenig Asphalt"`).
    - `tagLabels(tags: string[]): string[]` – bekannte Tags als Beschriftung, unbekannte fallen weg, `feature:bahnhof` bleibt (es ist ein Merkmal, kein POI der Liste).
    - `surfaceLine(shares: Record<string, number> | null): string | null` – „Belag: 37 % unbekannt · 29 % Schotter · 20 % Asphalt · 15 % naturbelassen“: absteigend, ganze Prozent, Anteile unter 5 % fallen weg; Labels `paved` Asphalt, `gravel` Schotter, `unpaved` naturbelassen, `unknown` unbekannt; `null` ohne Daten.
    - `describeTour(t: { roundtrip: boolean; length_km: number | null; ascent_m: number | null; time: string | null; pois: TrailPoi[] }): string | null`

- [ ] **Step 1: Migration schreiben** – View `trail_pois_geo` nach dem Muster von `20261028000003_trail_lodgings_geo.sql`: Spalten `trail_id, id, name, kind, dist_m, along_km, lon, lat` aus `trail_pois tp join pois p on p.id = tp.poi_id where p.kind <> 'station'`. Anwenden: `npx supabase migration up` (bzw. `npx supabase db reset` nur, wenn `up` nicht geht – danach `make admin-user` und `make smoke-user` erneut).

- [ ] **Step 2: Prüfen, dass die View liest**

Run: `curl -s "http://127.0.0.1:54321/rest/v1/trail_pois_geo?select=kind&limit=3" -H "apikey: $ANON"`
Expected: JSON-Liste mit `kind`-Werten, kein `station`.

- [ ] **Step 3: Failing tests für `lib/tour.ts`**

```ts
const poi = (kind: TrailPoi["kind"], id = 1): TrailPoi => ({ id, name: null, kind, dist_m: 50, along_km: 1, lon: 8, lat: 48 });

it("describes a round trip with stops", () => {
  expect(describeTour({ roundtrip: true, length_km: 11.4, ascent_m: 389, time: "3:54 h", pois: [poi("food", 1), poi("hut", 2), poi("viewpoint", 3)] }))
    .toBe("Rundweg, 11,4 km mit 389 m Aufstieg, Gehzeit etwa 3:54 h nach DIN 33466. Unterwegs 2 Einkehrmöglichkeiten und 1 Aussichtspunkt.");
});
it("leaves out what is missing and never says 0", () => {
  expect(describeTour({ roundtrip: false, length_km: 8, ascent_m: null, time: null, pois: [] })).toBe("Tour, 8,0 km.");
  expect(describeTour({ roundtrip: false, length_km: null, ascent_m: null, time: null, pois: [] })).toBeNull();
});
it("counts peaks as Aussichtspunkte and names waterfalls", () => {
  expect(describeTour({ roundtrip: false, length_km: 5, ascent_m: 100, time: null, pois: [poi("peak", 1), poi("waterfall", 2)] }))
    .toBe("Tour, 5,0 km mit 100 m Aufstieg. Unterwegs 1 Aussichtspunkt und 1 Wasserfall.");
});
it("surfaceLine sorts, rounds and drops small shares", () => {
  expect(surfaceLine({ paved: 0.2, gravel: 0.287, unknown: 0.368, unpaved: 0.15 }))
    .toBe("Belag: 37 % unbekannt · 29 % Schotter · 20 % Asphalt · 15 % naturbelassen");
  expect(surfaceLine({ paved: 0.97, gravel: 0.03 })).toBe("Belag: 97 % Asphalt");
  expect(surfaceLine(null)).toBeNull();
});
it("tagLabels drops unknown ids", () => {
  expect(tagLabels(["feature:rundweg", "x:y", "surface:naturweg"])).toEqual(["Rundweg", "Naturweg"]);
});
```

Singular/Plural: „1 Einkehrmöglichkeit“/„n Einkehrmöglichkeiten“, „1 Aussichtspunkt“/„n Aussichtspunkte“, „1 Wasserfall“/„n Wasserfälle“; Teile mit Komma, die letzten zwei mit „und“.

- [ ] **Step 4: Run** `cd web && npx vitest run src/lib/tour.test.ts` → FAIL (Modul fehlt).
- [ ] **Step 5: `lib/tour.ts` und die Daten-Funktionen implementieren.** `getTrailPois` nach dem Muster von `getLodgings` (`num()` für Zahlen, `Number()` für lon/lat). `surface_shares` im bestehenden `trails`-Select von `getTrail` mitladen (`select("profile,surface_shares")`), über eine neue `toShares(v: unknown)` absichern (Test: kaputte Werte → `null`).
- [ ] **Step 6: Run** `cd web && npm test && npx tsc --noEmit` → PASS.
- [ ] **Step 7: Commit** `feat: Daten für Einkehr, Aussicht, Belag und Tourbeschreibung`

---

### Task 2: Gemeinsamer dunkelgrüner Rahmen, Foto als begrenztes Bild

**Files:**
- Create: `web/src/components/PageFrame.tsx` (ersetzt `Panorama.tsx`; Test `PageFrame.test.tsx` aus `Panorama.test.tsx` übernehmen)
- Delete: `web/src/components/Panorama.tsx`, `Panorama.test.tsx`
- Modify: `web/src/components/PhotoSwitcher.tsx` (+ Test), `web/src/app/globals.css`
- Modify (nur Rahmen): `app/anmelden/page.tsx`, `app/meine-plaene/page.tsx`, `app/unterwegs/page.tsx`, `app/error.tsx`, `app/not-found.tsx`

**Interfaces:**
- Produces: `PageFrame({ children, back?, longDistance?, wide? }: { children: React.ReactNode; back?: { href: string; label: string }; longDistance?: { id: string; name: string }[]; wide?: boolean })` – gleiche Props wie `Panorama`. Hintergrund `bg-wald-dunkel`, Inhalt zentriert `max-w-6xl` (mit `wide` `max-w-7xl`), keine `drop-shadow`.
- Produces: `PhotoSwitcher({ photos, trailId?, className? })` – rendert ein `<figure>`: Bild `aspect-[4/3] w-full rounded-2xl object-cover` (Fallback `wald-verlauf`-Fläche gleicher Größe), darunter Vorschaubilder (bis 8, Klick wählt aus, `aria-label="Bild n"`, `aria-current` am aktiven), ‹/› und „n / m“, `Attribution`, „Foto löschen“, `PhotoUpload` wie bisher. Kein `fixed`-Element mehr.

- [ ] **Step 1: Tests anpassen/neu:** `PageFrame` rendert Logo-Link „Hike all about“, `back`-Link, Fernwege-Menü (aus Panorama-Test übernehmen). `PhotoSwitcher`: kein Element mit Klasse `fixed`; Klick auf „Bild 2“ zeigt das zweite Bild (`img[src]` wechselt) und die Attribution des zweiten; ohne Fotos und ohne `trailId` rendert es eine Fläche mit `data-testid="photo-fallback"`. Bestehende Upload-/Lösch-Tests behalten.
- [ ] **Step 2: Run** `npx vitest run src/components/PageFrame.test.tsx src/components/PhotoSwitcher.test.tsx` → FAIL.
- [ ] **Step 3: Implementieren.** In `globals.css` `--color-wald-flaeche: #284a32` ins `@theme`. In den fünf Seiten `Panorama` → `PageFrame`, `PhotoSwitcher photos={[]}` entfernen, `drop-shadow*` entfernen; helle Inhaltsblöcke behalten bzw. auf `bg-papier text-wald-dunkel` umstellen, wo bisher `bg-papier/15 backdrop-blur` auf Foto lag. Formularfelder in `anmelden`: `bg-wald-flaeche` statt `bg-black/20`.
- [ ] **Step 4: Run** `cd web && npm test && npm run lint && npx tsc --noEmit` → PASS (die übrigen Panorama-Nutzer – Startseite, Tourseite, Plan, Vorschläge – werden hier mit umgestellt, damit der Build hält; ihr Inhalt ändert sich erst in Aufgaben 4–7).
- [ ] **Step 5: Commit** `feat: dunkelgrüner Rahmen statt Fotohintergrund`

---

### Task 3: Eingebettete Karte mit Einkehr und Aussicht

**Files:**
- Modify: `web/src/components/MapPanel.tsx`, `MapPanel.test.tsx`, `web/src/components/PlanMap.tsx`, `TrailMap.tsx`, `web/src/app/globals.css` (Marker-Stil `.map-poi`)
- Modify: `web/src/app/unterwegs/…`/`Unterwegs.tsx` nur, falls die Signatur es verlangt (Unterwegs bleibt beim Knopf)

**Interfaces:**
- Consumes: `TrailPoi`, `POI_KIND` (Task 1).
- Produces:
  - `MapPanel({ trail, lodgings?, days?, position?, pois?, embedded? })` – `embedded` (Standard `false`): die Karte steht im Fluss (`h-[55vh] min-h-80 rounded-2xl overflow-hidden`), Legende darunter, Knopf „Vollbild“ öffnet das bisherige Overlay. Ohne `embedded` bleibt das Verhalten wie heute (Knopf „🗺 Karte“, für „Unterwegs“).
  - `pois?: TrailPoi[]` → je Punkt ein Marker (`button.map-poi`, Text = `POI_KIND[kind].icon`, `aria-label` = „Name, Label, km X“), Popup mit Name (oder Label), Label und „km X entlang des Wegs“, wenn `along_km` bekannt. Legende: „☕ Einkehr · 👁 Aussicht · 💧 Wasserfall“ nur für vorhandene Gruppen.
  - `PlanMap` und `TrailMap` reichen `pois?` und `embedded?` durch.
- Intern: den Karteninhalt (Container, Status, Marker, Legende) aus `MapOverlay` in `MapView({ …, className })` herausziehen; Overlay und eingebettete Ansicht nutzen `MapView`. maplibre wird weiterhin nur im Browser per `import()` geladen.

- [ ] **Step 1: Tests** (maplibre wie im bestehenden Test gemockt): mit `embedded` ist ohne Klick ein Element mit `data-map-status` im Dokument und ein Knopf „Vollbild“; Klick auf „Vollbild“ öffnet `role="dialog"`. Mit `pois=[food, viewpoint]` entstehen 2 Marker mit `aria-label`s, Legende enthält „Einkehr“ und „Aussicht“, nicht „Wasserfall“. Ohne `embedded`: bestehende Tests unverändert grün.
- [ ] **Step 2: Run** `npx vitest run src/components/MapPanel.test.tsx` → FAIL.
- [ ] **Step 3: Implementieren** (siehe Interfaces).
- [ ] **Step 4: Run** `cd web && npm test && npx tsc --noEmit` → PASS.
- [ ] **Step 5: Commit** `feat: Karte eingebettet, mit Einkehr und Aussicht`

---

### Task 4: Tourseite neu

**Files:**
- Modify: `web/src/app/t/[trailId]/page.tsx`, `page.test.tsx`
- Create: `web/src/components/TourDescription.tsx`, `ElevationProfile.tsx`, `WishChips.tsx` (client), `LodgingList.tsx`, `PoiList.tsx`, je mit Test
- Modify: `web/src/components/TrailMap.tsx` (`fromChat` statt `fromSuggestions`), `TrailMap.test.tsx`

**Interfaces:**
- Consumes: Task 1 (`getTrailPois`, `getTrailTags`, `describeTour`, `tagLabels`, `surfaceLine`, `POI_KIND`), Task 2 (`PageFrame`, `PhotoSwitcher`), Task 3 (`TrailMap … embedded pois`).
- Produces:
  - `fromChat(von: string | string[] | undefined): boolean` in `app/t/[trailId]/page.tsx`-Nachbardatei `web/src/lib/von.ts`: wahr für genau `"chat"` oder `"vorschlaege"`.
  - `TourDescription({ sentence, tags, surface, profile, trailId })`: Absatz, `WishChips`, Merkmal-Chips, Belagzeile, `ElevationProfile`; rendert `null`, wenn alles leer ist.
  - `ElevationProfile({ profile }: { profile: [number, number][] })`: SVG-Fläche (viewBox 0 0 300 60, `preserveAspectRatio="none"`), Beschriftung „Höhenprofil · 712–1.023 m“ (min–max aus den Daten), `role="img"` mit `aria-label` gleichen Inhalts.
  - `WishChips({ trailId })`: liest `useChat().state.last?.cards`, findet die Karte mit `trail_id === trailId`; rendert je `results`-Eintrag „✓ Rundweg“ / „✗ …“ / „? …“ (Beschriftung wie `Row` in `TourResultCard` – dafür `LABEL`/`UNIT` dort exportieren); ohne passende Karte `null`.
  - `LodgingList({ lodgings })`: die 5 nächsten nach `dist_m` (nulls last), je Name (oder `lodgingKind`), Art, „x m vom Weg“, Link über `lodgingLink` aus `lib/planView.ts`; Fußnote „Verfügbarkeit bitte auf der Website prüfen“. Leere Liste → `null`.
  - `PoiList({ pois })`: alle Punkte entlang des Wegs, je Icon, Name (oder Label), „km 3,2“ (nur wenn `along_km` bekannt). Leere Liste → `null`.

Seitenaufbau (Tagestour), von oben:
1. Kopf: Zurück-Link (`fromChat` → `{ href: "/", label: "← Zurück zu den Vorschlägen" }`, sonst `{ href: "/", label: "← Startseite" }`), `h1` Name (`text-papier`), Kennzahlen groß (`Facts`: Länge, Aufstieg, Abstieg, Gehzeit), rechts „Merken“ (`MerkenButton kind="day_hike"` nur, wenn eine passende Chat-Karte existiert – sonst weglassen; der Knopf erwartet eine `TourCard` als Payload) und Link „Unterwegs“.
2. `ChatShell variant="drawer"` mit bisherigem `intro`, `max-w-xl`.
3. `TrailMap embedded pois={pois} …`.
4. `grid md:grid-cols-[2fr_1fr]`: Block „Beschreibung“ (`TourDescription`) | Block „Übernachten in der Nähe“ (`LodgingList`).
5. `grid md:grid-cols-3`: „Fotos“ (`PhotoSwitcher photos={trail.photos} trailId`) | „Gruppen in der Nähe“ (`GroupList`) | „Einkehr & Aussicht“ (`PoiList`).
6. Quellen-Fußzeile wie bisher (Farbe `text-papier/75`).

Blöcke sind `rounded-2xl bg-papier p-4 text-wald-dunkel` mit `h2 font-serif`. Ein Block ohne Inhalt wird nicht gerendert, eine Reihe ohne Blöcke auch nicht. `getTrailPois`/`getTrailTags`/`getLodgings`/`getGroups` laden parallel; schlägt eines fehl, steht im betroffenen Block „… konnten nicht geladen werden“ (Unterkünfte, Einkehr) bzw. er fällt weg (Gruppen, Tags – wie heute). Fernweg: statt „Beschreibung“ die `StageCards` (volle Breite unter der Karte), Rest gleich.

- [ ] **Step 1: Tests**
  - `lib/von.test.ts`: `fromChat("chat")`, `fromChat("vorschlaege")` wahr; `undefined`, `"x"`, `["chat"]` falsch.
  - `page.test.tsx` (bestehende Mocks von `lib/data` erweitern um `getTrailPois`, `getTrailTags`): Überschrift „Beschreibung“ mit dem Satz aus `describeTour`; `von=chat` → Link „← Zurück zu den Vorschlägen“ auf `/`; ohne `von` → „← Startseite“; Tour ohne Unterkünfte, POIs, Gruppen → keine Überschriften „Übernachten in der Nähe“, „Einkehr & Aussicht“, „Gruppen in der Nähe“ und kein Text „0“; `getLodgings` wirft → „Unterkünfte konnten nicht geladen werden“ und die Seite rendert weiter; kein Element mit Klasse `fixed` (kein Fotohintergrund).
  - `WishChips.test.tsx`: mit ChatProvider-Zustand, dessen `last.cards` die Tour mit `results [{kind:"roundtrip", ok:true, bound:""}]` enthält → „✓ Rundweg“; ohne passende Karte → leeres Render.
  - `LodgingList.test.tsx`: 7 Unterkünfte → 5 Zeilen, nächste zuerst, „120 m vom Weg“; Link „Website“ bei sicherer URL, sonst „Suchen“.
  - `PoiList.test.tsx`: Reihenfolge wie geliefert, „km 3,2“, Icon ☕ für `food`; `along_km: null` → keine km-Angabe.
  - `ElevationProfile.test.tsx`: `aria-label` „Höhenprofil · 712–1.023 m“.
- [ ] **Step 2: Run** die neuen Tests → FAIL.
- [ ] **Step 3: Implementieren** (siehe Interfaces und Seitenaufbau).
- [ ] **Step 4: Run** `cd web && npm test && npm run lint && npx tsc --noEmit` → PASS.
- [ ] **Step 5: Sichtprüfung** `http://localhost:3000/t/<eine Tagestour mit POIs>` und `/t/westweg-west` im Browser (Desktop und 375 px): Karte ohne Klick sichtbar, Blöcke lesbar.
- [ ] **Step 6: Commit** `feat: Tourseite dunkelgrün mit Karte, Beschreibung, Übernachten, Einkehr`

---

### Task 5: Kachel ganz klickbar, `/vorschlaege` leitet um

**Files:**
- Modify: `web/src/components/TourResultCard.tsx`, `TourResultCard.test.tsx`
- Replace: `web/src/app/vorschlaege/page.tsx` (Server-Komponente mit `redirect("/")`), `page.test.tsx`

**Interfaces:**
- Produces: `TourResultCard({ card, runWithoutPace?, labels?, size?, from? })` mit `from?: "chat"`. Mit `from` ist die ganze Kachel ein Link (Overlay wie heute `after:absolute after:inset-0`) auf `/t/<id>?von=chat`, unten sichtbar „Details und Karte →“ (`aria-hidden`, der Name ist der Linktext). „Merken“ und Lizenzlinks bleiben `relative z-10`. Exportiert `LABEL` und `UNIT` für `WishChips`.

- [ ] **Step 1: Tests:** `from="chat"` → Link auf `/t/day-1?von=chat`, Text „Details und Karte →“ sichtbar; Klick auf „Merken“ ruft nicht die Navigation (bestehender Test anpassen). `/vorschlaege`: `redirect` aus `next/navigation` gemockt, `Vorschlaege()` ruft `redirect("/")`.
- [ ] **Step 2: Run** → FAIL. **Step 3:** Implementieren. **Step 4:** `npm test && npx tsc --noEmit` → PASS.
- [ ] **Step 5: Commit** `feat: ganze Kachel führt zur Tour, /vorschlaege leitet auf die Startseite`

---

### Task 6: Startseite mit Kacheln, Einzel-Vorschau und Plan-Vorschau

**Files:**
- Modify: `web/src/app/page.tsx`, `web/src/components/HomeStage.tsx`, `HomeStage.test.tsx`
- Create: `web/src/components/ResultsPane.tsx`, `TourPreview.tsx` (client), `PlanPreview.tsx`, je mit Test

**Interfaces:**
- Consumes: `TourResultCard from="chat"` (Task 5), `chipsFor` aus `ChatMessages`, `TrailMap embedded`, `describeTour`, `getTrail`/`getLodgings`/`getTrailPois`/`getTrailTags` (laufen auch im Browser, wie heute in `app/plan/page.tsx`).
- Produces:
  - `HomeStage({ photos }: { photos: Photo[] })`: ohne Ergebnis/Plan: Titel „Wandern im Schwarzwald“ + Untertitel + `ChatShell` links, `PhotoSwitcher photos` rechts (`md:grid-cols-2`, Handy untereinander). Mit `state.last.cards.length > 0` oder `state.plan`: `md:grid-cols-[24rem_1fr]`, links `ChatShell`, rechts `ResultsPane`; Titel klein über beiden. Der Link „Vorschläge zeigen →“ entfällt.
  - `ResultsPane()`: Plan → `PlanPreview`; genau 1 Karte → `TourPreview card={…}`; sonst Überschrift „n Touren gefunden“, Chips (`chipsFor(last.request…)`), `fallback`-Hinweis (amber, wie bisher), Raster `grid gap-4 sm:grid-cols-2 xl:grid-cols-3` mit höchstens 6 `TourResultCard from="chat" size="large"`, darunter fester Text „Zu viele? Schreib z. B. ‚mit Einkehr‘ oder ‚unter 300 Hm‘.“ (nur bei ≥ 2 Karten).
  - `TourPreview({ card, runWithoutPace, labels })`: Kachelkopf (Name, Kennzahlen, ✓/✗ wie Kachel), lädt im Browser Weg, Unterkünfte, POIs und Tags, zeigt `describeTour`-Satz und `TrailMap embedded`; Knopf „Zur Tour →“ auf `/t/<id>?von=chat`. Lädt der Weg nicht: Satz „Karte konnte nicht geladen werden“, Knopf bleibt.
  - `PlanPreview({ data }: { data: PlanData })`: `planTitle(data)`, je Tag eine kleine helle Kachel „Tag n · Start – Ziel · x km · Unterkunft“, Knopf „Plan mit Karte ansehen →“ auf `/plan`. Plan ohne Tage: die Notiz wie `planSummary`.
- `app/page.tsx`: Fotos wie bisher auswählen, an `HomeStage photos` geben; Fehler-/Leer-Zustände mit `PageFrame` und `HomeStage photos={[]}`.

- [ ] **Step 1: Tests** (ChatProvider mit vorbereitetem Zustand; `lib/data` gemockt):
  - 4 Karten → Überschrift „4 Touren gefunden“, 4 Links mit `?von=chat`, Hinweis „Zu viele?“; kein Link „Vorschläge zeigen“.
  - 1 Karte → Knopf „Zur Tour →“ auf `/t/<id>?von=chat`, Beschreibungssatz erscheint nach dem Laden (`findByText`).
  - Plan → Link „Plan mit Karte ansehen →“ auf `/plan`, eine Kachel je Tag.
  - Leerer Zustand → Überschrift „Wandern im Schwarzwald“, kein `ResultsPane`.
  - Spalten: Container hat `md:grid-cols-[24rem_1fr]` (Handy: ohne Präfix eine Spalte).
- [ ] **Step 2: Run** → FAIL. **Step 3:** Implementieren. **Step 4:** `npm test && npm run lint && npx tsc --noEmit` → PASS.
- [ ] **Step 5: Commit** `feat: Vorschläge als Kacheln auf der Startseite`

---

### Task 7: Planansicht mit Karte oben

**Files:**
- Modify: `web/src/app/plan/page.tsx` (+ neuer Test `page.test.tsx`), `web/src/components/PlanDays.tsx` (`mapHref` entfernen, Test anpassen)

**Interfaces:**
- Consumes: `PlanMap embedded` (Task 3), `useChat` (`state.plan`).
- Produces: `/plan` ohne `id`: `ChatPlan` liest `state.plan` (nach `hydrated`); ohne Plan „Noch kein Plan im Chat.“ + Link „Zur Startseite“. Mit Plan: Weg und Unterkünfte im Browser laden, `PlanMap embedded` **oben**, darunter `PlanDays data={plan}` (mit „Merken“), Zurück-Link „← Zurück zum Chat“ auf `/`. `/plan?id=…`: wie bisher, aber Karte oben und `PageFrame back` „← Meine Pläne“. Lädt der Weg nicht, fehlen nur Karte, die Tage bleiben.

- [ ] **Step 1: Tests:** ohne `id`, Chat mit Plan → Tage werden gerendert, `getTrail` aufgerufen mit `plan.trail_id`; `getTrail` wirft → Tage trotzdem da, kein Kartencontainer; ohne Plan → „Noch kein Plan im Chat.“; mit `id` und ohne Sitzung → Anmeldehinweis (bestehendes Verhalten).
- [ ] **Step 2: Run** → FAIL. **Step 3:** Implementieren. **Step 4:** `npm test && npx tsc --noEmit` → PASS.
- [ ] **Step 5: Commit** `feat: Planansicht nach dem Chat, Karte oben`

---

### Task 8: Aufräumen, Doku, Sichtprüfung

**Files:**
- Modify: `web/src/lib/chatState.ts` (Kommentare „/vorschlaege“ → „Startseite“), `web/src/components/ChatMessages.tsx` (Kommentar), `web/src/lib/contract.test.tsx` (Kommentar), `README.md` (Bildtexte, Abschnitt Oberfläche), `docs/presentation/demo-video.md` (Szene A2 ohne „Vorschläge zeigen“, Kacheln und Tourseite mit Karte), `docs/showcase/` (Screenshots neu, soweit ohne Modell möglich)

- [ ] **Step 1:** `grep -rn "vorschlaege\|Panorama\|drop-shadow" web/src` → nur noch die Weiterleitung und `fromChat` treffen.
- [ ] **Step 2:** Volle Prüfung `make test && make lint` → grün.
- [ ] **Step 3: Sichtprüfung im Browser** (Desktop 1440 px und 375 px): Startseite leer, nach einer Suche mit mehreren Touren, mit genau einer Tour, mit Plan; Tourseite Tagestour und Fernweg; `/plan`; Meine Pläne; Anmelden. Prüfen: kein Text auf Fotos, Karte ohne Klick sichtbar, keine horizontale Scrollleiste.
- [ ] **Step 4:** Screenshots in `docs/showcase/` neu aufnehmen (gleiche Dateinamen), README-Bildtexte anpassen, Drehbuch anpassen.
- [ ] **Step 5: Commit** `docs: Screenshots und Drehbuch nach dem neuen Layout`
