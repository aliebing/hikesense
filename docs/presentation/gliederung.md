# Präsentation „Hike all about“: Gliederung und Sprechnotizen

10 Minuten, sechs Punkte. Zahlen stammen aus dem [README](../../README.md), dem
[Evaluationsbericht vom 2026-10-31](../evaluation/bericht-2026-10-31-openai-gpt-4o-mini.md),
dem [Modellvergleich](../evaluation/vergleich.md) und der
[Spec](../superpowers/specs/2026-10-28-hike-all-about-design.md). Bilder liegen in
`docs/showcase/`.

| Nr. | Punkt | Minuten |
|---|---|---|
| 1 | Problem | 1,5 |
| 2 | Lösung und Demo | 2,0 |
| 3 | Architektur | 1,5 |
| 4 | Daten und Herkunft | 1,0 |
| 5 | Evaluation | 2,5 |
| 6 | Ethik, Grenzen, nächste Schritte | 1,5 |
| | **Summe** | **10,0** |

## 1. Problem (1,5 min)

**Folientitel:** Drei Tage Schwarzwald, mehrere Tage Vorbereitung

**Auf der Folie:**

- Drei Zimmer hintereinander, je etwa 15 km, Plan B für Regen
- Schwierig war nicht der Weg, sondern dass Strecke, Übernachtung und Wetter zusammenpassen
- HikeAI-Kritik: Wünsche still fallen gelassen, nur eine Liste, Daten ohne Herkunft

**Screenshot:** `docs/showcase/01-startseite.jpg`

**Sprechnotizen:**

Der Anlass für dieses Projekt war eine echte Planung. Ali wollte drei Tage im Schwarzwald wandern. Er hat bekannte Routen gesucht, Westweg, Komoot, Schwarzwaldverein, und Empfehlungen verglichen. Dann hat er drei Zimmer hintereinander gebucht, sodass jeden Tag etwa 15 Kilometer bis zur Unterkunft am späten Nachmittag lagen, und er hatte einen Plan B für Regen. Das hat gut funktioniert, aber es hat mehrere Tage Vorbereitung gekostet. Das Schwierige war nicht, einen Weg zu finden. Das Schwierige war, dass Strecke, Übernachtung und Wetter zusammenpassen.

Mein Vorgänger HikeAI hat genau das nicht gelöst, und im Review wurden drei Dinge kritisiert. Erstens hat er Wünsche stillschweigend fallen gelassen. Auf die Anfrage Rundweg, unter 200 Höhenmeter, über 15 Kilometer, Feldberg kam erst nichts und dann ein Vorschlag ohne Rundweg, ohne jeden Hinweis. Zweitens konnte man mit den Ergebnissen nichts anfangen: keine Route, keine Planung, nur eine Liste. Drittens war die Herkunft der Daten nicht nachvollziehbar, sie kamen fast nur aus OpenStreetMap. Deshalb habe ich die App neu gebaut. Das Planen steht im Vordergrund, der Chat ist die Bedienung, und die Regeln für Ehrlichkeit stehen im Code und nicht im Prompt.

## 2. Lösung und Demo (2,0 min)

**Folientitel:** Planen im Gespräch, ehrlich bei Widerspruch

**Auf der Folie:**

- Unerfüllbarer Wunsch wird benannt, Ausweichtouren verletzen genau eine Bedingung
- Mehrtagesplan mit Unterkunft (höchstens 1 km vom Weg), Ankunftszeit, Wetter, Regenvariante
- Änderung im Chat („Tag 3 kürzer“) und „Unterwegs“ auf dem Handy

**Screenshots (Folie oder Standbild, falls die Demo live läuft):**
`docs/showcase/04-unerfuellbar-ausweichtouren.png`, `docs/showcase/05-mehrtagesplan-wetter.png`,
`docs/showcase/10-unterwegs-handy.jpg`

**Demo-Ablauf (Video oder live):**

1. „Rundweg, unter 200 Hm, über 15 km, Feldberg“: Der Code sagt, dass keine Tour alles erfüllt, und zeigt Ausweichtouren mit der einen verletzten Bedingung.
2. „3 Tage Ostweg ab Freudenstadt“: Plan mit Tagesstrecken, Unterkünften, Ankunftszeiten und Wetter.
3. „Tag 3 kürzer“: Der Plan ändert sich, die anderen Tage bleiben.
4. „Unterwegs“ auf dem Handy: Restkilometer und Ankunft auf Tag 1.

**Sprechnotizen:**

