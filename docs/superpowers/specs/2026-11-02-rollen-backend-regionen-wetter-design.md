# Rollen, Admin-Backend, mehr Regionen, Wetter-Tagesfinder

Stand: 2026-11-02. Vier Stufen, in dieser Reihenfolge gebaut. Jede Stufe ist für sich lauffähig und wird einzeln geplant und gemergt.

## Warum

Ali will HikeAllAbout in vier Schritten erweitern:

1. Benutzer sollen Rollen haben und sich Ergebnisse merken können.
2. Ein Admin soll in einem eigenen Backend jede Suche mit allen Details nachvollziehen können (Kosten, Tokens, Prompts, Tool-Aufrufe, warum welche Tour gezeigt oder verworfen wurde), pro Benutzer.
3. Neben dem Schwarzwald sollen **Bodensee** (mit Schweizer und österreichischem Ufer) und **Pfälzerwald** dazukommen, wie bei HikeAi2 (`~/projects/HikeAi2`), auch mit **Fernwanderwegen und Etappen**.
4. Die App soll zu einem Wetterwunsch („Feldberg bei schönem Wetter“, „wenn es schneit“) selbst die passenden Tage finden.

**Ausdrücklich: Qualität vor Anzahl.** HikeAi2 hat 2.004 Routen (767 Schwarzwald, 406 Bodensee, 831 Pfälzerwald), weil es automatisch nach einem Beliebtheits-Score auswählt und dabei auch Wege mit Lücken, sehr kurze/lange Wege und Ort-zu-Ort-Verbindungen nimmt. HikeAllAbout behält seine strengeren Auswahlregeln; die Zahl soll nicht auf Kosten der Qualität steigen.

## Ausgangslage (Stand heute)

- Login und Registrierung per E-Mail/Passwort über Supabase Auth gibt es schon (`web/src/app/anmelden/page.tsx`, `web/src/lib/auth.ts`). Das Backend prüft das Supabase-JWT (`backend/src/hikeall/auth.py`). Es gibt **keine Rollen**; der Admin ist nur das Konto `admin@hikeall.local` (`backend/src/hikeall/admin.py`, `make admin-user`).
- „Merken“ speichert eine Tour oder einen Mehrtagesplan als Momentaufnahme in `saved_plans` (`supabase/migrations/20261030000001_*.sql`), angezeigt unter `/meine-plaene`.
- Jede Chat-Anfrage schreibt eine Zeile nach `data/logs/chat.jsonl` (`backend/src/hikeall/chatlog.py`): Tokens, Kosten, Anzahl Tool-Aufrufe, Grounding-Zähler, Fehler, nur ein Hash des Benutzers. Bisher bewusst **ohne** Text, Prompts, Tool-Details und Benutzer-ID.
- Routen: 4 Fernwanderwege (46 Etappen) und 122 Tagestouren, nur Schwarzwald (`BLACK_FOREST_BBOX` in `backend/src/hikeall/models.py`). Tagestouren: `data/curated/day_hikes.csv`, 1.712 gescannt, 122 übernommen.
- Wetter: Open-Meteo bis 14 Tage, nur für ein vom Nutzer genanntes Datum (`backend/src/hikeall/agent/weather.py`).

---

## Stufe 1: Rollen und gemerkte Ergebnisse

### Entscheidungen von Ali

- Zwei Rollen: **Benutzer** und **Admin**. Nur der Admin sieht das Backend.
- Benutzer werden in der Datenbank gespeichert.
- Ein Benutzer kann sich **Ergebnisse merken**: Das Ergebnis einer Suche wird beim Benutzer gespeichert und beim Öffnen genau so wieder gezeigt (Momentaufnahme, **keine** neue Suche). „Das reicht.“

### Was gebaut wird

