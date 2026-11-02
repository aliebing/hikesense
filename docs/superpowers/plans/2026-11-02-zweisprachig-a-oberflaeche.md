# Zweisprachig Teil A: Oberfläche – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Web-App zeigt alle eigenen Texte auf Englisch (Standard) oder Deutsch, umschaltbar über Fahnen 🇬🇧/🇩🇪 im Kopf; Zahlen und Daten im Format der Sprache; die Chat-Anfrage trägt die Sprache mit.

**Architecture:** Ein eigener Katalog (`web/src/i18n/en.ts`, `de.ts`, gleiche Schlüssel), ein `LocaleProvider` im Root-Layout mit `useT()`/`useLocale()`, Formatierung über `lib/format.ts` mit Locale-Parameter. Komponenten holen Texte nur noch aus dem Katalog. Das Backend nimmt `lang` an der Chat-API an (Standard `de`), nutzt es aber erst in Teil B.

**Tech Stack:** Next.js app router, React, TypeScript, Tailwind, Vitest/Testing Library; FastAPI/pydantic für das eine Backend-Feld.

**Spec:** `docs/superpowers/specs/2026-11-02-zweisprachig-design.md`

**Branch:** `zweisprachig-a` von `main` (nach dem Merge von Stufe 3 und „Knapp daneben“).

## Global Constraints

- Sprachen `en` (Standard) und `de`; Speicherung `localStorage["hikeall.lang"]`; ohne gespeicherte Wahl `en`.
- Fahnen-Knöpfe „🇬🇧“ und „🇩🇪“ mit `aria-label` „English“ / „Deutsch“, `aria-pressed` für die aktive Sprache.
- Intl-Locale: `en` → `en-GB`, `de` → `de-DE`; Zeitzone bleibt `Europe/Berlin`.
- URLs bleiben unverändert (deutsch).
- Texte, die vom Backend kommen (Antwort, Rückfrage, „Verstanden: …“, `deviation_text`, `bound`, Notizen, Wetter, Chat-Fehler), werden in Teil A **nicht** übersetzt.
- Englische Texte: natürliches britisches Englisch, kurz, gleicher Ton wie die deutschen (du → you). Fachwörter: „ascent“ für Höhenmeter (Einheit „m“), „round walk“ für Rundweg, „long-distance trail“ für Fernweg, „stage“ für Etappe, „Save result“ für „Ergebnis merken“, „My plans“ für „Meine Pläne“, „Near miss“ für „Knapp daneben“, „Backend“ bleibt „Backend“.
- Web-Tests: das Vitest-Setup setzt standardmäßig `de`, damit bestehende Tests mit deutschen Texten weiter gelten; jede Task fügt Tests für Englisch hinzu.
- Keine neue npm-Abhängigkeit.

## Review Focus

1. **Erster Aufruf ohne gespeicherte Wahl** – alles Englisch, `<html lang="en">`, kein kurzes Aufblitzen deutscher Texte nach dem Laden (Server rendert Englisch). Test in Task 1.
2. **Wechsel mitten im Chat** – Verlauf, Ergebnisse und Merken-Zustand bleiben, nur die Rahmentexte wechseln; die nächste Nachricht geht mit der neuen Sprache raus. Test in Task 2.
3. **Fehlender Katalogschlüssel** – TypeScript-Fehler (Typ `Messages` aus `en.ts`, `de.ts` muss ihn erfüllen); ein Test vergleicht die Schlüsselmengen. Task 1.
4. **Zahlen** – „11.6 km“, „1,200 m“ auf Englisch, „11,6 km“, „1.200 m“ auf Deutsch, überall wo die Web-App selbst formatiert. Test in Task 1 (format.ts) und je Seite.
5. **localStorage nicht verfügbar** (privates Fenster) – App läuft auf Englisch weiter, kein Absturz. Test in Task 1.

---

### Task 1: Katalog, Provider, Fahnen, Formatierung, Chat-Feld `lang`

**Files:**
- Create: `web/src/i18n/en.ts`, `web/src/i18n/de.ts`, `web/src/i18n/index.tsx` (Provider, Hooks), `web/src/components/LanguageFlags.tsx`, Tests dazu
- Modify: `web/src/app/layout.tsx` (Provider, `lang`), `web/src/components/PageFrame.tsx` und der Kopf der Startseite (`HomeStage.tsx`) – Fahnen neben dem Konto-Menü, `web/src/lib/format.ts` (+ Test), `web/vitest.setup.ts` (Standard `de`), `web/src/lib/chat.ts` (`lang` im Body), `backend/src/hikeall/api/chat.py` (`ChatRequest.lang: Literal["en","de"] = "de"`, an `run_chat` noch nicht weitergeben), Backend-Test

**Interfaces:**
- `type Locale = "en" | "de"`; `en.ts` exportiert `const en = {...} as const` und `type Messages = typeof en` (verschachtelte Objekte nach Bereich: `common`, `home`, `chat`, `results`, `tour`, `plan`, `account`, `admin`, `errors` …); Texte mit Platzhaltern als Funktionen, z. B. `tours: (n: number) => n === 1 ? "1 tour" : \`${n} tours\``.
- `de.ts`: `export const de: Messages = {...}`.
- `index.tsx`: `LocaleProvider({ children })`, `useLocale(): { locale: Locale; setLocale(l: Locale): void }`, `useT(): Messages`, `intlLocale(l: Locale): "en-GB" | "de-DE"`; setzt `document.documentElement.lang`; liest/schreibt `localStorage` in try/catch.
- `format.ts`: alle Helfer bekommen `locale: Locale` als letzten Parameter (Standard `"de"` nur für Übergangsaufrufe, am Ende von Task 4 entfernt).
- Chat-Body: `{ thread_id, message, lang }`.

