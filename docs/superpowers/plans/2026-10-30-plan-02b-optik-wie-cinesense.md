# Plan 2b – Optik wie CineSense: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Startseite wird eine ruhige Bühne wie bei CineSense: Hintergrundbilder blenden langsam ineinander, davor ziehen blasse Tour-Kacheln vorbei, links steht der Chat. Passende Touren werden klar und anklickbar, „Vorschläge zeigen →“ führt zu einer eigenen Vorschlagsseite, und von dort geht es zur Routenansicht mit Karte.

**Architecture:** Das Gespräch wird aus `ChatShell` in einen Client-Provider im Root-Layout gehoben (`ChatProvider`, gespiegelt in `sessionStorage`). Dadurch teilen Startseite, `/vorschlaege` und `/t/[trailId]` denselben Verlauf und dieselbe letzte Trefferliste. Bewegung entsteht nur durch CSS-Animationen, und `prefers-reduced-motion` schaltet sie ab. Kacheln kommen wie bisher aus Supabase (`getTrails`), passende Touren aus dem Chat-Stream. Das Backend bleibt unverändert.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, Tailwind 4 (`@theme` in `web/src/app/globals.css`), Vitest + Testing Library (jsdom). Es kommen keine neuen Abhängigkeiten hinzu.

**Spec:** `docs/superpowers/specs/2026-10-30-optik-wie-cinesense-design.md` (Grundlage: `docs/superpowers/specs/2026-10-28-hike-all-about-design.md` §10/§11). Vorbild zum Nachlesen, nicht zum Kopieren: `~/projects/CineSenseAi/web/components/atmosphere/HeroSlides.tsx`, `FogLight.tsx` und `components/home/TileRows.tsx`.

## Global Constraints

- Alle Regeln aus Plan 2 gelten weiter: Zahlen und Touren kommen nur aus Code oder Datenbank, Ausweichen wird offen benannt („Keine Tour erfüllt alle Wünsche, weil …“), Quellen und Lizenzen sind sichtbar. Ein Foto ohne Autor und Lizenz wird nie gezeigt (wie `coverOf`).
- Die Oberfläche ist auf Deutsch. Farben `wald`/`wald-dunkel`/`papier` und `font-serif` stehen in `globals.css`.
- Kacheln auf der Startseite sind am Anfang blass und **nicht anklickbar**. Passende Kacheln werden klar und sind Links auf `/t/<trail_id>`.
- „Passend“ heißt: die Touren aus dem **letzten** `results`-Event. Ausweichtouren zählen dazu, ihre Kachel zeigt aber `deviation_text`. Höchstens **5** passende Kacheln.
- Ein `results`-Event mit `cards: []` setzt die Trefferliste auf leer: die Kacheln werden blass, der Knopf verschwindet. Andere Antworten (Rückfrage, Wissensfrage, Fehler, Abbruch) lassen die Trefferliste unverändert.
- Der Knopf „Vorschläge zeigen →“ ist nur sichtbar, wenn die Trefferliste nicht leer ist. Es gibt keinen automatischen Seitenwechsel.
- Ein Gespräch gilt pro Browser-Tab: `sessionStorage`-Schlüssel `hikeall.chat.v1`. Neuladen behält Verlauf, Thread-ID und Trefferliste.
- Die Routenansicht verlinkt mit `?von=vorschlaege` zurück, wenn man von der Vorschlagsseite kommt, sonst führt „Zurück“ zur Startseite.
- Bei `prefers-reduced-motion: reduce` stehen Hintergrund (ein Bild, kein Zoom), Nebel und Kachelreihen still.
- Auf dem Handy (< `sm`) gibt es eine Kachelreihe, passende Kacheln stehen vorn, der Nebel ist aus.
- Die bestehenden Tests für Chat-Protokoll (`lib/chat.test.ts`, `lib/contract.test.tsx`), Karte und Routenseite bleiben grün. Komponenten, die entfallen, werden mit ihren Tests gelöscht.

## Review Focus