- **Tabelle `profiles`** (eine Zeile pro Benutzer): `user_id` (= `auth.users.id`), `email`, `role` (`user` | `admin`, Default `user`), `created_at`. Wird per Trigger beim Registrieren angelegt; bestehende Konten (auch Admin und Smoke-Benutzer) werden in der Migration nachgetragen. RLS: jeder liest nur seine eigene Zeile; niemand außer dem Service ändert `role`. *(Builder-Entscheidung von Claude: eigene Tabelle statt `app_metadata`, weil Ali „Speicherung der Benutzer in der Datenbank“ wollte und das Backend die Benutzerliste daraus liest.)*
- **Admin-Rolle vergeben:** `make admin-user` setzt für `admin@hikeall.local` zusätzlich `role = 'admin'`. Keine Rollenverwaltung in der Oberfläche. *(Claudes Annahme, Ali hat nicht widersprochen.)*
- **Rollenprüfung im Server**, nicht nur in der Oberfläche: FastAPI liest die Rolle zum geprüften JWT aus `profiles`; Admin-Endpunkte geben sonst 403.
- **Ergebnis merken:** Auf der Startseite gibt es zu einer Antwort mit Kacheln einen Knopf „Ergebnis merken“. Gespeichert werden Suchtext (die Nachricht(en) des Benutzers), die Antwort und die gezeigten Touren-Karten. Umsetzung als neuer `kind = 'search'` in `saved_plans` (Payload: Suchtext, Antworttext, Karten, Zeitpunkt). *(Claudes Entscheidung: bestehende Tabelle, RLS und Seite weiterverwenden.)*
- **Anzeige** auf `/meine-plaene` in einem eigenen Abschnitt „Gemerkte Suchen“ neben den gemerkten Touren und Plänen. Öffnen zeigt Suchtext, Antwort und Kacheln wie damals; Klick auf eine Kachel führt zur heutigen Tourseite. Löschen wie bei Plänen.
- Bestehendes „Merken“ für einzelne Touren/Pläne bleibt unverändert.

### Nicht-Ziele

- Keine weiteren Rollen, kein Rollen-Editor, kein Passwort-Reset-Flow, keine E-Mail-Bestätigung (bleibt `enable_confirmations = false`).
- Gemerkte Suchen werden nicht neu ausgeführt und nicht bearbeitet.

---

## Stufe 2: Admin-Backend

### Entscheidungen von Ali

- Eigener Backend-Bereich; Einloggen wie heute im Frontend, nur eben für das Backend. Nur Admin.
- **Keine neue Tabelle für Suchen**: Das Backend zeigt die Suchen **aus den Logs** (`data/logs/chat.jsonl`).
- Der Log darf dafür ab jetzt **Suchtext, Prompts, Tool-Aufrufe und die echte Benutzer-ID** enthalten.
- Aufbau **A mit Tabelle darunter** (im Browser gewählt, Entwurf `.superpowers/brainstorm/133811-1793610352/content/backend-layout-v2.html`, von Ali mit „so passt das“ bestätigt):
  - links **Benutzer** (mit „Alle“ und Anzahl Suchen),
  - Mitte **letzte Suchen** des gewählten Benutzers (Suchtext, Zeit, Kosten),
  - rechts **Details** der gewählten Suche,
  - darunter **Tabelle aller Suchen** (folgt der Benutzer-Auswahl) mit Zeit, Benutzer, Suchtext, Intent, Treffer (mit Hinweis „Ausweich“), Tools, Tokens, Kosten, Dauer, Fehler und einer Summenzeile (Anzahl, Kosten, Ø Dauer).
- In den Details eine **Begründung, warum Touren gefunden und gezeigt wurden – auch die verworfenen** mit Grund.

### Details einer Suche (rechte Spalte, von oben nach unten)

1. Suchtext, Benutzer, Zeit, Intent, Aktivität.
2. **So verstanden**: die strukturierte Anfrage (`HikeRequest`: Ort/Gebiet, Radius, Länge, Höhenmeter, Rundweg, Dauer, Datum, Vorlieben/Meiden).
3. **Antwort** des Assistenten und Ergebnis der Zahlenprüfung (belegt / ersetzt / entfernt, aus den vorhandenen Grounding-Zählern).
4. **Warum diese Touren?** Tabelle je Kandidat: Name, jede harte Bedingung mit ✓/✗/? und echtem Wert (aus `ConstraintResult` in `agent/constraints.py`: Länge, Höhenmeter, Rundweg, Entfernung, Dauer), erfüllte/fehlende/gemiedene Vorlieben (`PreferenceMatch`), Punktzahl, Status *gezeigt*, *gezeigt als Ausweich* oder *verworfen*; dazu der Ausweich-Satz (`Selection.reason`) bzw. Widerspruch. Verworfene: die **20 besten** nach den gezeigten, ausgegraut. *(Die Grenze 20 ist Claudes Entscheidung.)* Bei Mehrtagesplänen statt dessen: gewählter Weg, Etappen mit Länge und gewählter Unterkunft. Bei Wissensfragen/Veranstaltungen entfällt der Block.
5. **Tool-Aufrufe**: nummeriert, Name, Argumente als JSON, Ergebnis (gekürzt, aufklappbar voll).
6. **Modell · Tokens · Kosten · Dauer**: je LLM-Aufruf und Summe; Kosten nur wie von OpenRouter gemeldet (wie heute in `llm/usage.py`), nie geschätzt.
7. **Prompts** (aufklappbar): System- und Nutzer-Prompt jedes LLM-Aufrufs (understand, answer, react …).

