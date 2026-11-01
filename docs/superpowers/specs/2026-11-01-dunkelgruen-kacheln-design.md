# Dunkelgrünes Layout, Kacheln auf der Startseite, Tourseite mit Karte

Stand: 2026-11-01. Ersetzt in Teilen die Optik aus `2026-10-30-optik-wie-cinesense-design.md`.

## Warum

Ali gefällt die Aufmachung noch nicht. Konkret:

1. Nach einer Chat-Antwort muss man erst „Vorschläge zeigen →“ klicken und landet auf einer eigenen Seite. Ali will die Vorschläge **sofort auf der Startseite als Kacheln** sehen.
2. Auf der Vorschlagsseite und der Tourseite steht **weißer Text auf einem verschwommenen Foto**. Das ist schlecht lesbar.
3. **Wie man zur Karte kommt, ist nicht klar.** Die Karte steckt hinter einem kleinen Knopf „🗺 Karte“ (Overlay in `MapPanel.tsx`).
4. Vorbild für die Übersichtlichkeit ist HikeAi2 (`~/projects/HikeAi2`, Streamlit): Kacheln mit Foto und Kennzahlen, Karte und Details ohne Umwege. Die Farben von HikeAi2 übernimmt Ali ausdrücklich **nicht**.

Erfolg heißt: Ein Besucher sieht nach der ersten Antwort Kacheln, versteht ohne Erklärung, dass ein Klick zur Tour führt, und sieht dort die Karte sofort, ohne einen Knopf zu suchen. Die App soll schöner und ruhiger wirken.

## Entscheidungen von Ali