1. **`sessionStorage` fehlt, ist voll oder enthält kaputtes JSON / alte Form:** Die App startet mit leerem Gespräch und stürzt nicht ab (Task 1, Test `starts fresh on corrupt storage`).
2. **Neuladen während einer laufenden Antwort:** Nach dem Laden ist `busy` false und keine halbe Antwort hängt im Status „denkt nach“ (Task 1, Test `busy is never restored`).
3. **Passende Tour ohne Foto oder nicht in den Reihen:** Sie erscheint trotzdem als klare Kachel (grüne Fläche mit Namen). Es gibt keine doppelte Kachel (Task 3, Tests `inserts a match that is not in the pool`, `match without photo`).
4. **`/vorschlaege` direkt aufgerufen oder nach einer Antwort ohne Treffer:** freundlicher Hinweis mit Link zur Startseite, keine leere Seite (Task 5, Test `without results shows a hint`).
5. **Leere Datenbank oder Supabase nicht erreichbar:** Die Startseite zeigt weiter Chat und Hinweis. Kachelreihen fehlen dann einfach (Task 4, bestehende `page.test.tsx`-Fälle angepasst).

---

## Dateien

| Datei | Verantwortung |
|---|---|
| `web/src/lib/chatState.ts` (neu) | reiner Reducer und Persistenz: `ChatState`, `reduceEvent`, `loadState`, `saveState` |
| `web/src/components/ChatProvider.tsx` (neu) | Context und `useChat()`. Hält den Stream und spiegelt nach `sessionStorage` |
| `web/src/components/ChatShell.tsx` (ändern) | nur Darstellung und Eingabe über `useChat()`. Prop `variant: "stage" \| "drawer"` |
| `web/src/components/ChatMessages.tsx` (ändern) | Ergebniseintrag ohne Karten: Fallback-Hinweis und Zeile „n Touren gefunden“ |
| `web/src/components/HeroBackdrop.tsx` (neu) | wechselnde Hintergrundbilder mit Ken-Burns, Nebel und Attribution des aktuellen Bildes |
| `web/src/lib/tiles.ts` (neu) | reine Funktion `arrangeTiles` |
| `web/src/components/TileRows.tsx` (neu) | laufende Kachelreihen, blass bzw. klar und als Link |
| `web/src/components/CreditsOverlay.tsx` (neu) | Overlay „Bildnachweise“ |
| `web/src/components/HomeStage.tsx` (neu) | Client-Teil der Startseite: Chat, Reihen, Knopf, Bildnachweise |
| `web/src/components/Panorama.tsx` (ändern) | Kopfzeile mit Menü „Fernwege“, Zurück-Ziel |
| `web/src/app/page.tsx` (ändern) | lädt Touren, rendert `HeroBackdrop` und `HomeStage` |
| `web/src/app/vorschlaege/page.tsx` (neu) | Vorschlagsseite |
| `web/src/app/t/[trailId]/page.tsx` (ändern) | Zurück-Link je nach `?von=vorschlaege`, neuer Look |
| `web/src/app/layout.tsx` (ändern) | `ChatProvider` um `children` |
| entfällt | `ChatStage.tsx`, `CoverContext.tsx` (und ihre Tests). `PhotoSwitcher` verliert den Cover-Zweig |

---

### Task 1: Gesprächszustand als Provider mit `sessionStorage`

**Files:**
- Create: `web/src/lib/chatState.ts`, `web/src/lib/chatState.test.ts`, `web/src/components/ChatProvider.tsx`, `web/src/components/ChatProvider.test.tsx`
- Modify: `web/src/components/ChatShell.tsx`, `web/src/components/ChatShell.test.tsx`, `web/src/components/ChatMessages.tsx`, `web/src/app/layout.tsx`, `web/src/app/t/[trailId]/page.tsx` (ChatShell-Aufruf)
- Delete: `web/src/components/ChatStage.tsx`, `web/src/components/CoverContext.tsx`, `web/src/components/ChatStage.test.tsx` und die Cover-Logik in `PhotoSwitcher.tsx` sowie deren Tests