Ich zeige jetzt, wie sich das anfühlt, und beginne mit dem Satz, an dem HikeAI gescheitert ist. Ich schreibe: Rundweg, unter 200 Höhenmeter, über 15 Kilometer, Feldberg. Die App tut nicht so, als gäbe es etwas. Sie sagt, dass keine Tour alle Wünsche erfüllt, und nennt den Grund. Dann zeigt sie Touren, die genau eine Bedingung verletzen, mit der Abweichung, zum Beispiel 632 Höhenmeter statt höchstens 200.

Jetzt der eigentliche Zweck: Ich schreibe, drei Tage Ostweg ab Freudenstadt. Das ist der Weg, den ich in der Demo benutze. Die App teilt den Weg in drei Tage, wählt je Tag eine Unterkunft höchstens einen Kilometer vom Weg, rechnet die Ankunftszeit nach DIN 33466 und holt das Wetter von Open-Meteo. An Regentagen bietet sie eine Regenvariante mit der Bahn an. Dann schreibe ich, Tag 3 kürzer. Der Plan ändert sich im Gespräch, und die anderen Tage bleiben, wie sie waren.

Zum Schluss nehme ich das Handy. Die Seite Unterwegs zeigt meine Position auf dem Tagesabschnitt, die Restkilometer und die geschätzte Ankunft. Das rechnet der Browser, es wird nichts aufgezeichnet. Die Bilder auf den Folien stammen vom Westweg ab Hausach, weil ich diesen Plan fotografiert habe. Gezeigt wird dieselbe Funktion. Wichtig ist mir dabei: Nichts davon erfindet das Modell. Jede Strecke, jede Unterkunft und jede Zeit kommt aus der Datenbank und wird vom Code gerechnet.

## 3. Architektur (1,5 min)

**Folientitel:** Das Modell formuliert, der Code garantiert

**Auf der Folie:**

- LangGraph-Agent: Eingabeschutz, Verstehen, Suchen oder Planen, Antworten, Grounding-Prüfung
- Das Modell macht aus der Nachricht eine Anfrage und formuliert die Antwort
- Der Code sucht Touren, prüft jede Bedingung, plant Tage und rechnet Gehzeiten
- Jede Zahl im Text wird gegen die Werkzeugergebnisse geprüft

**Screenshot:** keiner; stattdessen das Diagramm aus dem Abschnitt „Wie es funktioniert“ im README (Mermaid, als Grafik rendern)

**Sprechnotizen:**

Die Architektur folgt einer Regel: Das Modell darf formulieren, aber der Code garantiert. Die Web-App ist in Next.js gebaut, Anmeldung, Pläne und Fotos laufen über Supabase. Für den Chat spricht sie mit einer Python-API, und die führt einen LangGraph-Graphen aus. Erst kommt ein Eingabeschutz, der Prompt-Injection und themenfremde Fragen mit einer festen Antwort beantwortet, ohne das Modell aufzurufen. Dann macht das Modell aus der Nachricht eine strukturierte Anfrage. Zahlen und Bedingungen daraus übernimmt der Code nur, wenn sie wirklich in der Nachricht stehen.

Danach arbeitet nur noch der Code. Er sucht die Touren in der Datenbank, prüft jede Bedingung, wählt Ausweichtouren, plant die Tage und rechnet Gehzeiten. Erst dann formuliert das Modell die Antwort aus diesen Ergebnissen. Und zum Schluss kommt die Grounding-Prüfung. Sie sucht jede Zahl mit Einheit im Text in den Werkzeugergebnissen. Was nicht belegt ist, wird durch ein Fragezeichen ersetzt. Tournamen, die nicht vorkommen, bekommen einen Hinweis. Die ehrlichen Sätze, etwa Keine Tour erfüllt alle Wünsche, schreibt der Code selbst und stellt sie vor den Text des Modells. Für Wissensfragen gibt es zusätzlich einen Index mit Quellen, und ohne Quelle gibt es keine Antwort.

## 4. Daten und Herkunft (1,0 min)

**Folientitel:** Jede Zeile hat eine Quelle mit Lizenz

**Auf der Folie:**

- 4 Fernwege mit 46 Etappen, 122 Tagestouren, 1814 Unterkünfte
- Wege und Orte aus OSM (ODbL), Höhen aus Copernicus DEM, Karte von basemap.de, Wetter von Open-Meteo
- 849 Bilder von Wikimedia Commons mit Urheber und Lizenz, 551 Abschnitte im Wissensindex
- Fester Datenstand vom 2026-10-28 bis 2026-10-31