### Was gebaut wird

- **Log erweitern** (`chatlog.py`): pro Anfrage zusätzlich `user_id`, Suchtext (die aktuelle Nachricht; bei Verfeinerungen auch die vorherigen Nachrichten der Unterhaltung), verstandene Anfrage, Antworttext, Prompts und Usage je LLM-Aufruf, Tool-Aufrufe mit Argumenten und Ergebnis, Kandidaten mit Prüfergebnis und Status, Gesamtdauer. Eine Zeile bleibt eine Anfrage; bisherige Felder bleiben, damit alte Auswertungen weiter laufen.
- **Alte Zeilen** (840, ohne Text und Details): 808 davon tragen `user_hash` (erste 12 Zeichen von sha256 der Benutzer-ID, `chatlog.hash_user`). Das Backend berechnet diesen Hash für jedes Profil und **ordnet die alten Zeilen so ihren Benutzern zu** (Ali: „ok“). Sie zeigen nur, was sie haben (Kosten, Tokens, Zähler). Zeilen ohne Hash oder ohne passendes Profil sowie Anfragen ohne Login erscheinen unter „Unbekannt“.
- **API** (FastAPI, nur Admin): Benutzerliste (aus `profiles` plus Zählung im Log), Suchen-Liste mit Filter nach Benutzer und Paging, Detail einer Suche über `request_id`. Liest die JSONL-Datei; bei der zu erwartenden Größe genügt Einlesen pro Anfrage, Builder darf cachen.
- **Seite `/admin`** im Next-Frontend, Login über das bestehende Anmelden; Nicht-Admins sehen nur „Kein Zugriff“. Desktop-Layout genügt.
- **Vorlage**: HikeAi2 hat einen ähnlichen Admin-Bereich mit Protokoll je Aufruf (`~/projects/HikeAi2/src/hikeai/admin/`), CineSense eine Detailansicht einer Suche (`~/projects/CineSenseAi/web/app/tech/page.tsx`). Beide als Anregung für Inhalt und Darstellung, nicht als Code zum Kopieren. Optik passend zum bestehenden HikeAllAbout-Stil.

### Nicht-Ziele

- Keine Bearbeitung von Benutzern oder Rollen, keine Modell-Umschaltung, keine Auswertungsgrafiken.
- Keine Datenbanktabelle für Suchen.

### Anti-Ziele

- Das Backend darf für Nicht-Admins weder über die Seite noch über die API Daten liefern.
- Der Log darf weiter keine Passwörter oder Tokens (JWTs, API-Keys) enthalten.

---

## Stufe 3: Bodensee und Pfälzerwald, fehlende Schwarzwald-Routen

### Entscheidungen von Ali

- Neue Regionen **Bodensee inkl. Schweiz und Österreich** und **Pfälzerwald**, wie in HikeAi2.
- **Qualität vor Anzahl**: Dieselben Auswahlregeln wie im Schwarzwald (Länge 5–30 km, keine Lücken im Verlauf, kein Fernweg als Tagestour, eigenständige Tagestour statt Ort-zu-Ort-Verbindung). Ähnlich viele Routen wie HikeAi2 sind **kein** Ziel.
- **Fernwanderwege mit Etappen** auch in den neuen Regionen, wie im Schwarzwald (mit Unterkünften und Mehrtagesplanung).

### Was gebaut wird