**Interfaces:**
- Produces:
  ```ts
  // lib/chatState.ts
  export type LastResults = { cards: TourCard[]; fallback: string | null; runWithoutPace: boolean; labels: Labels };
  export type ChatState = {
    threadId: string;
    items: ChatItem[];
    /** null: nothing found yet, or the last search found nothing */
    last: LastResults | null;
    /** the last understood request (for chips on /vorschlaege); null before the first */
    request: { request: HikeRequest; labels: Labels } | null;
    /** internal: activity "run" without pace, carried from "understood" to "results" */
    runWithoutPace: boolean;
  };
  export const STORAGE_KEY = "hikeall.chat.v1";
  export function initialState(threadId: string): ChatState;
  export function reduceEvent(s: ChatState, e: ChatEvent): ChatState;   // pure; same item logic as today's ChatShell.apply
  export function addUser(s: ChatState, text: string): ChatState;
  export function addNotice(s: ChatState, text: string): ChatState;
  export function loadState(storage: Storage | null, newId: () => string): ChatState; // never throws
  export function saveState(storage: Storage | null, s: ChatState): void;            // never throws
  // components/ChatProvider.tsx
  export function ChatProvider({ children, apiUrl }: { children: React.ReactNode; apiUrl?: string }): JSX.Element;
  export function useChat(): { state: ChatState; busy: boolean; send(text: string): Promise<void>; abort(): void };
  // components/ChatShell.tsx
  export default function ChatShell(props: { intro: string; variant?: "stage" | "drawer" }): JSX.Element;
  ```
- `coverOf` aus `ChatShell.tsx` zieht nach `lib/chatState.ts` um (bleibt exportiert, Task 3/5 nutzen es).

- [ ] **Step 1: Failing tests in `lib/chatState.test.ts`**
  - `results replaces last`: Zwei `results`-Events nacheinander, `last.cards` sind die des zweiten.
  - `empty results clear last`: `results` mit Karten, dann `results` mit `cards: []` → `last === null`.
  - `clarify, token, sources and error keep last`: Nach `results` ändern diese Events `last` nicht.
  - `understood sets request and runWithoutPace`: `activity: "run"`, `pace_min_per_km: null` → das folgende `results` hat `last.runWithoutPace === true`.
  - `token appends to the last assistant item`: wie heute in ChatShell.
  - `starts fresh on corrupt storage`: `loadState` mit `"{kaputt"`, mit `{"v":0}` und mit einem `Storage`, dessen `getItem` wirft → `initialState` mit neuer ID.
  - `round trip`: `saveState`, dann `loadState` ergibt einen gleichen Zustand.
  - `saveState swallows quota errors`: `setItem` wirft, `saveState` wirft nicht.
- [ ] **Step 2:** `cd web && npx vitest run src/lib/chatState.test.ts` → FAIL (Modul fehlt).
- [ ] **Step 3:** `lib/chatState.ts` implementieren. Die Item-Logik zieht unverändert aus `ChatShell.apply` um. Gespeichert wird `{ v: 1, ...state }`. `loadState` akzeptiert nur `v === 1` mit `threadId` als String und `items` als Array.
- [ ] **Step 4:** Test läuft → PASS.
- [ ] **Step 5: Failing tests in `components/ChatProvider.test.tsx`** (mit gemocktem `streamChat` wie in `ChatShell.test.tsx`)
  - `shares one conversation`: zwei Konsumenten unter einem Provider. `send` im einen, der andere sieht das neue Item.
  - `restores from sessionStorage`: Vor dem Rendern einen Zustand mit `last` speichern. Nach dem Mount liefert `useChat().state.last` ihn.
  - `busy is never restored`: Gespeicherter Zustand, Mount → `busy === false`.
  - `abort adds the notice "Abgebrochen."` (wie heute).