**Screenshot:** `docs/showcase/07-routenseite-fotos.png` (Bilder mit Lizenz); alternativ `docs/showcase/09-wissensfrage-quellen.jpg`

**Sprechnotizen:**

Die Daten liegen in einer lokalen Datenbank mit Postgres und PostGIS, und jede Zeile verweist auf eine Quelle mit Lizenz. Das war die dritte Kritik am Vorgänger. Die Wege kommen aus OpenStreetMap unter ODbL. Es sind vier Linien mit zusammen 46 Etappen: Westweg in zwei Varianten, Mittelweg und Ostweg. Dazu kommen 122 Tagestouren. Ich habe 1712 Wanderrelationen gescannt, automatisch gefiltert und danach weitere 255 abgelehnt. Diese Ablehnungen hat Claude vorgeschlagen, und ich muss sie noch bestätigen. Dazu kommen 1814 Unterkünfte, Einkehr und Aussichtspunkte.

Höhenprofile berechne ich mit dem Copernicus-Geländemodell, die Karte kommt von basemap.de, das Wetter von Open-Meteo. Zu den Touren gibt es 849 Bilder von Wikimedia Commons, jedes mit Urheber und Lizenz. Der Wissensindex enthält 551 Abschnitte aus Wikipedia, Wikivoyage und eigenen Texten. Wichtig ist, dass die App OpenStreetMap zur Laufzeit nicht abfragt. Der Stand ist fest, er stammt vom 28. bis 31. Oktober, und das sage ich auch offen: Daten können veraltet sein.

## 5. Evaluation (2,5 min)

**Folientitel:** Vier SMART-Ziele erreicht, ein ehrlicher Fehlschlag

**Auf der Folie:**

| Ziel | Ist-Wert |
|---|---|
| 0 % erfundene Touren | 0 von 74 Tour-IDs |
| ≤ 2 % nicht belegte Zahlen | 0 von 518 (0,0 %) |
| 100 % offen benannte Unerfüllbarkeit | 8 von 8 |
| Recall@5 ≥ 0,8 | 1,00 (10 von 10) |

- 52 Fälle, echtes Modell (`openai/gpt-4o-mini`), Prüfung durch Code, 52 von 52 bestanden, 0,0282 USD je Lauf
- Abgleich mit OSM: 0 von 82 Touren und Plan-Tagen über 2 % Abweichung
- Fehlschlag: Der Test blieb grün, obwohl die App „Keine Tour erfüllt alle Wünsche“ fälschlich sagte

**Screenshot:** `docs/showcase/02-tagestouren.jpg` (erfüllbare Anfrage, Karten mit ✓, ohne den falschen Satz nach dem Fix)

**Sprechnotizen:**

Ich habe vier SMART-Ziele festgelegt und gegen einen festen Testsatz von 52 Anfragen gemessen. Der Test läuft gegen den echten Agenten, mit echtem Modell, echter Datenbank und echtem Index, und geprüft wird mit Code, nicht von Hand. Ergebnis: Keine erfundene Tour, null von 74 Tour-IDs nicht in der Datenbank. Von 518 Zahlen im Antworttext war keine unbelegt, das sind 0,0 Prozent bei einem Ziel von höchstens 2 Prozent. Die Unerfüllbarkeit wurde in 8 von 8 Fällen offen benannt. Recall at 5 liegt bei 1,00, in 10 von 10 Wissensfragen stand die richtige Quelle unter den ersten fünf. Alle 52 Fälle bestehen, ein Lauf kostet 2,8 Cent. Im Abgleich mit OpenStreetMap wich keine von 82 Touren um mehr als 2 Prozent ab.

Aber das ist nur die halbe Wahrheit, und jetzt kommt der ehrliche Fehlschlag. Beim Aufnehmen der Screenshots fiel mir auf, dass die App bei Rundweg 10 bis 14 Kilometer um Hinterzarten sagte, keine Tour erfülle alle Wünsche, obwohl alle vier Karten alles erfüllten. Das passierte in 3 von 3 Versuchen. Der Eval-Lauf davor war trotzdem komplett grün, denn keine Erwartung verbot diesen Satz, und die Zahlenquote erfasst nur Zahlen mit Einheit. Die Ursache war mein eigener Prompt, der den Satz zitierte. Das Modell hat ihn in 12 von 12 erfüllbaren Fällen übernommen. Ich habe den Satz aus dem Prompt genommen, der Code entfernt ihn jetzt, wenn er nicht ausgewichen ist, und der Testsatz prüft ihn. Seitdem: 0 von 21. Was weiterhin nicht gemessen wird: andere falsche Sätze ohne Zahl. Dazu kommen ein kleiner, selbst geschriebener Testsatz und nur ein Lauf je Konfiguration. Ein zweites Modell, Gemini Flash Lite, besteht 51 von 52, und die Temperatur ändert bei gpt-4o-mini nichts.