- **Aufbau B** (im Browser gewählt): Startseite mit Chat links und Kacheln rechts daneben, die Tour öffnet sich auf einer **eigenen Seite**. Nicht Aufbau A (alles auf einer Seite wie HikeAi2).
- **Eine Tour gefunden:** Statt Kacheln gleich Beschreibung und Karte.
- **Mehrere Touren:** Der Chat bietet an, weiter einzugrenzen, oder man klickt eine Kachel.
- **Tourseite** wie im Entwurf `.superpowers/brainstorm/…/content/tourseite.html`, von Ali mit „passt so“ bestätigt: von oben nach unten Name und Kennzahlen mit „Merken“ und „Unterwegs“, große Karte mit Weg, Start, Unterkünften, Einkehr und Aussicht, darunter die Blöcke **Beschreibung** (Häkchen je Wunsch, Merkmale, Belag, Höhenprofil) und **Übernachten in der Nähe** nebeneinander, dann **Fotos**, **Gruppen in der Nähe** und **Einkehr & Aussicht** in drei Spalten, unten die Quellen.
- **Dunkelgrün überall:** Tourseite, Fernweg-Seiten, Mehrtagesplan, „Meine Pläne“, „Unterwegs“ bekommen dunkelgrünen Grund (`--color-wald-dunkel` #1f3f27) **ohne Hintergrundbild**. Inhalte stehen in hellen Blöcken (`--color-papier`) mit dunkler Schrift.
- **Startseite darf ihr Foto behalten**, aber nicht als verschwommenen Vollbild-Hintergrund hinter Text (siehe „Startseite“ unten).
- **Screenshots und Video** werden nach dem Umbau neu aufgenommen.

## Ziele

- Kacheln auf der Startseite direkt nach der Antwort, ohne Zwischenseite.
- Karte auf Tour- und Planseite direkt sichtbar, nicht hinter einem Knopf.
- Kein Text mehr direkt auf Fotos; Kontrast mindestens 4,5:1 für Fließtext.
- Alle vorhandenen Informationen zur Tour lesbar aufbereitet, inklusive Einkehr und Aussicht (bisher nur in der Datenbank, nicht in der Web-App).

## Nicht-Ziele

- Keine Änderung am Backend, am Agenten oder an der Evaluation. Die Chat-Ereignisse (`results`, `plan`, …) bleiben wie sie sind.
- Kein neuer Beschreibungstext vom Sprachmodell. Die Beschreibung setzt der Code aus Daten zusammen (siehe unten), damit die Regel „jede Zahl aus der Datenbank“ gilt.
- Keine GPX-Datei, keine neuen Datenimporte.
- Keine Farben von HikeAi2.

## Anti-Ziele (wäre ein Fehlschlag, auch wenn es technisch läuft)

- Text, der wieder auf einem Foto steht oder schlecht lesbar ist.
- Eine Karte, die man erst suchen oder aufklappen muss.
- Eine Beschreibung, die Zahlen nennt, die nicht in der Datenbank stehen.
- Eine Startseite, auf der Kacheln und Chat auf dem Handy nicht mehr bedienbar sind.

## Seiten im Einzelnen

### Startseite (`app/page.tsx`, `HomeStage.tsx`)

- **Vor der ersten Nachricht:** wie bisher Titel „Wandern im Schwarzwald“, Untertitel und Chat. Das Foto bleibt, aber als klar begrenztes Bild (z. B. Kopfbild oben oder rechte Hälfte), nicht als verschwommener Vollbild-Hintergrund. Der übrige Grund ist dunkelgrün. Fotonachweis bleibt am Bild.
- **Nach einer Antwort mit Touren (`state.last.cards`):** zweispaltig ab `md`: links der Chat (schmal, ca. 24 rem), rechts Überschrift („4 Touren um Hinterzarten“), die erkannten Wünsche als Chips, ggf. der ehrliche Hinweis (`fallback`, gelb wie bisher) und die Kacheln im Raster (2 Spalten, ab `xl` 3). Auf dem Handy untereinander: Chat, dann Kacheln.
- **Genau eine Tour:** statt der einen Kachel eine größere Vorschau mit Beschreibung und eingebetteter Karte der Tour plus Knopf „Zur Tour →“. *(Meine Annahme: Ali meint die Vorschau auf der Startseite; die volle Tourseite bleibt einen Klick entfernt.)*
- **Mehrere Touren:** unter den Kacheln bzw. im Chat ein kurzer Hinweis „Zu viele? Schreib z. B. ‚mit Einkehr‘ oder ‚unter 300 Hm‘“. Der Hinweis ist fester Text der Oberfläche, kein Modelltext.
- **Mehrtagesplan im Chat (`state.plan`):** rechts statt der Kacheln eine Plan-Vorschau (Tage als Kacheln: Tag, Strecke, km, Unterkunft) und ein Knopf „Plan mit Karte ansehen →“ zur Planansicht.
- *Meine Entscheidung:* Die Planansicht nach dem Chat ist `/plan` **ohne** `id`: sie liest den aktuellen Plan aus dem `ChatProvider` (wie heute `/vorschlaege`) und zeigt Karte mit Tagesabschnitten oben, darunter die Tage. Ohne Plan im Chat: Hinweis und Link zur Startseite. Gemerkte Pläne bleiben `/plan?id=…` (angemeldet, `saved_plans`).
- Der Knopf „Vorschläge zeigen →“ entfällt.

### Kachel (`TourResultCard.tsx`)

- Heller Block mit Foto oben (Nachweis wie bisher), Name, Kennzahlen (km, Hm, Gehzeit, Entfernung zum Start) und ✓/✗/? je Bedingung wie bisher.
- **Die ganze Kachel ist klickbar** und führt zur Tourseite; sichtbarer Hinweis „Details und Karte →“ unten in der Kachel. „Merken“ bleibt als eigener Knopf (Klick darauf öffnet nicht die Tour).

### Vorschlagsseite (`app/vorschlaege`)

- Entfällt als eigener Einstieg. Die Route bleibt erreichbar und leitet immer auf `/` um, damit alte Links nicht ins Leere führen (Pläne laufen über `/plan`, siehe Startseite).
- Der Parameter `?von=vorschlaege` an Tourseiten-Links wird zu `?von=chat` und heißt: „kam aus einer Chat-Suche“; der Zurück-Link führt dann auf `/` („← Zurück zu den Vorschlägen“). Alte Links mit `von=vorschlaege` gelten gleich.

### Tourseite (`app/t/[trailId]/page.tsx`), Tagestour

Dunkelgrüner Grund, kein `PhotoSwitcher`-Hintergrund. Reihenfolge:

1. Kopf: Zurück-Link („← Zurück zu den Vorschlägen“, wenn man von der Startseite kam, sonst „← Startseite“), Name, Kennzahlen groß (Länge, Aufstieg, Abstieg, Gehzeit), Knöpfe „Merken“ und „Unterwegs“.
2. **Karte eingebettet**, volle Breite, ca. 50–60 vh hoch: Weg, Start, Unterkünfte, Einkehr, Aussicht, mit Legende. Vollbild bleibt als Zusatzknopf möglich.
3. Zwei Spalten (Handy: untereinander):
   - **Beschreibung** (breiter): ein vom Code gebauter Absatz aus Daten, z. B. „Rundweg, 11,4 km mit 389 Hm Aufstieg, Gehzeit etwa 3:54 h nach DIN 33466. Unterwegs 2 Einkehrmöglichkeiten und 1 Aussichtspunkt.“; darunter Chips: erfüllte Wünsche (*meine Entscheidung:* ein Client-Baustein liest die ✓/✗ aus dem Chat-Zustand, `state.last.cards` mit passender `trail_id`; steht die Tour dort nicht, z. B. bei einem geteilten Link, fallen diese Chips still weg) und Merkmale (`trail_tags`, Beschriftung aus dem Tag-Vokabular); Belaganteile (`surface_shares`); Höhenprofil (`profile`).
   - **Übernachten in der Nähe**: die nächsten Unterkünfte aus `trail_lodgings_geo`, sortiert nach Abstand zum Weg, mit Abstand und Link zur Website; Hinweis „Verfügbarkeit bitte auf der Website prüfen“.
4. Drei Spalten (Handy: untereinander): **Fotos** (Raster der Commons-Fotos mit Nachweis, „Eigenes Foto hinzufügen“ wie bisher), **Gruppen in der Nähe** (`GroupList` wie bisher, mit Prüfstatus), **Einkehr & Aussicht** (`trail_pois` + `pois`: Einkehr, Hütte, Aussicht, Gipfel, Wasserfall, mit km entlang des Wegs). *Meine Entscheidung:* alle Zeilen aus `trail_pois`, die der Import zugeordnet hat (er verknüpft nur Punkte bis 300 m vom Weg, `POI_BUFFER_M` in `backend/src/hikeall/ingest/places.py`), ohne `kind = station`. Beschreibungssatz, Liste und Kartenebene nutzen genau diese Auswahl, damit die Anzahlen übereinstimmen. Einkehr = `food` + `hut`, Aussicht = `viewpoint` + `peak`, dazu `waterfall`.
5. Quellen-Fußzeile wie bisher.

**Chat bleibt auf der Tourseite** (Ali): als aufklappbarer Chat wie bisher (`ChatShell variant="drawer"`), z. B. unten rechts fixiert oder oberhalb der Karte, so dass er die eingebettete Karte nicht verdeckt. Er teilt den Gesprächsverlauf mit der Startseite (`ChatProvider`).

Ein Block ohne Daten fällt weg (kein „0 Unterkünfte“). Lädt ein Block nicht, steht dort ein kurzer Hinweis, die übrige Seite bleibt.

### Tourseite, Fernweg (`/t/westweg-west` usw.)

Gleicher Rahmen. Statt „Beschreibung“ einer Tagestour die Etappen (`StageCards`) als helle Kacheln; Karte mit allen Etappen eingebettet. Übernachten, Fotos, Gruppen, Einkehr wie oben.

### Mehrtagesplan (`PlanDays.tsx`, `app/plan`, Planansicht nach dem Chat)

Dunkelgrün, Karte mit Tagesabschnitten **eingebettet oben** (bisher Link „Karte mit Tagesabschnitten“), darunter die Tage als helle Blöcke wie bisher (Unterkunft, Ankunft, Wetter, Regenvariante).

### „Meine Pläne“, „Unterwegs“, Anmelden

Nur der Rahmen: dunkelgrüner Grund statt Foto, Inhalte in hellen Blöcken. Keine Funktionsänderung.

## Gestaltung

- Farben aus `globals.css`: Grund `--color-wald-dunkel` #1f3f27, Blöcke `--color-papier` #f4f1ea, Akzent `--color-wald` #2f5d3a; für Hinweise weiter Amber. Ein zweiter, etwas hellerer Grünton für Flächen auf dunklem Grund ist erlaubt.
- Schrift wie bisher (Serif für Überschriften, Sans für Text). Keine Schlagschatten mehr nötig (`drop-shadow` fällt mit dem Foto weg).
- Kartenlinien und Nummern in Farben, die sich auch in der Helligkeit unterscheiden.

## Was offen bleibt (für den Umsetzer)

- Wie genau das Startseitenfoto platziert wird (Kopfbild oder halbe Seite), solange kein Text darauf steht.
- Ob die Einkehr-/Aussichtspunkte als eigene Kartenebene oder nur als Liste erscheinen; beides ist im Entwurf, die Liste ist Pflicht.
- Komponentenschnitt (z. B. ein gemeinsamer `PageFrame` statt `Panorama` + `PhotoSwitcher`), Datenladen für POIs und Tags (`lib/data.ts`).
- Tests: bestehende Tests anpassen, neue für Kachel-Klick, Weiterleitung `/vorschlaege` → `/`, Beschreibungstext aus Daten, leere Blöcke fallen weg.
- Nach dem Umbau: Screenshots in `docs/showcase/` neu, README-Texte zu den Bildern anpassen, Video nach `docs/presentation/demo-video.md` (Szene A2 „Vorschläge zeigen“ entfällt).