- [ ] **Step 6:** `ChatProvider` implementieren. Den Zustand im ersten `useEffect` aus `window.sessionStorage` laden, damit es keine Hydration-Differenz gibt. Bei jeder Änderung speichern. Den Stream nach Unmount abbrechen (Logik aus ChatShell).
- [ ] **Step 7:** `ChatShell` auf `useChat()` umstellen. `variant="drawer"` rendert eine kompakte, einklappbare Fassung (`<details>` mit Zusammenfassung „Chat“). `ChatMessages` rendert beim `results`-Item keine `TourResultCard`s mehr. Es zeigt den Fallback-Hinweis wie heute und dazu `<p>` „{n} Touren gefunden“ bzw. „1 Tour gefunden“ bzw. bei 0 „Keine passende Tour gefunden.“. `ChatShell.test.tsx` anpassen: Rendern unter `ChatProvider`, Erwartungen zu Ergebniskarten werden zur Zeile „n Touren gefunden“. `layout.tsx` umschließt `children` mit `ChatProvider`. `/t/[trailId]` übergibt nur noch `intro`. `ChatStage`, `CoverContext` und den Cover-Zweig von `PhotoSwitcher` samt Tests löschen.
- [ ] **Step 8:** `cd web && npm test && npx tsc --noEmit && npm run lint` → alles grün.
- [ ] **Step 9:** Commit `feat(web): one conversation per tab, shared via a provider and sessionStorage`.

### Task 2: Bewegter Hintergrund

**Files:**
- Create: `web/src/components/HeroBackdrop.tsx`, `web/src/components/HeroBackdrop.test.tsx`
- Modify: `web/src/app/globals.css` (Keyframes und Reduced-Motion-Regeln)

**Interfaces:**
- Consumes: `Photo` aus `lib/data.ts`, `Attribution` aus `components/Attribution.tsx`.
- Produces: `export default function HeroBackdrop({ photos, intervalMs = 9000 }: { photos: Photo[]; intervalMs?: number }): JSX.Element` liegt fest hinter der Seite (`fixed inset-0 -z-10`) und zeigt unten rechts die Attribution des aktuellen Bildes.

- [ ] **Step 1: Failing tests**
  - `shows the first photo with its attribution`: Autor und Lizenz des ersten Fotos sind sichtbar.
  - `advances after the interval`: `vi.useFakeTimers()`, `intervalMs` weiterdrehen → Attribution des zweiten Fotos. Nach dem letzten kommt wieder das erste.
  - `reduced motion shows one still photo`: `matchMedia("(prefers-reduced-motion: reduce)")` gemockt `true` → nach `3 * intervalMs` immer noch das erste Foto. Das Element trägt kein Animations-Attribut (`data-motion="still"`).
  - `without photos the forest gradient`: `photos=[]` → Element mit Klasse `wald-verlauf`, keine Attribution.
  - `a broken image is skipped`: `onError` des aktuellen Bildes → das nächste Foto wird gezeigt.
- [ ] **Step 2:** `npx vitest run src/components/HeroBackdrop.test.tsx` → FAIL.
- [ ] **Step 3:** Implementieren: zwei übereinanderliegende `<img>`-Ebenen, die per Opacity überblenden (Dauer 1,5 s) und langsam zoomen (`scale(1)` → `scale(1.08)` über die Standzeit), dazu eine Nebel-Ebene (radiale Verläufe, langsame `translateX`-Animation, unter `sm` ausgeblendet). Keyframes `hike-kenburns`, `hike-fog` in `globals.css`. `@media (prefers-reduced-motion: reduce)` setzt `animation: none`, und die Komponente prüft zusätzlich `matchMedia`, damit der Timer nicht läuft.
- [ ] **Step 4:** Test → PASS. Danach `npm test`.
- [ ] **Step 5:** Commit `feat(web): slow cross-fading landscape backdrop with fog`.

### Task 3: Kachelreihen

**Files:**
- Create: `web/src/lib/tiles.ts`, `web/src/lib/tiles.test.ts`, `web/src/components/TileRows.tsx`, `web/src/components/TileRows.test.tsx`
- Modify: `web/src/app/globals.css` (Keyframe `hike-drift`)