## 6. Ethik, Grenzen, nächste Schritte (1,5 min)

**Folientitel:** Was die App nicht weiß, sagt sie

**Auf der Folie:**

- Standort bleibt im Browser, eigene Fotos privat, keine Kontodaten ans Modell
- Eingabeschutz gegen Injection; Kosten gedeckelt (0,05 USD je Nachricht)
- Grenzen: Zimmerverfügbarkeit unbekannt, OSM-Daten veraltet möglich, Modell kann trotz Grounding falsch formulieren
- Nächste Schritte: 24 Gruppen von Hand prüfen, Streckenlängen der Etappen angleichen, Bus und berechnete Regenvarianten

**Screenshot:** `docs/showcase/11-unterwegs-karte-handy.jpg` (Position nur auf dem Gerät)

**Sprechnotizen:**

Zur Ethik gehört zuerst der Datenschutz. Der Standort bei Unterwegs bleibt im Browser. Er wird weder gesendet noch gespeichert noch protokolliert, und es gibt keine Hintergrundortung. Eigene Fotos sind privat, und beim Hochladen fallen die GPS-Daten weg. E-Mail und Nutzer-ID gehen nicht an das Modell. Gegen Prompt-Injection gibt es den Eingabeschutz, und die Kosten sind gedeckelt, auf 0,05 Dollar je Nachricht.

Dann die Grenzen. Die App weiß nicht, ob in einer Unterkunft ein Zimmer frei ist, sie verlinkt nur die Website. OpenStreetMap-Daten können veraltet oder unvollständig sein, und gut kartierte Gebiete sind bevorzugt. Das Modell kann trotz Grounding falsch formulieren, denn geprüft sind Zahlen, Namen und ein Satz, nicht alles dazwischen. Auch bei den Etappen gibt es eine Lücke: Beim Ostweg weichen 7 von 12 Etappen um mehr als 5 Prozent von den offiziellen Kilometern ab. Das steht so im README.

Als nächste Schritte sind drei Dinge offen. Erstens prüfe ich die 24 Gruppen von Hand, bisher sind sie nur automatisch geprüft. Zweitens gleiche ich die Etappenenden an die offiziellen Kilometer an. Drittens fehlen Bushaltestellen und eine berechnete Regenvariante. Und an Wanderer gerichtet: Wetter und Sperrungen bitte immer vor Ort prüfen. Die App ersetzt keine Ortskenntnis.

## Folien

Die Folien werden aus dieser Gliederung erzeugt (Titel, Stichpunkte und Screenshot je Punkt). Sie liegen als Folien-Artifact vor (https://claude.ai/artifact/J9h4AjHsvxaXvGF7Nzc2TG, privat bis zum Teilen; Export als PDF oder PPTX). Das Drehbuch fürs Demo-Video steht in [demo-video.md](demo-video.md). Die Sprechnotizen kommen in die Notizenfelder. Zahlen bleiben auf die Quellen oben beschränkt.

## Zeitprüfung der Sprechnotizen

Richtwert 130 Wörter je Minute, Toleranz ±20 %. Gezählt sind nur die Sprechnotizen je Punkt.

| Punkt | Minuten | Soll (130 Wörter/min) | Ist (Wörter) | Abweichung |
|---|---|---|---|---|
| 1 | 1,5 | 195 | 186 | -5 % |
| 2 | 2 | 260 | 222 | -15 % |
| 3 | 1,5 | 195 | 187 | -4 % |
| 4 | 1 | 130 | 155 | +19 % |
| 5 | 2,5 | 325 | 280 | -14 % |
| 6 | 1,5 | 195 | 196 | +1 % |
| Summe | 10,0 | 1300 | 1226 | -6 % |

Punkt 2 enthält zusätzlich die Demo selbst; läuft sie live, bleibt dafür weniger Sprechzeit, das Video sollte dann kurz sein oder die Notizen werden gekürzt. Die Wortzahl ist ein Richtwert, der Probelauf mit Uhr (Sprechtempo) steht noch aus.
