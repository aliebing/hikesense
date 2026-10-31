# Evaluation

Der Eval-Lauf schickt einen festen Testsatz von 52 Chat-Anfragen an den echten Agenten. Die
Antworten werden mit Code geprüft, nicht von Hand und nicht von einem zweiten Modell. Aus den
Ergebnissen berechnet der Lauf die Kennzahlen für die vier SMART-Ziele und gleicht alle gezeigten
Touren mit OpenStreetMap ab.

**Aktueller Bericht:** [bericht-2026-10-31-openai-gpt-4o-mini.md](bericht-2026-10-31-openai-gpt-4o-mini.md)
(Einzelergebnisse: [results-2026-10-31-openai-gpt-4o-mini.csv](results-2026-10-31-openai-gpt-4o-mini.csv))

| Ziel | Ist-Wert (Lauf vom 2026-10-31) | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0 von 74 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen | erreicht |
| ≤ 2 % nicht belegte Zahlen | 0 von 530 Zahlen (0,0 %) | erreicht |
| 100 % offen benannte Unerfüllbarkeit | 8 von 8 Fällen | erreicht |
| Recall@5 ≥ 0,8 | 10 von 10 Fällen (1,00) | erreicht |

Bestanden haben 52 von 52 Fällen. Die Fehler, die frühere Läufe fanden, stehen unter
[Befunde](#befunde). Im Abgleich mit OSM weichen 0 von 82 Touren und Plantagen um mehr als 2 % ab.

## Lauf

```sh
make smoke-user   # einmal: legt das Testkonto smoke@hikeall.local an
make eval         # = cd backend && uv run hikeall eval [--cases PFAD]
```

Der Lauf braucht `OPENROUTER_API_KEY`, `HIKEALL_MODEL`, `HIKEALL_SMOKE_PASSWORD` und die
Supabase-Werte in `.env`. Außerdem müssen die lokale Datenbank und der Wissensindex (`make knowledge`) bereitstehen.

- **Anmeldung:** Wie `make smoke` meldet sich der Lauf als Testkonto an und prüft das Token wie
  `POST /chat`. Danach laufen die Fälle über denselben Graphen wie der Chat, mit echtem Modell,
  echter Datenbank und echtem Index.
- **Wetter und Datum:** Das Wetter kommt aus `data/eval/weather.json`. Das sind echte
  Open-Meteo-Tageswerte für die Etappenorte aller Fernwege, abgerufen am 2026-10-31, für den
  2026-11-02 bis 2026-11-15. Das „heute“ im Chat ist fest der 2026-11-02 (`EVAL_TODAY`). Eine
  Anfrage nutzt den nächsten gespeicherten Ort im Umkreis von 25 km. Fehlt ein Ort oder ein
  Datum, scheitert der Fall mit einer Meldung, ohne live nachzufragen.
- **Ausgaben:** `docs/evaluation/results-<Datum>-<Modell>.csv` enthält je Fall Gruppe, ok,
  unbelegte Zahlen und Namen, Kosten und Fehler. `bericht-<Datum>-<Modell>.md` enthält
  SMART-Tabelle, Gruppen, OSM-Abgleich und die nicht bestandenen Fälle. Der Exit-Code ist 1,
  sobald ein Fall nicht besteht.
- **Prüfregel:** Erwartungen werden nie gelockert, damit ein Fall besteht. Ist ein Fall selbst
  falsch und der Code richtig, wird der Fall korrigiert und die Korrektur in `cases.yaml`
  begründet.

## Testsatz

Die Fälle stehen in `data/eval/cases.yaml`. Jeder Fall wurde vor dem Eintragen gegen Datenbank
bzw. Index geprüft, damit er am Agenten scheitern kann und nicht an fehlenden Daten. Bei den
Tagestouren steht die SQL-Abfrage mit ihrem Ergebnis am Fall. Bei den Mehrtagesfällen steht dort
der vorab berechnete Plan, bei den Wissensfällen die Fundstelle im Index.

| Gruppe | Fälle | Was geprüft wird (Erwartungsarten aus `smoke.py`) |
|---|---|---|
| erfuellbar | 12 | Mindestens ein Treffer, jede Bedingung jeder Karte erfüllt (`min_results`, `all_constraints_ok`). Drei Laufrunden zusätzlich mit `activity: run`, ohne erfundenes Tempo (`no_pace`) und ohne Dauer ohne Tempo. |
| unerfuellbar | 8 | Die Antwort beginnt mit „Keine Tour erfüllt alle Wünsche“ und hat einen `fallback_reason` (`unsatisfiable_named`). Wo es Ausweichtouren gibt, verletzt jede genau eine Bedingung (`fallback_single_violation`). Dabei sind eine Rückfrage (Feldberg → Gemeinde), ein Widerspruch (mindestens 15 und höchstens 10 km) und ein Fall, in dem jede Tour mehrere Bedingungen verletzt. |
| mehrtag | 9 | Je 3 Fälle auf Westweg (einmal Ostvariante), Mittelweg und Ostweg. Geprüft werden Tagesanzahl, Unterkunft ≤ 1 km oder genannter Zuweg bzw. genannte Lücke, und Tageslänge im Band oder Abweichung benannt. Drei Fälle haben ein Datum. Davon liegen zwei auf Regentagen, einmal mit Regenvariante (`plan_rain_variant`), einmal ohne Haltestelle, also „Regenvariante nicht möglich“ (`plan_no_rain_variant`). Einer liegt auf trockenen Tagen. Alle drei prüfen, dass jeder Tag eine Vorhersage hat (`plan_weather`). |
| aenderung | 5 | Folgerunde im selben Gespräch: „Tag N kürzer/länger“. Die nicht genannten Tage bleiben gleich (`days_unchanged`), der genannte Tag wird kürzer oder länger (`day_shorter`, `day_longer`). Ein Fall ändert denselben Plan zum zweiten Mal. |
| wissen | 10 | Eine erwartete Quelle unter den ersten fünf (`sources_include`) und die Kernbegriffe der Sollantwort im Text (`reply_contains`, z. B. „Raute“, „Gauchach“, „2014“). Bei w01 darf zusätzlich die falsche Farbe nicht im Text stehen (`reply_not_contains`). |
| eingabeschutz | 5 | Vier Injection-Varianten (Systemprompt, englisch, Rollenspiel, mit Nullbreite-Zeichen) bekommen die feste Antwort ohne Modellaufruf (`reply: injection`, `no_model_calls`). Eine themenfremde Frage („Rezept für Apfelkuchen“) bekommt die feste Antwort `other`. |
| gruppen_laeufe | 3 | Wanderverein mit Prüfdatum (`min_groups`), ehrlich „keine Gruppe“ bei Lauftreffs (`no_groups`), Läufe nur mit zitierten Feldern oder Kalender-Links (`events_quoted`). Der Läufe-Fall sucht live im Web. |

## Kennzahlen

Die Definitionen stehen im Modulkopf von `backend/src/hikeall/evaluation.py`. Ein Ziel, dessen
Nenner 0 ist, gilt als „nicht erreicht“: Was nicht gemessen wurde, gilt nicht als erreicht.

- **Nicht belegte Zahlen (Ziel ≤ 2 %).** Gezählt wird über jede Runde jedes Falls.
  - Zähler: `DoneEvent.unsupported`, also Zahlen, die die Grounding-Prüfung nicht belegen konnte.
    Sie stehen im Text bereits als „?“.
  - Nenner: Zahlen mit Einheit, die noch im Antworttext stehen (`grounding.numbers_in_text`),
    plus `unsupported`.
  - Gezählt werden nur Zahlen mit Einheit (km, Hm, h, °C, %, …), so wie die Grounding-Prüfung
    sie erkennt. Jahreszahlen und Uhrzeiten ohne Einheit zählen nicht.
- **Erfundene Touren (Ziel 0 %).**
  - Je Fall werden die verschiedenen gezeigten Tour-IDs gezählt (Karten und Pläne aller Runden)
    und über alle Fälle summiert (`tours_total`). Gezählt werden die IDs, die nicht in
    `trails` stehen.
  - Dazu kommen Tournamen im Text, die in den Ergebnissen der Runde nicht vorkommen
    (`unsupported_names`).
  - Das Ziel ist nur erreicht, wenn beide Zahlen 0 sind.
- **Unerfüllbarkeit offen benannt (Ziel 100 %).**
  - Nenner: Fälle der Gruppe `unerfuellbar` (8).
  - Zähler: Fälle, deren letzte Runde `unsatisfiable_named` erfüllt.
- **Recall@5 (Ziel ≥ 0,8).**
  - Nenner: Fälle der Gruppe `wissen` mit `sources_include` (10).
  - Zähler: Fälle, in denen jeder gesuchte String in ID oder URL einer der ersten fünf Quellen
    steht.
  - Ein Fall ohne Quellen-Ereignis zählt als Fehlschlag und bleibt im Nenner.
- **Abgleich mit OSM** (kein SMART-Ziel, Plausibilitätsprüfung).
  - Tourkarten: Jede gezeigte Tour wird dreifach verglichen: Länge auf der Karte,
    `trails.length_km` und Länge der gespeicherten OSM-Linie (geodätisch).
  - Plantage: Jeder Tag eines Mehrtagesplans wird einzeln verglichen. Die Gehstrecke auf dem Weg
    wird gegen den Linienabschnitt zwischen den km-Positionen des Tages gemessen. Ein Zuweg zur
    Unterkunft wird getrennt ausgewiesen und nicht verglichen.
  - Als Abweichung zählt mehr als 2 % zur Linie.

## Interpretation

Was die Zahlen zeigen:

- Auf diesen 52 Anfragen hat `openai/gpt-4o-mini` keine Tour, keinen Tournamen und keine Zahl
  mit Einheit erfunden.
- Jede unerfüllbare Anfrage wurde offen als unerfüllbar benannt.
- Für jede Wissensfrage war die erwartete Quelle unter den ersten fünf.
- Die km-Angaben von Karten und Plantagen passen zur OSM-Linie.

Was sie nicht zeigen:

- **Ein Modell, ein Lauf, kein Konfidenzintervall.** Das Modell antwortet nicht deterministisch.
  Am selben Tag gab es fünf Läufe mit Korrekturen dazwischen. Der Fall u08 bestand in Lauf 1,
  fiel in den Läufen 2 und 3 durch und bestand nach dem Fix wieder (siehe Befunde). Ein grüner
  Lauf heißt also nicht, dass jeder Fall immer grün ist. Bei 8 bzw. 10 Fällen je Ziel verschiebt schon ein einziger Fall die Quote um 10–12
  Prozentpunkte. Aussagen über andere Modelle oder über die Häufigkeit seltener Fehler sind damit
  nicht möglich.
- **Kleiner, selbst geschriebener Testsatz.** Die Fälle stammen vom Entwickler des Systems und
  sind gezielt so gewählt, dass die Daten sie tragen. Er misst, ob der Agent mit vorhandenen
  Daten richtig umgeht, nicht wie gut er Anfragen echter Nutzer abdeckt.
- **„0 % erfundene Touren“ ist teils durch die Bauweise gesichert.** Karten und Pläne kommen
  immer aus der Datenbank. Aussagekräftig ist vor allem der Teil mit Tournamen im Text.
- **Die Zahlenquote erfasst nur Zahlen mit Einheit.** Falsche Aussagen ohne Zahl misst sie nicht,
  etwa eine falsche Farbe einer Markierung. Für Wissensfragen prüft das nur `reply_contains`,
  und zwar mit Teilstrings: Eine Antwort, die zusätzlich etwas Falsches behauptet, kann trotzdem
  bestehen.
- **Recall@5 hängt vor allem an der Vorab-Suche im Index.** Die Frage geht im Code zuerst an
  den Index. Ein Treffer zeigt, dass die Suche die passende Stelle findet, nicht dass die Antwort
  sie richtig wiedergibt.
- **Wetter ist eingefroren, Läufe sind live.** Die Wetterfälle sind wiederholbar, der Läufe-Fall
  (Websuche) nicht.

## Befunde

- **Behoben: km-Positionen auf Fernwegen waren Gradanteile** (Commit `96e4246`).
  - Ursache: `along_km` von Unterkünften und Haltestellen, `start_km` und der Endpunkt eines
    Plantags waren Anteile der Linie in Grad mal `trails.length_km`. Ein Längengrad ist hier nur
    etwa 0,67 eines Breitengrads.
  - Folge: Der erste Lauf zeigte 22 von 82 Plantagen mit mehr als 2 % Abweichung zur OSM-Linie,
    zum Beispiel einen Westweg-Tag mit 15,1 statt 16,1 km.
  - Fix: Jetzt sind es Anteile der Linie in ETRS89/UTM 32N (`geo.METRIC_SRID`). Die
    Abweichung liegt unter 0,5 %, Tests mit einer L-förmigen Linie sichern das ab.
    `trail_lodgings` und `trail_pois` wurden neu verknüpft.
  - Eine bestehende Datenbank bekommt die korrigierten `along_km` mit `cd backend && uv run
    hikeall import-lodgings` und `uv run hikeall import-places` (beide verknüpfen am Ende neu)
    oder mit einem vollständigen `make import`. Ohne das bleiben die alten Gradanteile stehen,
    und Pläne und OSM-Abgleich passen nicht zueinander.
- **Fall korrigiert: w01.**
  - Erwartet war „rote Raute“ als ein String. Die richtige Antwort „mit einer roten Raute auf
    weißem Grund“ fiel an der Deklination durch.
  - Jetzt wird nach „rote“ und „Raute“ einzeln gesucht. Damit dabei die naheliegende falsche
    Antwort „schwarz-rote Raute“ (das Zeichen des Ostwegs) nicht durchrutscht, darf sie nicht in
    der Antwort stehen (neue Erwartungsart `reply_not_contains`).
  - Ein erster Versuch verbot bloß „schwarz“. Daran fiel in Lauf 4 eine richtige Antwort durch,
    weil sie den „Schwarzwaldverein“ nannte. Verboten sind jetzt die Schreibweisen
    „schwarz-rot“, „schwarzrot“, „schwarz/rot“ und „schwarz und rot“. Die Begründung steht am
    Fall.
- **Behoben: Das Modell setzte ungefragt „kein Rundweg“** (Commit `e052c20`, Fall u08).
  - Bei „Wanderung im Umkreis von 3 km um Feldberg-Ort, über 20 km“ setzte das Modell oft
    `roundtrip: false`, obwohl die Anfrage nichts dazu sagt. Bei einer Probe des
    Verstehens-Schritts geschah das in 2 von 3 Versuchen. Lauf 1 bestand den Fall, die Läufe 2
    und 3 nicht.
  - Der Code übernahm den Wert ungeprüft. Zahlen dagegen prüft er gegen den Nachrichtentext
    (R27). Folge: Jede Tour verletzte zwei Bedingungen, die Antwort benannte die
    Unerfüllbarkeit, zeigte aber keine Ausweichtour. Die Tour „Bernauer Hochtal Steig“ (15,3 km,
    2,9 km entfernt) verletzt nur die Länge.
  - Fix: Das Rundweg-Feld zählt jetzt nur, wenn die Nachricht es nennt (Rundweg, Runde,
    Rundtour, Rundwanderung, Rundkurs, Schleife, Strecke…, „von … nach …“). Sonst wird es
    verworfen und wie R27 als verworfener Modellwert gezählt. „rund 20 km“ zählt nicht als
    Rundweg.
  - Grenze: Eine Streckentour ohne eines dieser Wörter (etwa „bis zum Titisee“) verliert die
    Bedingung. Sie fehlt dann sichtbar im Verständnis-Echo.
- **Beobachtung ohne roten Fall: Wetter im Antworttext.** Im Fall m03 nennt das Modell das
  Wetter der Regentage im Text nicht. Vorhersage und „Regenvariante nicht möglich“ stehen im
  Plan-Ereignis und davor im Code-Text, die App zeigt sie je Tag an.

## Kosten

Ein vollständiger Lauf kostet mit `openai/gpt-4o-mini` etwa 0,03 USD (Lauf vom 2026-10-31:
0,0264 USD). Davon entfallen 0,008 USD auf den Läufe-Fall mit Websuche, der Rest verteilt sich
auf rund 0,0002–0,0005 USD je Fall. Die Injection-Fälle kosten nichts. Für diese Auswertung gab es
fünf volle Läufe (0,0282 + 0,0278 + 0,0261 + 0,0265 + 0,0264 USD) und einzelne Nachläufe zur
Fehlersuche. Zusammen waren das rund 0,14 USD.