**Interfaces:**
- Consumes: `TrailSummary` (`lib/data.ts`), `TourCard` (`lib/chat.ts`), `coverOf` (`lib/chatState.ts`).
- Produces:
  ```ts
  // lib/tiles.ts
  export type Tile = {
    id: string;                 // trail id
    name: string;
    photo: Photo | null;        // null → green surface with the name
    match: null | { deviation: string | null };   // null = pale, not clickable
  };
  /** rows × perRow tiles, no trail twice; matches (≤ 5, in card order) replace pale tiles,
   *  spread one per row first; a match not in the pool is built from its TourCard. */
  export function arrangeTiles(pool: TrailSummary[], matches: TourCard[], rows: number, perRow: number): Tile[][];
  // components/TileRows.tsx
  export default function TileRows({ pool, matches }: { pool: TrailSummary[]; matches: TourCard[] }): JSX.Element;
  ```

- [ ] **Step 1: Failing tests `lib/tiles.test.ts`**
  - `fills rows without duplicates`: Pool mit 30 Touren, `arrangeTiles(pool, [], 3, 8)` → 3 Reihen mit je 8 Kacheln, 24 verschiedene IDs, alle `match === null`.
  - `small pool`: 5 Touren, 3×8 → keine Tour doppelt. Reihen dürfen kürzer sein, und leere Reihen fallen weg.
  - `matches become clear in place`: Ein Treffer, der schon im Pool steht, bekommt `match` gesetzt und steht genau einmal da.
  - `inserts a match that is not in the pool`: Er ersetzt eine blasse Kachel. Die Gesamtzahl bleibt gleich, die ID kommt einmal vor.
  - `match without photo`: TourCard ohne `cover_author` → `photo === null`, `match !== null`.
  - `at most five matches`: 7 Karten → genau 5 Kacheln mit `match`, nämlich die ersten 5.
  - `fallback carries the deviation`: `deviation_text: "340 Hm statt < 200"` → `match.deviation` hat genau diesen Text.
- [ ] **Step 2:** FAIL. **Step 3:** `arrangeTiles` implementieren. Die Pool-Reihenfolge ist die von `pickSpread`, damit das Ergebnis deterministisch bleibt. **Step 4:** PASS.
- [ ] **Step 5: Failing tests `TileRows.test.tsx`**
  - `pale tiles are not interactive`: ohne Treffer keine `link`-Rolle in den Reihen. Die Reihen sind `aria-hidden`.
  - `matches are links`: ein Treffer → genau ein `link` mit `href="/t/<id>"` und dem Namen als zugänglichem Namen, außerhalb von `aria-hidden`.
  - `fallback tile shows the deviation`: Text „340 Hm statt < 200“ ist an der Kachel sichtbar.
- [ ] **Step 6:** Implementieren. Jede Reihe wird doppelt gerendert und per `hike-drift` endlos verschoben (`translateX(0)` → `translateX(-50%)`, 60–90 s, jede zweite Reihe rückwärts). Blasse Kacheln haben etwa `opacity-35 saturate-50`, passende `opacity-100` mit hellem Rand und weichem Übergang (`transition 700ms`). Passende Kacheln sind nur in der ersten Kopie der Reihe Links, die zweite Kopie ist `aria-hidden` und `tabIndex=-1`, damit Screenreader keine Doppelungen hören. Unter `sm` rendert die Komponente nur die erste Reihe, Treffer vorn. Reduced motion → `animation: none`.
- [ ] **Step 7:** `npm test` → PASS. Commit `feat(web): drifting tour tiles that turn clear and clickable when they match`.

### Task 4: Startseite zusammensetzen

**Files:**
- Create: `web/src/components/HomeStage.tsx`, `web/src/components/HomeStage.test.tsx`, `web/src/components/CreditsOverlay.tsx`
- Modify: `web/src/app/page.tsx`, `web/src/app/page.test.tsx`, `web/src/components/Panorama.tsx`
- Delete: Nutzung von `CardRow`/`TrailCard` auf der Startseite. `StageCards.tsx` bleibt, die Routenseite nutzt es.

