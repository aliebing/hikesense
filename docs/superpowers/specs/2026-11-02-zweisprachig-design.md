# Zweisprachige App (Englisch / Deutsch)

Stand: 2026-11-02. Wunsch von Ali: „Hauptsprache ist Englisch“, App zweisprachig wie gewünscht „mit Fahnen“; Englisch Standard, Deutsch umschaltbar. Danach Videos auf Englisch. Ali hat Claude beauftragt, das in seiner Abwesenheit zu entwerfen und zu bauen („einfach alles durchführen“) – alle Entscheidungen unten außer den drei ersten sind **Claudes Entscheidungen** und werden Ali als Liste berichtet.

## Entscheidungen von Ali

1. Zwei Sprachen: **Englisch (Standard)** und **Deutsch**.
2. Umschalter **mit Fahnen** in der Kopfzeile.
3. Die Videos (nach dieser Stufe) auf Englisch.

## Claudes Entscheidungen

4. **Fahnen** 🇬🇧 / 🇩🇪 als zwei Knöpfe im Kopf (aktive Sprache hervorgehoben, `aria-label` „English“/„Deutsch“). Die Wahl wird in `localStorage` (`hikeall.lang`) gespeichert; ohne gespeicherte Wahl gilt Englisch (nicht die Browsersprache – „Englisch Standard“).
5. **Zwei Teile**, je eigener Plan und Branch: **A – Oberfläche** (alle Texte der Web-App, Zahlen-/Datumsformat, Fahnen, `<html lang>`, Admin-Seite eingeschlossen) und **B – Assistent** (Antworten, feste Sätze, Rückfragen, Abweichungstexte, Wetter- und Mehrtages-Notizen in der gewählten Sprache).
6. Web ohne neue Bibliothek: eigener kleiner Katalog `web/src/i18n/en.ts` und `de.ts` (gleiche Schlüssel, TypeScript prüft Vollständigkeit), `LocaleProvider` + `useT()`; Formatierung über `Intl` mit `en-GB` bzw. `de-DE` (km, m, Stunden; Zeitzone weiter Europe/Berlin).
7. **URLs bleiben deutsch** (`/meine-plaene`, `/gemerkt`, `/t/…`) – Umbenennen bräche gespeicherte Links und bringt keinen Nutzen.
8. **Sprache je Nachricht**: Die Chat-Anfrage trägt `lang: "en" | "de"`. Fehlt das Feld (alte Clients, Tests, Eval, Smoke), gilt **Deutsch** – so bleiben alle bestehenden deutschen Tests, die Eval und der Smoke unverändert gültig. Die Web-App schickt die Sprache immer mit.
9. Texte, die das Backend schreibt und die Web-App nur anzeigt (Antwort, Rückfragen, „Verstanden: …“, `deviation_text`, `bound`, Mehrtages-Notizen, Wetter-Text, Fehlermeldungen des Chats), erzeugt das Backend **in der Sprache der Anfrage** (Teil B). Bis Teil B fertig ist, kommen sie deutsch – Teil A übersetzt nur, was die Web-App selbst schreibt.
10. **Gespeicherte Ergebnisse und Pläne** bleiben in der Sprache, in der sie gespeichert wurden (Momentaufnahme, wie bisher). Rahmentexte um sie herum folgen der gewählten Sprache.
11. **Wissensquellen bleiben deutsch** (Wikipedia/Wikivoyage de); bei Englisch antwortet das Modell auf Englisch auf Grundlage der deutschen Quellen, Quellentitel bleiben im Original.
12. **Zahlenprüfung (Grounding)** kennt beide Schreibweisen: bei Englisch „11.6 km“, „1,200 m“, englische Einheiten- und Zahlwörter (Teil B). Der Code schreibt Zahlen in seinen festen Sätzen im Format der Sprache.
13. **Eingaben** dürfen in beiden Sprachen kommen (unabhängig vom Umschalter); die Ortsauflösung bleibt bei den Original-Ortsnamen. Merkmal-Tags bekommen englische Labels und Synonyme (`label_en`, `synonyms_en` in `data/tags/features.yaml`), z. B. „inn“, „viewpoint“, „waterfall“.
14. Eval und Smoke bleiben deutsch; der Smoke bekommt zusätzlich drei englische Anfragen.
15. Admin-Backend wird mit übersetzt (Teil A), API-Fehlermeldungen (`detail`) bleiben deutsch und werden in der Web-App über Statuscodes auf Katalogtexte abgebildet.

## Nicht-Ziele

- Keine weitere Sprache, keine übersetzten Tour-/Ortsnamen, keine englischen Wissensquellen, keine Übersetzung bereits gespeicherter Inhalte.

## Anti-Ziele

- Ein Sprachwechsel darf keine Daten verlieren (Chat-Verlauf, gemerkte Ergebnisse).
- Gemischte Oberfläche (halb Englisch, halb Deutsch) bei gewählter Sprache – außer den unter 9 genannten Backend-Texten bis Teil B fertig ist.

## Bestandsaufnahme (Recon 2026-11-02)

- Web: keine i18n-Bibliothek; `<html lang="de">`, Manifest `lang: de`; ca. 250–350 deutsche Texte in ~40 Dateien (meist MapPanel, Tourseite, Unterwegs, TourResultCard, SearchDetail, chat.ts, meine-plaene, photo.ts, ChatMessages, tour.ts, PlanDays, GroupList); ~100 aria/title/alt/placeholder; `de-DE` in ~20 Dateien, zentrale Helfer in `lib/format.ts`; Tag-Labels doppelt in `lib/tour.ts`.
- Backend: Texte vor allem in `agent/prompts.py`, `agent/understand.py` (inkl. deutscher Zahlwörter/Monate in Regexen), `agent/constraints.py`, `agent/graph.py`, `agent/grounding.py` (nur deutsches Zahlenformat), `agent/multiday.py`, `agent/weather.py`, `adapters/open_meteo.py`, `agent/events.py`, `api/*`, `regions.py`, `numfmt.py`.
- Tests mit deutschen Texten: Backend ~270 Zeilen in ~21 Dateien, Web ~550 Zeilen in ~45 Dateien – deshalb Entscheidung 8 (Deutsch als API-Standard) und in Teil A: Web-Tests rendern standardmäßig auf Deutsch (Test-Setup setzt `de`), neue Tests prüfen Englisch.