- [ ] Step 1: Failing tests – Provider ohne Speicher → `en`; `setLocale("de")` speichert und rendert Deutsch; kaputtes `localStorage` (wirft) → `en`, kein Fehler; Schlüsselmengen `en`/`de` gleich (rekursiver Vergleich); `LanguageFlags` mit `aria-pressed`; `format.ts` für beide Locales (`km(11.6,"en") === "11.6 km"`, `"de"` → `"11,6 km"`, Höhenmeter `1,200 m`/`1.200 m`); Chat-Body enthält `lang`; Backend: `ChatRequest` akzeptiert `lang` und lehnt `"fr"` mit 422 ab, ohne Feld gilt `de`.
- [ ] Step 2: Run – FAIL. Step 3: Implement. Step 4: `npx vitest run && npx tsc --noEmit`, `cd backend && uv run pytest tests/test_api_chat.py -q` – PASS.
- [ ] Step 5: Commit `feat: Sprachkatalog, Fahnen und Sprache in der Chat-Anfrage`

### Task 2: Startseite und Chat

**Files:** `HomeStage.tsx`, `ChatShell.tsx`, `ChatMessages.tsx`, `ChatText.tsx` (nur eigene Texte), `WishChips.tsx`, `ResultsPane.tsx`, `TourResultCard.tsx`, `MerkenButton.tsx`, `AccountMenu.tsx`, `app/anmelden/page.tsx`, `lib/auth.ts` (Fehlermeldungen), `lib/chat.ts` (ERROR_*-Texte der Web-App), `lib/chatState.ts`, `app/page.tsx`, zugehörige Tests.
- Alle sichtbaren Texte, `aria-label`, `title`, `alt`, `placeholder` aus dem Katalog; Zahlen über `format.ts` mit der aktiven Locale.
- [ ] Failing tests (Englisch): Startseite zeigt englische Überschrift „Hiking in the Black Forest, at Lake Constance and in the Palatinate Forest“; Chat-Platzhalter englisch; Ergebnis-Kachel zeigt „round walk“/„ascent“ und „Near miss“; „Save result“; Anmelden-Seite englisch; Wechsel der Sprache mitten im Chat lässt Nachrichten und Ergebnisse stehen. Bestehende deutsche Tests bleiben grün (Setup `de`).
- [ ] Implement, `npx vitest run && npx tsc --noEmit` – PASS. Commit `feat: Startseite und Chat auf Englisch und Deutsch`

### Task 3: Tourseite, Plan, Unterwegs, Karte

**Files:** `app/t/[trailId]/page.tsx`, `app/plan/page.tsx`, `app/unterwegs/page.tsx`, `Unterwegs.tsx`, `MapPanel.tsx`, `TrailMap.tsx`, `PlanMap.tsx`, `PlanDays.tsx`, `PlanPreview.tsx`, `TourPreview.tsx`, `TourDescription.tsx` / `lib/tour.ts` (`describeTour`, POI-Arten, Tag-Labels – Tag-Labels englisch über den Katalog, Schlüssel = tag_id), `LodgingList.tsx`, `PoiList.tsx`, `GroupList.tsx`, `EventCards.tsx`, `ElevationProfile.tsx`, `StageCards.tsx`, `PhotoSwitcher.tsx`, `PhotoUpload.tsx`, `lib/photo.ts`, `lib/planView.ts`, `Attribution.tsx`, Tests.
- [ ] Failing tests (Englisch) je Hauptkomponente (mindestens Tourseite, PlanDays, MapPanel-Legende, LodgingList, PhotoUpload-Fehler, describeTour); Implement; Run – PASS; Commit `feat: Tourseite, Plan und Karte auf Englisch und Deutsch`

### Task 4: Meine Pläne, Gemerkt, Admin, Rahmen

**Files:** `app/meine-plaene/page.tsx`, `app/gemerkt/page.tsx`, `lib/plans.ts` (`searchTitle` bleibt Momentaufnahme; Rahmentexte übersetzt), `app/admin/page.tsx`, `components/admin/*`, `lib/admin.ts` (Formatierer mit Locale; Status 401/403/503/0 → Katalogtexte), `app/error.tsx`, `app/not-found.tsx`, `app/layout.tsx` Metadaten (englisch), `public/manifest.webmanifest` (`lang: "en"`, englischer Name/Beschreibung), `public/sw.js` (Offline-Text zweisprachig), Tests.
- `format.ts`-Standardparameter `"de"` entfernen; alle Aufrufer geben die Locale mit (TypeScript erzwingt es).
- [ ] Failing tests (Englisch) für Meine Pläne, Gemerkt (Fehltexte), Admin („No access“, Tabellenkopf, Summenzeile), not-found; grep-Test: kein `"de-DE"` mehr außerhalb von `i18n/index.tsx` in `web/src` (außer Tests); Implement; Run – PASS; Commit `feat: Pläne, Admin und Rahmen auf Englisch und Deutsch`

### Task 5: Prüfung im Browser und README

- [ ] Web-App bauen und starten (`cd web && npx next build && npx next start --port 3100`, API auf 8000 bzw. der laufende Stack), mit Playwright (Chromium) Startseite, Tourseite, Meine Pläne, Admin je in Englisch und Deutsch öffnen, Screenshots nach `/tmp/claude-1000/-home-ali-projects-HikeAllAbout/11ed28bc-039f-4f41-86d7-dc5f3607e06f/scratchpad/i18n/`, und prüfen, dass auf Englisch kein deutscher Rahmentext übrig ist (außer Backend-Texten nach Spec 9 und Eigennamen).
- [ ] README: Abschnitt Sprache (Fahnen, Standard Englisch, was in Teil B noch folgt).
- [ ] Commit `docs: Sprache in README`