**Interfaces:**
- Consumes: `useChat` (Task 1), `HeroBackdrop` (Task 2), `TileRows`/`arrangeTiles` (Task 3), `getTrails`/`pickSpread` (`lib/data.ts`).
- Produces:
  - `HomeStage({ pool }: { pool: TrailSummary[] })`: Client-Komponente mit Titel und Untertitel, `ChatShell variant="stage"`, `TileRows pool={pool} matches={state.last?.cards ?? []}`, dem Knopf „Vorschläge zeigen →“ als `Link href="/vorschlaege"` (nur wenn `state.last` nicht leer ist) und dem Knopf „Bildnachweise“.
  - `CreditsOverlay({ photos, onClose }: { photos: Photo[]; onClose(): void })`: Dialog (`role="dialog"`, `aria-label="Bildnachweise"`), Liste mit Autor, Lizenz (Link) und Commons-Seite, schließt per Knopf und mit Escape.
  - `Panorama({ children, back }: { children; back?: { href: string; label: string } })`: Kopfzeile mit Logo, Menü „Fernwege“ (Prop `longDistance: { id: string; name: string }[]`, optional; ohne Einträge entfällt das Menü) und optionalem Zurück-Link.

- [ ] **Step 1: Failing tests `HomeStage.test.tsx`** (unter `ChatProvider`, mit vorgeladenem `sessionStorage`)
  - `no button before results`: kein Link „Vorschläge zeigen →“.
  - `button after results`: gespeicherter Zustand mit `last.cards` → Link „Vorschläge zeigen →“ mit `href="/vorschlaege"`.
  - `empty results hide the button`: `last === null` nach leerem `results` → kein Link.
  - `credits list visible tile photos`: Klick auf „Bildnachweise“ → Dialog listet Autor und Lizenz einer Kachel. Escape schließt ihn.
- [ ] **Step 2:** FAIL. **Step 3:** Implementieren. `page.tsx` bleibt Server-Komponente. Sie lädt `getTrails()`, bildet `pool = pickSpread(trails, 24)` und die Hintergrundbilder (Covers der Fernwege und von `pickSpread(trails, 8)`, ohne doppelte URLs). Gerendert werden `Panorama` (mit Fernwege-Menü), `HeroBackdrop` und `HomeStage`. Die Fehler- und Leerzustände bleiben wie heute (Hinweis plus Chat, keine Reihen). Footer mit den Datenquellen wie heute, ohne „Urheber und Lizenz am Bild“, stattdessen „Fotos: Wikimedia Commons, siehe Bildnachweise“. Layout ab `md`: Chat links (≈ 40 %), Reihen rechts (≈ 55 %) vertikal zentriert. Unter `md` steht der Chat oben, darunter eine Reihe. Die Kartenreihen „Fernwege“ und „Tagestouren“ fallen weg. Weil `Panorama.back` jetzt ein Objekt ist, ruft `/t/[trailId]/page.tsx` es vorerst mit `back={{ href: "/", label: "← Zur Startseite" }}` auf (Task 6 macht es abhängig von `?von`).
- [ ] **Step 4:** `page.test.tsx` anpassen: Die Fälle für DB-Fehler und leere DB bleiben. Neu: `renders chat and tile rows`, `menu lists long-distance trails`. Der alte Fall zur Cover-Übernahme entfällt.
- [ ] **Step 5:** `npm test && npx tsc --noEmit && npm run lint` → grün. Commit `feat(web): home as a quiet stage with chat, drifting tiles and a suggestions button`.

### Task 5: Vorschlagsseite

**Files:**
- Create: `web/src/app/vorschlaege/page.tsx`, `web/src/app/vorschlaege/page.test.tsx`
- Modify: `web/src/components/TourResultCard.tsx` (Variante groß mit Bild, Link mit `?von=vorschlaege`), `web/src/components/TourResultCard.test.tsx`