- **Regionen statt fester Box**: Liste der Regionen mit Id, Name, Bounding-Box und Ländern; Boxen aus `~/projects/HikeAi2/data/regions.yaml` übernehmen, Pfälzerwald nur DE (die Box reicht ins Elsass). *(Claudes Entscheidung.)* Fernwege über Regionsgrenzen (z. B. Querweg Schwarzwald–Bodensee) regelt das Regionsmodell, Builder entscheidet. Jede Tour, Unterkunft, jeder Ort usw. gehört zu einer Region. `check_in_region` prüft gegen die passende Region.
- **Schwarzwald-Lücke: kein Fehler, bleibt wie sie ist** *(Entscheidung Ali, 2026-11-02)*: Die 127 HikeAi2-Routen fehlen im Scan, weil es `network:type=node_network`-Abschnitte des Schwarzwaldvereins sind (1–4 km, Wegweiser zu Wegweiser). Sie sind absichtlich gefiltert (`ingest/day_hikes.py`, Test `test_day_hikes.py:77`) und unter 5 km; sie bleiben draußen.
- **Tagestouren** für Bodensee und Pfälzerwald: `scan-day-hikes`/`import-day-hikes` je Region mit denselben automatischen Regeln. Die bisherige manuelle Stufe (Claude schlägt vor, Ali bestätigt) gilt auch hier; Claudes Vorschläge sind als solche markiert, wie heute in der CSV.
- **Fernwanderwege**: vier Wege mit Etappen, kuratiert in `data/curated/trails.yaml`: Pfälzer Weinsteig, Pfälzer Waldpfad, Jubiläumsweg Bodenseekreis und SeeGang *(Auswahl Ali, 2026-11-02; Recherche: `docs/superpowers/specs/2026-11-02-stufe3-fernwege-recherche.md`)*. Beim SeeGang sind die Etappen-km nicht offiziell; die Quelle trägt diesen Hinweis. Kriterien wie bisher: Etappen mit Quelle, durchgehende OSM-Relation, liegt überwiegend in der Region.
- **Daten für die neuen Gebiete**: weitere Copernicus-DEM-Kacheln (u. a. N47/E009, N49/E007, N49/E008), Unterkünfte und Orte für Rheinland-Pfalz, Bayern, Schweiz, Österreich (weitere PBF-Auszüge oder Overpass, Builder entscheidet), Commons-Fotos mit den bestehenden Filtern (`prune-photos`), Wissenstexte (Wikipedia/Wikivoyage) zu den neuen Regionen, Tags für die neuen Touren.
- **Assistent regionsfähig**: Guard, Prompts, `understand.py`, Tag-Vokabular und Frontend-Texte, die heute fest „Schwarzwald“ sagen, kennen alle drei Regionen. Ortsangaben in der Schweiz und Österreich werden aufgelöst. Startseite/Texte nennen alle drei Regionen.
- README und Zählungen aktualisieren.

### Nicht-Ziele

- Keine weiteren Regionen; keine Lockerung der Qualitätsregeln, um auf HikeAi2-Zahlen zu kommen.
- Keine Übernahme der HikeAi2-Suchtechnik (Text-/Vektorsuche, Multi-Query, HyDE); HikeAllAbout bleibt bei Ortssuche plus Prüfregeln.

---

## Stufe 4: Wetter-Tagesfinder

### Entscheidungen von Ali

- Kommt **nach** den Stufen 1–3.
- Bei Anfragen wie „Feldberg-Wanderung bei schönem Wetter“ oder „wenn es schneit“ sucht die App die Tage, an denen das Wetter gut ist bzw. zur Suche passt, **falls vorhanden**.

### Was gebaut wird

- **Wetterwunsch verstehen**: `HikeRequest` bekommt einen Wetterwunsch (z. B. sonnig/trocken, Schnee). Das LLM erkennt ihn, der Code prüft ihn.
- **Tage finden**: Für den Ort der gefundenen Tour(en) prüft der Code die Vorhersage der nächsten 14 Tage (bestehender Horizont, Open-Meteo, inklusive Schneefall) und nennt die passenden Tage mit den Werten. Feste, im Code definierte Schwellen für „schön“ und „Schnee“ (Builder legt sie fest und dokumentiert sie).
- **Ehrlich**: Gibt es keinen passenden Tag, sagt die App das und nennt die besten verfügbaren Tage. Nie geschätzt, Vorhersage nie erfunden; Zahlen laufen durch die Zahlenprüfung.
- **Mehrtagestouren**: Zeitraum mit passendem Wetter für alle Etappentage suchen, sonst ehrlich sagen, dass es keinen gibt.
- Die Wetterprüfung erscheint auch im Admin-Backend (Tool-Aufruf bzw. eigener Block).

### Nicht-Ziele

- Keine Vorhersage über 14 Tage hinaus, keine Klimastatistik, keine Wetterwarnungen über das Bestehende hinaus.

---

## Für alle Stufen

- Bestehende Konventionen gelten: deutsche Oberfläche, Kosten nur wie gemeldet, Code entscheidet und prüft, das LLM formuliert; Tests wie im Projekt üblich (pytest im Backend, Vitest im Web).
- Screenshots/Video werden erst nach allen Stufen neu aufgenommen.
- Der offene, uncommittete Stand auf dem Branch `hintergrund-feinschliff` wird vor Beginn abgeschlossen; jede Stufe auf eigenem Branch.

## Dem Builder überlassen

- Technische Form der Region-Definition, des API-Pagings, eines Log-Caches.
- Genaue Gestaltung von `/admin` und dem Abschnitt „Gemerkte Suchen“ im Rahmen des bestehenden Stils.
- Datenquelle für Unterkünfte/Orte außerhalb Baden-Württembergs.
- Schwellen für den Wetterwunsch.