**Interfaces:**
- Consumes: `useChat` (Task 1), `chipsFor` (`ChatMessages.tsx`), `TourResultCard`, `HeroBackdrop` (Task 2, Bilder sind die Covers der Treffer).
- Produces: `TourResultCard({ card, runWithoutPace, labels, size = "compact", from })` mit `size: "compact" | "large"` und `from?: "vorschlaege"`. Bei gesetztem `from` lautet der Link `/t/<id>?von=vorschlaege`, und die ganze Karte ist klickbar (`after:absolute after:inset-0` wie bei `ImageCard`).

- [ ] **Step 1: Failing tests**
  - `shows chips, sentence and cards`: Zustand mit `request` (Rundweg, Länge 10–14 km), `last` mit 3 Karten und einem Assistenten-Text → Chips „Rundweg“ und „Länge 10–14 km“, der Antwortsatz und 3 Links auf `/t/<id>?von=vorschlaege`.
  - `fallback note first`: `last.fallback = "Keine Tour erfüllt alle Wünsche, weil …"` → Hinweis steht vor den Karten, jede Karte zeigt ihre `deviation_text`.
  - `without results shows a hint`: leerer Zustand → Text „Noch keine Vorschläge.“ und Link „Zur Startseite“ (`href="/"`), keine Karten.
  - `chat drawer is present`: Ein `<details>` mit der Zusammenfassung „Chat“ ist vorhanden. Ein neues `results`-Event aus dem Drawer ersetzt die Karten.
- [ ] **Step 2:** FAIL. **Step 3:** Implementieren als Client-Seite (`"use client"`). Oben `Panorama` mit Zurück zur Startseite („← Zum Chat“), darunter Chips und Antwortsatz (letztes `assistant`-Item nach dem letzten `results`, ohne Fallback-Satz wie `withoutFallback`), dann ein Raster mit 3–5 großen Karten (`sm:grid-cols-2 lg:grid-cols-3`), rechts bzw. unten der Drawer-Chat. Der Hintergrund ist `HeroBackdrop` mit den Covers der Treffer (`coverOf`).
- [ ] **Step 4:** PASS, `npm test`. Commit `feat(web): suggestions page with chips, honest fallback and large tour cards`.

### Task 6: Routenansicht im neuen Look

**Files:**
- Modify: `web/src/app/t/[trailId]/page.tsx`, `web/src/app/t/[trailId]/page.test.tsx`

**Interfaces:**
- Consumes: `Panorama` mit `back` (Task 4), `HeroBackdrop` (Task 2), `ChatShell variant="drawer"` (Task 1).

- [ ] **Step 1: Failing tests**
  - `back to suggestions`: `searchParams = { von: "vorschlaege" }` → Link „← Zu den Vorschlägen“ mit `href="/vorschlaege"`.
  - `back to home otherwise`: ohne Parameter → „← Zur Startseite“ mit `href="/"`.
  - `unknown von is ignored`: `von: "https://evil"` → Zurück zur Startseite.
- [ ] **Step 2:** FAIL. **Step 3:** `searchParams` lesen (Next 15: `Promise`). Statt `PhotoSwitcher` kommt `HeroBackdrop` mit `trail.photos`. Ein Durchblättern von Hand ist hier nicht mehr nötig, die Bilder wechseln selbst. Bildnachweise wie auf der Startseite: `HeroBackdrop` zeigt die Attribution des aktuellen Bildes. Der Chat wird zum Drawer. Karte, Eckdaten, Etappen und Quellen bleiben.
- [ ] **Step 4:** `PhotoSwitcher.tsx` löschen, falls ihn nichts mehr nutzt, samt Test. `npm test && npx tsc --noEmit && npm run lint` → grün.
- [ ] **Step 5:** Sichtprüfung: `make up`, Startseite, eine Nachricht („Rundweg 10–14 km um Hinterzarten, unter 400 Hm“), Kacheln werden klar, Knopf, Vorschlagsseite, Route mit Karte, Zurück. Ergebnis kurz im Commit-Text oder in der README-Chat-Anleitung vermerken, falls sich Bedienschritte geändert haben (README „Chat starten“, Punkt 3).
- [ ] **Step 6:** Commit `feat(web): trail view in the new look, back link to the suggestions`.
