# HikeSense – Details (Deutsch)

Ein Wanderplaner für Schwarzwald, Bodensee (mit Schweizer und österreichischem Ufer) und Pfälzerwald, den man über einen KI-Chat bedient, auf Deutsch oder Englisch. Er plant Tagestouren und Mehrtagestouren auf acht Fernwegen mit Unterkünften, Gehzeiten und Wetter. Jede Strecke kommt aus der Datenbank, nicht vom Sprachmodell. Jede Zahl im Antworttext prüft der Code gegen die Ergebnisse der Werkzeuge.

## Showcase

**Video: folgt** <!-- Link zum Demo-Video hier eintragen -->

| Unerfüllbarer Wunsch: ehrlich benannt, Ausweichtouren mit genau einer verletzten Bedingung | Mehrtagesplan mit Unterkünften, Ankunftszeiten und Wetter | „Unterwegs“ auf dem Handy |
|---|---|---|
| ![Ausweichtouren für „Rundweg, unter 200 Hm, über 15 km, Feldberg“](showcase/04-unerfuellbar-ausweichtouren.jpg) | ![Plan „3 Tage Westweg ab Hausach“ mit Unterkünften](showcase/05-mehrtagesplan.jpg) | ![Restkilometer und Ankunft auf Tag 1](showcase/10-unterwegs-handy.jpg) |

Alle Screenshots stammen aus der lokal laufenden App vom 2026-10-31 mit dem echten Modell (`openai/gpt-4o-mini`). Die Position für „Unterwegs“ ist simuliert: ein Punkt auf Tag 1 des Plans, die Uhr des Browsers steht auf 10:00. Die Bilder 02, 10, 11 und 12 sind nach den Fixes vom selben Tag neu aufgenommen.

<details>
<summary>Alle Screenshots</summary>

Die Bilder zeigen noch die Optik vor dem Umbau vom 2026-11-01 (Fotohintergrund, eigene Vorschlagsseite). Seitdem ist die App dunkelgrün, die Vorschläge stehen als Kacheln direkt neben dem Chat, und Tour- und Planseite zeigen die Karte eingebettet. Neue Screenshots folgen mit dem neuen Video.

1. [Startseite](showcase/01-startseite.jpg). Die Screenshots 1–8 sind vom 2026-11-03 (HikeSense, englische Oberfläche), 9–12 noch mit dem alten Namen.
2. [Tagestouren zu „A round walk near Titisee, about 10 km“ und „Under 300 m ascent, please“](showcase/02-tagestouren.jpg): Karten mit ✓ je Bedingung, dazu eine gelbe Karte „Near miss“ mit der einen knappen Abweichung (11,6 statt höchstens 11,5 km).
3. [Rückfrage „Feldberg“ und ehrlich benannte Unerfüllbarkeit im Chat](showcase/03-unerfuellbar-chat.jpg)
4. [Ausweichtouren mit der einen verletzten Bedingung](showcase/04-unerfuellbar-ausweichtouren.jpg)
5. [Mehrtagesplan mit Unterkünften und Ankunftszeiten](showcase/05-mehrtagesplan.jpg)
6. [Karte mit Tagesabschnitten](showcase/06-tagesabschnitte-karte.jpg)
7. [Routenseite mit Fotos, Lizenzen und Gruppen in der Nähe](showcase/07-routenseite-fotos.jpg)
8. [Karte einer Tagestour mit Unterkünften (basemap.de)](showcase/08-routenkarte.jpg)
9. [Wissensfrage mit Quellen und Lizenz](showcase/09-wissensfrage-quellen.jpg)
10. [„Unterwegs“ auf dem Handy](showcase/10-unterwegs-handy.jpg)
11. [„Unterwegs“ mit Position auf der Karte](showcase/11-unterwegs-karte-handy.jpg)
12. [Startseite auf dem Handy](showcase/12-startseite-handy.jpg)

</details>

## Problem

Eine echte Planung war der Anlass: drei Tage Schwarzwald. Dafür habe ich bekannte Routen gesucht (Westweg, Komoot, Schwarzwaldverein) und Empfehlungen verglichen. Dann habe ich drei Zimmer hintereinander gebucht, so dass jeden Tag etwa 15 km bis zur Unterkunft am späten Nachmittag lagen, mit einem Plan B für Regen. Das hat gut funktioniert, kostete aber mehrere Tage Vorbereitung. Schwierig war nicht, einen Weg zu finden. Schwierig war, dass **Strecke, Übernachtung und Wetter zusammenpassen**.

Der Vorgänger HikeAI (Sprint 2) wurde im Review vor allem für drei Dinge kritisiert:

- **Wünsche stillschweigend fallen gelassen.** „Rundweg, unter 200 Hm, über 15 km, Feldberg“ ergab erst nichts. Danach kam ein Vorschlag *ohne* Rundweg, ohne Hinweis darauf.
- **Mit den Ergebnissen ließ sich nichts anfangen.** Es gab keine Route und keine Planung, nur eine Liste.
- **Die Herkunft der Daten war nicht nachvollziehbar.** Sie kamen fast nur aus OSM.

HikeSense ist deshalb neu gebaut. Im Vordergrund steht das Planen, der Chat ist die Hauptbedienung, und die Regeln für Ehrlichkeit stehen im Code statt im Prompt.

## Was die App kann

1. **Mehrtagestour planen:** teilt Westweg (West- und Ostvariante), Mittelweg, Ostweg, SeeGang, Jubiläumsweg Bodenseekreis, Pfälzer Weinsteig oder Pfälzer Waldpfad ab einem Etappenort in Tage mit Zielstrecke. Tagesziel ist eine Unterkunft höchstens 1 km vom Weg. Dazu kommen die Ankunftszeit nach DIN 33466, das Wetter und an Regentagen eine Regenvariante mit der Bahn.
2. **Tagestouren:** schlägt höchstens 5 Touren im Umkreis eines Startorts vor, jede mit ✓ oder ✗ je Bedingung.
3. **Ehrlicher Umgang mit Wünschen:** Erfüllt keine Tour alle Bedingungen, sagt der Code das mit Begründung. Er zeigt dann Touren, die genau eine Bedingung verletzen, und nennt die Abweichung (z. B. „632 Hm statt höchstens 200“).
4. **Chat im Vordergrund:** Der Plan entsteht im Gespräch und lässt sich dort ändern, etwa mit „Tag 3 kürzer“ oder „Und eine Regenvariante für Tag 1?“.
5. **Wissensfragen mit Quelle:** beantwortet Fragen wie „Wie ist der Westweg markiert?“ aus einem Index mit Wikipedia, Wikivoyage und eigenen Texten, immer mit Quelle und Lizenz. Ohne Quelle gibt es keine Antwort.
6. **Unterwegs (PWA):** zeigt auf dem Handy die eigene Position auf dem Tagesabschnitt, die Restkilometer und die geschätzte Ankunft. Alles wird im Browser berechnet, nichts wird aufgezeichnet.
7. **Bilder:** Touren und Etappen haben Bilder von Wikimedia Commons mit Urheber und Lizenz. Man kann sie durchblättern, als Hintergrund wählen und eigene, private Fotos hinzufügen.
8. **Gäste und Konten:** Chatten geht ohne Konto (Gast). Merken, „Meine Pläne“ und Fotos hochladen brauchen ein Konto (Supabase Auth mit E-Mail-Bestätigung). Gemerkte Pläne erscheinen unter „Meine Pläne“, auch auf dem Handy.

Dazu kommen eine kuratierte Liste von Wandervereinen und eine Suche nach Laufveranstaltungen mit Quellenpflicht (siehe [Gruppen und Läufe](#gruppen-und-läufe)).

## Wie es funktioniert

Die Web-App (Next.js, als PWA installierbar) spricht mit Supabase für Anmeldung, gemerkte Pläne und Fotos. Für den Chat spricht sie mit der Python-API (FastAPI). Die API prüft das Supabase-Token und das Rate-Limit und führt dann einen LangGraph-Graphen aus. Die Knoten unten heißen so wie in `backend/src/hikesense/agent/graph.py` (`build_graph`).

```mermaid
flowchart TD
    web["Web-App (Next.js, PWA)"] -->|"POST /chat mit Supabase-Token"| api["API (FastAPI): Token prüfen, Rate-Limit"]
    web <-->|"Anmeldung, Pläne, Fotos (RLS)"| sb[("Supabase: Postgres + PostGIS, Auth, Storage")]
    api --> guard

    subgraph lg["LangGraph"]
        guard["guard: Eingabeschutz (Injection, themenfremd)"]
        understand["understand: Modell macht aus der Nachricht eine HikeRequest; Code prüft Zahlen und Bedingungen gegen den Text"]
        clarify["clarify: Rückfrage statt raten"]
        reply["reply: feste Antwort"]
        search["search: search_day_hikes + Bedingungsprüfung + Ausweichtouren (Code)"]
        multiday["multiday: plan_multiday, Unterkunft ≤ 1 km, DIN 33466, Wetter, Regenvariante (Code)"]
        react["react: Wissensfrage, search_knowledge vorab, dann Werkzeug-Runden"]
        groups["groups: kuratierte Gruppenliste"]
        events["events: Läufe mit wörtlichen Zitaten"]
        answer["answer: Modell formuliert die Antwort aus den Werkzeugergebnissen"]
        ground["ground: Grounding-Prüfung (Zahlen und Tournamen gegen die Werkzeugergebnisse)"]
        log["log: Protokoll ohne Nachrichtentext und ohne Nutzer-ID"]

        guard -->|"Injection / themenfremd"| reply
        guard --> understand
        understand --> clarify
        understand --> reply
        understand --> search
        understand --> multiday
        understand --> react
        understand --> groups
        understand --> events
        search --> answer
        multiday --> answer
        react --> answer
        groups --> answer
        events --> answer
        answer --> ground
        ground --> log
        clarify --> log
        reply --> log
    end

    search -.-> sb
    multiday -.-> sb
    groups -.-> sb
    react -.-> chroma[("ChromaDB + BM25 (Wissensindex)")]
    multiday -.-> meteo["Open-Meteo"]
    events -.-> websearch["OpenRouter-Websuche + Seiten der Veranstalter"]
    understand -.-> llm["Sprachmodell über OpenRouter (Standard openai/gpt-4o-mini)"]
    react -.-> llm
    answer -.-> llm
```

Die Arbeit ist so aufgeteilt:

- **Das Modell** macht aus der Nachricht eine strukturierte Anfrage und formuliert die Antwort. In `react` wählt es außerdem Werkzeuge aus.
- **Der Code** übernimmt Zahlen und Bedingungen aus dem Modell nur, wenn sie in der Nachricht stehen. Er sucht die Touren, prüft jede Bedingung, wählt Ausweichtouren, plant die Tage und rechnet Gehzeiten.
- **Die Grounding-Prüfung** sucht jede Zahl mit Einheit im Antworttext in den Werkzeugergebnissen der Runde. Nicht belegte Zahlen ersetzt sie durch „?“. Tournamen, die in den Ergebnissen nicht vorkommen, bekommen einen Hinweis.
- **Die ehrlichen Sätze schreibt der Code selbst.** Das sind „Keine Tour erfüllt alle Wünsche, weil …“, Lücken bei Unterkünften und „Zeiten ohne Pausen“. Sie stehen wörtlich vor dem Text des Modells.

## Sprache

Die Oberfläche gibt es auf **Englisch (Standard)** und **Deutsch**. Zwei Fahnen oben rechts (🇬🇧 / 🇩🇪) schalten um, ohne die Seite neu zu laden: Die Serverteile der Seite werden neu gerendert (Daten werden noch einmal geholt), die Karte behält ihren Ausschnitt. Die Wahl steht im Cookie `hikesense.lang` und bleibt erhalten; ohne Wahl gilt Englisch. Server und Browser lesen dasselbe Cookie, damit die erste Anzeige schon in der richtigen Sprache kommt. Datum und Zahlen folgen der Sprache (`11.4 km` / `11,4 km`). Die Texte stehen in `web/src/i18n/en.ts` und `de.ts`; ein Test stellt sicher, dass beide Kataloge dieselben Schlüssel haben und kein Rahmentext fest im Code steht (auch keine deutschen Umlaute in Zeichenketten außerhalb von `i18n/`).

**Teil A (fertig):** alles, was die Web-App selbst schreibt: Menüs, Beschriftungen, Tourseite, Plan, Meine Pläne, Admin, Fehler- und Leerzustände.

**Teil B (fertig):** Das Backend schreibt seine Texte in der Sprache der Anfrage. Die Web-App schickt die gewählte Sprache als `lang` (`en`/`de`) mit jeder Chat-Nachricht mit. Das gilt für die Antwort im Chat, Rückfragen, das „Verstanden: …“-Echo, die Abweichungstexte bei „Knapp daneben“, die ✓/✗-Zeilen der Karten, Mehrtages-Notizen und Lücken, Wettertext, Gruppen- und Event-Texte, die festen Sätze (Eingabeschutz, „keine Tour erfüllt alle Wünsche, weil …“) und Chat-Fehlermeldungen. Das Modell bekommt dafür einen englischen oder deutschen Systemprompt; die Zahlenprüfung (Grounding) kennt auch englische Schreibweisen („11.6 km“, „1,200 m“) und Zahlwörter. Ein gespeicherter Plan behält die Sprache, in der er erstellt wurde (ebenso gemerkte Suchen). **API-Clients ohne `lang` bekommen weiter Deutsch** (Standard im Backend), die Web-App dagegen standardmäßig Englisch. Englische Texte sind britisches Englisch („round walk“, „ascent“, „stage“, „near miss“); Eigennamen und deutsche Quellentitel bleiben unübersetzt. Der Smoke-Test (`data/smoke/prompts.yaml`) enthält drei englische Fälle mit `lang: en`.

## Daten und Lizenzen

Alles liegt in einer lokalen Supabase-Datenbank. Die Import-Skripte (`hikesense import-*`, siehe `Makefile`) erzeugen einen festen Stand, die App fragt OSM zur Laufzeit nicht ab. Wege, Etappen, Unterkünfte, Orte und Punkte verweisen je Zeile auf eine Quelle mit Lizenz (Tabelle `sources`), Bilder tragen Urheber und Lizenz selbst. Die Karte zeigt die Attribution für OSM und BKG, jedes Bild seinen Urheber und seine Lizenz. Die Mengen unten wurden am 2026-11-03 aus der Datenbank abgefragt, die Abfrage steht als Kommentar daneben.

| Datenart | Quelle und Lizenz | Menge |
|---|---|---|
| Fernwege und Etappen | Wegverlauf: OSM-Relationen (ODbL). Etappeneinteilung (Start, Ziel, km) als Fakten von Schwarzwald Tourismus (Westweg), vom Schwarzwaldverein (Mittelweg, Ostweg), von Pfalz.Touristik (Weinsteig, Waldpfad), vom Landratsamt Bodenseekreis (Jubiläumsweg) und von seen.de/wildganz.com (SeeGang, Etappen-km nicht offiziell bestätigt), ohne übernommene Texte | 8 Linien: Westweg West 286,1 km, Westweg Ost 288,6 km, Mittelweg 224,8 km, Ostweg 244,5 km, SeeGang 52,9 km, Jubiläumsweg Bodenseekreis 114,9 km, Pfälzer Weinsteig 181,8 km, Pfälzer Waldpfad 126,7 km; zusammen 75 Etappen <!-- select id, round(length_km::numeric,1) from trails where kind='long_distance'; select count(*) from stages; --> |
| Tagestouren | OSM-Wanderrelationen (ODbL) aller drei Regionen. 4014 gescannt, 3048 nach festen Regeln verworfen (Name, 5–30 km, Lücken, Fernweg, Region), danach 389 weitere abgelehnt, davon 84 mit „Regionsausgleich“ (Dichteregel im Schwarzwald, keine Qualitätsregel). Diese Ablehnungen sind von Claude vorgeschlagen, noch nicht von Ali bestätigt (siehe [Offene Prüfungen](#offene-prüfungen-vor-abgabe)). Entscheidung und Grund je Relation in `data/curated/day_hikes.csv` | 577 Touren: Schwarzwald 122, Bodensee 95, Pfälzerwald 360 <!-- select region, count(*) from trails where kind='day_hike' group by region; CSV: 4014 Zeilen, 3048 automatisch verworfen, 389 mit manual_reason „Vorschlag Claude: …“ verworfen --> |
| Unterkünfte | OSM (Hotel, Pension, Ferienwohnung, Chalet, Hostel, Hütte, Campingplatz; ODbL), Website-Link, falls vorhanden | 3514 Unterkünfte, 9426 Verknüpfungen mit Wegen <!-- select count(*) from lodgings; select kind, count(*) from lodgings group by kind; select count(*) from trail_lodgings; --> |
| Einkehr, Aussicht, Gipfel, Wasserfälle, Hütten, Bahnhöfe | OSM (ODbL), gelesen aus Geofabrik-Extrakten (Baden-Württemberg, Rheinland-Pfalz, Schwaben, Schweiz, Österreich; `make osm-extract`, `make places`, Stand 2026-10-29 bzw. 2026-11-03). Wegverläufe kommen weiter über Overpass. In `sources` steht dafür eine Zeile `osm`: „OpenStreetMap contributors (Overpass API; Geofabrik extracts …)“ | 2389 Einkehr, 1212 Aussichtspunkte, 628 Gipfel, 85 Wasserfälle, 46 Hütten, 127 Bahnhöfe und Haltepunkte; 4487 davon an Wegen <!-- select kind, count(*) from pois group by kind; --> |
| Orte (Startorte) | OSM (wie oben; ODbL) | 10308 Orte <!-- select count(*) from places; --> |
| Höhenprofile | Copernicus DEM GLO-30 (© DLR e.V. 2010–2014 und © Airbus Defence and Space GmbH 2014–2018, bereitgestellt unter COPERNICUS von EU und ESA), beim Import auf jede Linie gerechnet | alle Linien |
| Bilder | Wikimedia Commons (Geo-Suche entlang der Linie). Urheber und Lizenz stehen je Bild in der Datenbank und am Bild. Eigene Uploads sind privat (Supabase Storage) | 2713 Commons-Bilder zu 530 von 585 Touren und Wegen <!-- select source, count(*) from photos group by source; select count(distinct trail_id) from photos where source='commons'; --> |
| Wissensindex (RAG) | 25 Wikipedia- und 5 Wikivoyage-Artikel (CC BY-SA 4.0, `data/knowledge/sources.yaml`) und 4 eigene Texte (`data/knowledge/*.md`), ChromaDB + BM25 | 1160 Abschnitte im Index <!-- sqlite3 data/chroma/chroma.sqlite3 'select count(*) from embeddings' --> |
| Gruppen | Kuratierte Liste `data/curated/groups.csv`, Link und Prüfdatum je Eintrag | 24 Einträge, alle mit Status „vorschlag“ <!-- select status, count(*) from groups group by status; --> |
| Karte | basemap.de-Vektorkacheln (BKG, CC BY 4.0), zur Laufzeit geladen | – |
| Wetter | Open-Meteo.com (CC BY 4.0), zur Laufzeit für Tage bis 14 Tage ab heute | – |

## Evaluation

Ein fester Testsatz von 64 Anfragen (`data/eval/cases.yaml`) läuft mit `make eval` gegen den echten Agenten: echtes Modell, echte Datenbank, echter Index. Geprüft wird mit Code, nicht von Hand und nicht von einem zweiten Modell. Das Wetter kommt aus gespeicherten Open-Meteo-Daten, damit der Lauf wiederholbar ist. Methode, Kennzahlen und Grenzen stehen in [docs/evaluation/README.md](evaluation/README.md).

SMART-Ziele, drei Wiederholungen vom 2026-11-03 mit `openai/gpt-4o-mini` ([Lauf 1](evaluation/bericht-2026-11-03-openai-gpt-4o-mini-lauf1.md), [2](evaluation/bericht-2026-11-03-openai-gpt-4o-mini-lauf2.md), [3](evaluation/bericht-2026-11-03-openai-gpt-4o-mini-lauf3.md)):

| Ziel | Ist-Wert (jeder der drei Läufe) | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0 von 110 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen im Text | erreicht (3/3) |
| ≤ 2 % nicht belegte Zahlen | 0 von 661–690 Zahlen (0,0 %) | erreicht (3/3) |
| 100 % offen benannte Unerfüllbarkeit | 10 von 10 Fällen | erreicht (3/3) |
| Recall@5 ≥ 0,8 | 10 von 10 Fällen (1,00) | erreicht (3/3) |

Bestanden sind in jedem Lauf 64 von 64 Fällen: erfüllbar 18, unerfüllbar 10, Mehrtag 12, Änderung 5, Wissen 10, Eingabeschutz 6 sowie Gruppen und Läufe 3. 12 Fälle (Bodensee, Pfälzerwald, Schweiz, Englisch) kamen nach dem Basislauf vom 2026-10-31 dazu und wurden nicht an gpt-4o-mini entwickelt, sondern vorab nur gegen die Datenbank geprüft. Im Abgleich mit OSM wichen 0 von 116 Touren und Plan-Tagen um mehr als 2 % ab. Ein Lauf kostete 0,032–0,034 USD.

Zusätzlich zu den SMART-Zielen zählt der Lauf falsche Unerfüllbarkeits-Behauptungen: Antworten, die „Keine Tour erfüllt alle Wünsche“ sagen, obwohl der Code nicht ausweichen musste. Ergebnis: 0 von 30 erfüllbaren Fällen in jedem Lauf, der Code musste keinen solchen Satz entfernen. Vor dem Fix vom 2026-10-31 schrieb das Modell den Satz in 12 von 12 erfüllbaren Tagestour-Fällen, ohne dass ein Fall rot wurde ([Befunde](evaluation/README.md#befunde)).

Der [Modellvergleich](evaluation/vergleich.md) nutzt denselben Testsatz. `openai/gpt-4.1-mini` (rund doppelt so teuer) bestand vor einem Grounding-Fix 59 und 58 von 64 Fällen: Es schrieb „902 m Anstieg“, und das Grounding las „m“ als Länge (behoben, danach 60 und 61 von 64). Die übrigen Fehler sind falsch herausgelöste Ortsangaben („near Überlingen“), bei denen der Code nachfragt, statt etwas zu erfinden. `google/gemini-2.5-flash-lite` war am 2026-11-03 beim Anbieter gedrosselt (HTTP 429); von den beantworteten Fällen bestanden 42 von 43 und 55 von 55. gpt-4o-mini bleibt Standardmodell.

Was die Zahlen **nicht** zeigen:

- **Drei Läufe sind wenig, ein Konfidenzintervall gibt es nicht.** Bei 10 Fällen je Ziel verschiebt ein einziger Fall die Quote um 10 Prozentpunkte; seltene Fehler zeigen drei grüne Läufe nicht.
- **Der Testsatz ist klein und selbst geschrieben.** 52 der 64 Fälle sind mit gpt-4o-mini entwickelt worden, alle sind so gewählt, dass die Daten die Fälle tragen. Er misst, ob der Agent richtig mit den Daten umgeht, nicht, wie gut er echte Anfragen abdeckt.
- **Die Zahlenquote erfasst nur Zahlen mit Einheit.** Falsche Aussagen ohne Zahl misst sie nicht. Ein Beispiel: Die falsche Behauptung „Keine Tour erfüllt alle Wünsche“ bei erfüllbaren Anfragen fiel keiner Kennzahl auf, sondern erst beim Aufnehmen der Screenshots ([Befunde](evaluation/README.md#befunde)). Seitdem prüft der Testsatz genau diesen Satz, andere falsche Sätze ohne Zahl weiterhin nicht.

## Ethik und Datenschutz

- **Herkunft und Lizenz sind sichtbar.** Jede importierte Zeile hat eine Quelle mit Lizenz. Die Karte nennt OSM (ODbL) und BKG (CC BY 4.0), jedes Bild Urheber und Lizenz, jede Wissensantwort ihre Quelle mit Lizenz. Der Wetterhinweis nennt Open-Meteo (CC BY 4.0). Die Etappeneinteilungen sind als Fakten mit Link übernommen, ohne Texte.
- **Der Standort bleibt im Browser.** „Unterwegs“ rechnet Restkilometer und Ankunft auf dem Gerät. Die Position wird weder gesendet noch gespeichert noch protokolliert. Die Ortung läuft nur, solange die Seite offen und gestartet ist. Es gibt keine Hintergrundortung und keine Aufzeichnung.
- **Eigene Fotos sind privat.** Nur der Eigentümer sieht sie (Row Level Security). Vor dem Hochladen kodiert der Browser sie neu als JPEG. Dabei fallen EXIF- und GPS-Daten weg.
- **Keine Kontodaten an das Modell.** E-Mail und Nutzer-ID gehen nicht an das Modell und nicht an LangSmith (dort nur ein gekürzter SHA-256). Das lokale Chat-Protokoll (`data/logs/chat.jsonl`) enthält für den Admin-Bereich Suchtext, Antwort und Nutzer-ID, also persönliche Daten: Es bleibt lokal, ist git-ignoriert und nur im Admin-Backend `/backend` sichtbar (siehe [Backend (Admin)](#backend-admin)).
- **Prompt-Injection:** Der Eingabeschutz beantwortet bekannte Injection-Muster und themenfremde Fragen mit einer festen Antwort, ohne das Modell aufzurufen. Antworten, die den Systemprompt wiedergeben würden, werden ersetzt.
- **Sicherheitshinweis:** Wetter, Sperrungen und Gelände bitte vor Ort selbst prüfen. Die App ersetzt keine Ortskenntnis. Gehzeiten sind Richtwerte nach DIN 33466 ohne Pausen.
- **Gruppen:** Die Liste enthält nur Name, Art, Ort, Link und Prüfdatum, keine Personen und keine Termine. Sie sagt offen, ob ein Eintrag von Hand oder nur automatisch geprüft ist.

Grenzen, die die App nicht wegnehmen kann:

- **Zimmerverfügbarkeit ist unbekannt.** Die App prüft und bucht keine Zimmer. Sie verlinkt die Website der Unterkunft oder eine Suche. Eine Unterkunft im Plan heißt nicht, dass dort ein Zimmer frei ist oder dass sie noch geöffnet hat.
- **OSM-Daten können veraltet oder unvollständig sein.** Das betrifft Wegverläufe, Unterkünfte, Einkehr und Haltestellen, mit dem Stand des Imports (2026-10-28 bis 2026-11-03). <!-- select min(retrieved_at)::date, max(retrieved_at)::date from sources; -->
- **Gut kartierte Gebiete sind bevorzugt.** Touren, Unterkünfte und Fotos gibt es dort, wo OSM und Commons viele Daten haben. Weniger kartierte Orte kommen seltener vor, Orte außerhalb der drei Regionen gar nicht (siehe Bekannte Lücken).
- **Das Modell kann trotz Grounding falsch formulieren.** Geprüft werden Zahlen mit Einheit, Tournamen und der Satz „Keine Tour erfüllt alle Wünsche“, nicht die übrigen Aussagen dazwischen. Ein Beispiel steht unter [Bekannte Lücken](#bekannte-lücken).
- **Angaben zu Läufen sind ohne Gewähr.** Sie stammen live aus dem Web, jedes Feld mit wörtlichem Zitat von der Seite des Veranstalters. Termine können sich trotzdem ändern, deshalb bitte beim Veranstalter prüfen.
- **KI-Kosten:** Jede Nachricht kostet Geld bei OpenRouter, gedeckelt auf 0,05 USD und 8 Werkzeugaufrufe je Nachricht. Je Konto gelten höchstens 10 Nachrichten pro Minute und 100 pro Tag. Ein Eval-Lauf über 64 Fälle kostet etwa 0,033 USD. Die Websuche für Läufe kostet etwa 0,007 USD je Suche.

## Schnellstart

Voraussetzungen: Docker, Node.js (für `npx supabase`) und [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env   # danach SUPABASE_ANON_KEY aus `npx supabase status` eintragen
make up                # Supabase starten, API und Web-App bauen und starten
make import            # Wege, Tagestouren, Unterkünfte und Fotos importieren (dauert)
make test              # Tests von Backend und Web-App
```

Die Web-App läuft dann auf http://localhost:3000.

## Chat starten

Der Chat nutzt ein Sprachmodell über [OpenRouter](https://openrouter.ai) (Standard `openai/gpt-4o-mini`).

1. Schlüssel in `.env` eintragen: `OPENROUTER_API_KEY=...` (die Datei wird nicht eingecheckt; je Nachricht gelten höchstens 0,05 USD und 8 Werkzeugaufrufe).
2. Touren, Orte und Merkmale müssen importiert sein (`make import`), dann Merkmale und Wissensindex bauen:

   ```sh
   make tags knowledge
   ```

   Die API lädt Merkmale und Orte beim ersten Chat; nach `make tags` oder einem neuen Orts-Import die API neu starten (`make up`).

3. API und Web-App starten (`make up`), http://localhost:3000 öffnen und den Chat in der Mitte der Startseite nutzen, als Gast oder angemeldet (siehe „Konto anlegen“). Hat der Chat Touren gefunden, stehen sie als Kacheln rechts neben dem Chat; ein Klick auf eine Kachel öffnet die Tourseite mit eingebetteter Karte, Beschreibung, Unterkünften, Einkehr und Aussicht. Bei genau einer Tour zeigt die Startseite gleich Beschreibung und Karte, bei einem Mehrtagesplan die Tage und den Weg zur Planansicht `/plan` mit Karte. Je Konto gelten höchstens 10 Nachrichten pro Minute und 100 pro Tag (gezählt je Nutzer-ID). Gäste haben 10 Anfragen in 24 Stunden je IP-Adresse (IPv6 je /64) und alle Gäste zusammen 200 (`HIKESENSE_GUEST_PER_DAY`, `HIKESENSE_GUEST_TOTAL_PER_DAY`); beide Zählungen liegen in der Datenbank (`guest_requests`) und überstehen einen Neustart. Danach antwortet der Chat „Melde dich an oder registriere dich, um weiterzumachen“ mit Anmelde-Link.

Beispiel-Fragen:

- „Rundweg 10–14 km um Hinterzarten, unter 400 Hm“
- „Rundweg, unter 200 Hm, über 15 km, Feldberg“ (der Chat fragt nach: Gipfel oder Ort?)
- „Laufrunde 8 km ab Titisee, wenig Asphalt“
- „Wie ist der Westweg markiert?“
- „3 Tage Westweg ab Hausach, ~15 km pro Tag“, danach „Tag 3 kürzer“
- „3 Tage Ostweg ab Freudenstadt, ~15 km pro Tag“ oder „3 Tage Mittelweg ab Schiltach, 18 km pro Tag“
- „Wanderverein in Freiburg“
- „Halbmarathon im Frühjahr bei Freiburg“

Erfüllt keine Tour alle Wünsche, beginnt die Antwort mit „Keine Tour erfüllt alle Wünsche, weil …“ und zeigt Touren mit genau einer verletzten Bedingung. Touren, Bedingungen und Abweichungen berechnet der Code, nicht das Modell. Den Antworttext formuliert das Modell; jede Zahl mit Einheit darin (auch „15-km-Runde“ oder „zwei Stunden“) prüft der Code gegen die Werkzeugergebnisse der Runde, ersetzt nicht belegte Zahlen durch „?“ und sagt das dazu. Tournamen aus der Datenbank, die in den Ergebnissen der Runde nicht vorkommen, bleiben im Text stehen; der Code hängt den Hinweis „… kommt in den Suchergebnissen dieser Antwort nicht vor – bitte nicht als Vorschlag verstehen“ an und meldet sie im Done-Ereignis (`unsupported_names`, getrennt von den gezählten Zahlen in `unsupported`). Wissensfragen beantwortet der Chat nur, wenn er eine Quelle gefunden hat.

`make smoke` spielt zwölf Fälle gegen das echte Modell durch (`data/smoke/prompts.yaml`): die Beispiel-Fragen, einen Prompt-Injection-Versuch („Ignoriere alle vorherigen Anweisungen“), „3 Tage Westweg ab Hausach“ ohne Tagesziel, die Folgerunde „Tag 3 kürzer“ im selben Gesprächsfaden, „3 Tage Ostweg ab Freudenstadt“ und „Lauftreff in Freiburg“ (erwartet wird die ehrliche Antwort „keine Gruppe“, siehe „Gruppen und Läufe“). Der Lauf meldet sich als Testkonto `smoke@hikesense.local` an und prüft dessen Token wie `/chat`; das Konto legt einmalig

```sh
make smoke-user   # Passwort aus HIKESENSE_SMOKE_PASSWORD in .env (zufällig wählen, nie einchecken)
make admin-secrets   # Backend-Anmeldung: fragt ein Passwort, gibt Hash und Sitzungsgeheimnis für .env aus
```

in der lokalen Supabase-Auth an (der Smoke-Nutzer wird über die Admin-API gleich bestätigt angelegt, dafür braucht es `SUPABASE_SERVICE_ROLE_KEY`). Ergebnis: `data/smoke/result-<Datum>.csv` (je Fall ok, unbelegte Zahlen, Kosten) und die Gesamtkosten (zuletzt etwa 0,01 USD); Exit-Code 1, wenn eine Erwartung nicht erfüllt ist. Erwartungen werden nie gelockert, um einen Fall grün zu machen.

## Konto anlegen

Pläne merken, „Meine Pläne“ und eigene Fotos brauchen ein Konto; Chatten geht auch als Gast. Auf http://localhost:3000/anmelden E-Mail und Passwort (mindestens 6 Zeichen) eingeben und „Konto anlegen“ wählen. Supabase schickt eine Bestätigungsmail (`enable_confirmations = true` in `supabase/config.toml`); lokal landet sie im Test-Postfach Mailpit unter http://127.0.0.1:54324. Der Link führt auf `/anmelden/bestaetigt`, erst danach ist die Anmeldung möglich („Bestätigungsmail erneut senden“ steht auf der Anmeldeseite). „Passwort vergessen?“ schickt einen Link auf `/passwort-neu`; die Meldung ist immer dieselbe, ob es die Adresse gibt oder nicht. Die Mailtexte sind die Standardtexte von Supabase; echter Versand (SMTP) kommt erst mit dem Online-Gang. Danach steht im Kopf neben „Fernwege“ das Kontomenü mit „Meine Pläne“ und „Abmelden“. Meldet sich ein Gast mitten im Gespräch an, bleibt der sichtbare Verlauf stehen, das Gedächtnis des Assistenten beginnt aber neu.

- Die API nimmt `/chat` ohne `Authorization`-Header als Gast an. Ein mitgeschicktes, aber ungültiges oder abgelaufenes Token gibt 401 (kein stiller Wechsel zum Gast). Läuft die Sitzung mitten im Gespräch ab, zeigt der Chat „Sitzung abgelaufen – bitte erneut anmelden“, der getippte Text bleibt im Eingabefeld.
- Das Backend prüft das Token über die JWKS der lokalen Supabase (`SUPABASE_URL`); ältere Projekte mit HS256 brauchen `SUPABASE_JWT_SECRET` in `.env`.
- An das Modell gehen weder E-Mail noch Nutzer-ID. Das Protokoll (`data/logs/chat.jsonl`) enthält die Nutzer-ID für das Backend (siehe „Backend (Admin)“); ältere Zeilen haben nur einen gekürzten SHA-256 der ID (12 Zeichen).
- Gemerkte Pläne und hochgeladene Fotos sieht nur ihr Eigentümer (Row Level Security). Fotos werden vor dem Hochladen im Browser neu als JPEG kodiert, dabei fallen EXIF- und GPS-Daten weg; erlaubt sind JPEG, PNG und WebP bis 10 MB.
- **Konten (`app_users`):** Jedes Konto hat eine Zeile in `app_users` mit Status `aktiv` oder `gesperrt`; sie entsteht per Trigger bei der Registrierung, Clients können nur ihre eigene lesen. Rollen gibt es nicht mehr: Der Admin ist kein App-Konto. `make users-migrate` bestätigt nach dem Umstieg einmalig alle bestehenden Konten und löscht das alte `admin@hikesense.local`.
- **Sperren:** Im Backend sperrt der Admin ein Konto. Das Backend setzt über die Supabase-Admin-API (`SUPABASE_SERVICE_ROLE_KEY`) eine Sperre (keine Anmeldung, keine Token-Erneuerung) und den Status `gesperrt`. Das noch bis zu einer Stunde gültige Access-Token bewirkt nichts mehr: `/chat` antwortet 403, und RLS lässt in `saved_plans`, `photos` und dem Upload-Bucket nichts mehr schreiben oder löschen. Die Web-App fragt beim Start `/api/account` und meldet ein gesperrtes Konto ab (Chat leer, Hinweis „Dein Konto ist gesperrt.“). Abgemeldet kann die Person wie jeder Gast weiterchatten.
- **Gast-IP:** Next reicht `X-Forwarded-For` nur durch, deshalb glaubt die API den Header erst mit `HIKESENSE_TRUSTED_PROXY_HOPS` > 0 (Anzahl der Reverse-Proxys vor der Web-App, die ihn ergänzen; online z. B. 1). Lokal (0) teilen sich alle Gäste eine Zählung. Im Protokoll steht für Gäste nur `gast:` plus ein Hash, nie die IP.
- **Ergebnis merken:** Auf der Startseite speichert „Ergebnis merken“ (erst nach Ende der Antwort aktiv) eine Suche als Momentaufnahme: Nachrichten, Antwort, Hinweis und Kacheln. Sie steht unter „Meine Pläne“ im Abschnitt „Gemerkte Suchen“; `/gemerkt?id=…` zeigt sie so, wie sie war, ohne die Suche neu zu starten.

### Backend (Admin)

`/backend` (nirgends verlinkt, `noindex`) zeigt Benutzer und ihre Suchen mit Details und Summen und unten die Benutzerverwaltung (Status unbestätigt/aktiv/gesperrt, Registrierung, letzte Anmeldung, Sperren/Entsperren mit Rückfrage). Es hat eine eigene Anmeldung: Name `admin`, Passwort gegen `HIKESENSE_ADMIN_PASSWORD_HASH` (bcrypt), danach ein signiertes HttpOnly-Cookie (`HIKESENSE_ADMIN_SESSION_SECRET`, 8 Stunden), das sich der Server zusätzlich merkt: „Abmelden“ macht auch eine Kopie des Cookies sofort ungültig, ein Neustart der API meldet den Admin ab. Supabase-Tokens zählen dort nicht. POST-Anfragen von fremden Seiten (anderer `Origin`) lehnt die API ab. Nach 5 Fehlversuchen in 15 Minuten ist die Anmeldung gesperrt (429). Fehlt Hash oder Geheimnis, ist das Backend aus. Gäste erscheinen als eine Zeile „Gäste“. `/admin` gibt es nicht mehr.

Das Protokoll enthält je Anfrage:

- Suchtext (und bis zu 5 frühere Nachrichten des Gesprächs), verstandene Anfrage und Antwort
- Tourkandidaten mit Begründung und den Mehrtagesplan
- Prompts und Ausgaben jedes LLM-Aufrufs mit Tokens, Kosten und Dauer (Prompts und Ausgaben werden wie Tool-Ergebnisse bei 20.000 Zeichen gekürzt)
- Tool-Aufrufe mit Argumenten und Ergebnissen (bis zu 20.000 Zeichen je Ergebnis)
- Gesamtdauer und Benutzer-ID

Die Kosten der einzelnen Aufrufe müssen nicht die Gesamtkosten ergeben: Fehlgeschlagene LLM-Aufrufe zählen in der Summe mit, stehen aber nicht in der Liste.

Nie im Protokoll stehen Passwörter, Tokens oder Fehlermeldungen von Ausnahmen. Ältere Zeilen (vor dieser Änderung) haben nur die Kennzahlen und werden über den Hash der Benutzer-ID den Benutzern zugeordnet.

**Gäste:** Gezählt (Tabelle `guest_requests`) und protokolliert wird je Gast nur ein HMAC der IPv4-Adresse bzw. des IPv6-/64-Netzes mit `HIKESENSE_GUEST_SALT`, nie die Adresse selbst. Ungültige oder leere Nachrichten verbrauchen kein Gast-Kontingent.

**Datenschutz:** Durch Suchtexte und Benutzer-ID enthält `data/logs/chat.jsonl` jetzt persönliche Daten. Die Datei nicht weitergeben, nicht einchecken und nicht in Berichte oder Screenshots übernehmen.

### LangSmith (optional)

With tracing on, every chat turn shows up in [LangSmith](https://eu.smith.langchain.com) as one run named `chat`: the LangGraph nodes, below them each LLM call (structured output, tool rounds, answer, the events web search) and each tool call (`search_day_hikes`, `plan_multiday`, the knowledge tools), with tokens, cost and duration. The run metadata carries the `request_id` of the matching `/backend` log line, `lang` and hashes of user and thread; tool inputs and outputs are cut at 20,000 characters.

Off by default. To enable, set in `.env` (also passed to the `api` service by `docker compose`) and restart the API:

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_PROJECT=hikesense
```

**Privacy:** with tracing on, user messages, model prompts and answers and tool results leave the machine and are stored by LangChain Inc. (EU region). The raw user id and e-mail are never sent, only the user hash. Keep it off for anything you do not want to share with that service; tests always run with tracing off.

## Mehrtagestour

„3 Tage Westweg ab Hausach, ~15 km pro Tag“ ergibt einen Plan Tag für Tag. Das geht auf allen drei Fernwegen: Westweg (West- und Ostvariante, Pforzheim – Basel), Mittelweg (Pforzheim – Waldshut, westliche Variante über Häusern) und Ostweg (Pforzheim – Schaffhausen). Nennt die Nachricht keinen Fernweg (etwa „4 Tage ab Pforzheim“, Pforzheim liegt an allen drei), fragt der Chat „Auf welchem Fernweg?“, statt zu raten. „Westweg“ allein heißt Westvariante; das Verständnis-Echo sagt dann „Ostvariante möglich“. Der Code plant, das Modell formuliert nur:

- **Tagesziel ist eine Unterkunft höchstens 1000 m vom Weg.** Nur wenn im Band keine liegt, wird bis 2000 m ausgewichen; der Zuweg wird dann am Ankunftstag und am Folgetag zur Strecke addiert und genannt. Gibt es auch das nicht, nennt der Plan die Lücke („Keine Unterkunft ≤ 1 km zwischen km A und km B“) statt eine zu erfinden.
- **Tagesstrecke:** ohne Angabe 15 km, Toleranzband ±20 %. Liegt ein Tag außerhalb, steht der Grund im Plan.
- **Zeiten:** Start ohne Angabe 09:00 Uhr, Ankunft = Start + Gehzeit nach DIN 33466 **ohne Pausen** (so beschriftet). Würde ein Tag nach Mitternacht enden, gibt es keine Ankunftszeit, sondern einen Hinweis.
- **Wegende:** Der Plan läuft nicht über das Ende hinaus („ab Kandern bleiben 28 km bis Basel – 2 Tage bei ~15 km“).
- **Folgerunden** im selben Gespräch: „Tag 3 kürzer“ oder „Tag 2 länger“ ändern nur diesen Tag (und planen die Tage danach neu), die Tage davor bleiben gleich. „Und eine Regenvariante für Tag 1?“ zeigt die Regenvariante (an Regentagen kommt sie von selbst): bis zur nächsten Haltestelle am Weg, weiter mit Bus/Bahn (Fahrplan selbst prüfen).
- **Wetter:** Mit Startdatum („ab 2. November“) holt der Code für Tage bis 14 Tage ab heute eine Vorhersage von Open-Meteo (Quelle „Open-Meteo.com (CC BY 4.0)“ steht dabei); spätere Tage zeigen „noch keine Vorhersage“. Regentag = Niederschlagswahrscheinlichkeit ≥ 60 % oder ≥ 5 mm.
- Der Plan erscheint auf der Startseite neben dem Chat, `/plan` zeigt ihn mit den Tagesabschnitten auf der Karte; „Merken“ speichert ihn unter „Meine Pläne“ (`/plan?id=…`), von dort öffnet „Unterwegs“ einen Tag.

Lücken bei Wegenden, Startorten und Etappenlängen stehen unter [Bekannte Lücken](#bekannte-lücken).

## Wetter-Tagesfinder

„Feldberg-Wanderung bei schönem Wetter“, „Rundweg am Titisee, wenn es schneit“ oder „3 Tage Westweg ab Hausach bei trockenem Wetter“ (englisch: „fine weather“, „dry“, „snow“): Nennt die Nachricht einen Wetterwunsch, sucht der Code die passenden Tage in der Vorhersage von Open-Meteo. Das Modell erkennt nur den Wunsch; Tage, Zahlen und Sätze kommen vom Code, in der Sprache der Anfrage und mit der Quelle „Open-Meteo.com (CC BY 4.0)“.

| Wunsch | Schwelle |
| --- | --- |
| schön / fine | Wettercode 0–3 (klar bis bedeckt, kein Nebel, kein Niederschlag), Niederschlag ≤ 0,5 mm, Niederschlagswahrscheinlichkeit ≤ 30 % |
| trocken / dry | Niederschlag ≤ 1,0 mm, Wahrscheinlichkeit ≤ 40 % |
| Schnee / snow | Schneefall ≥ 1,0 cm oder Schnee-Wettercode (71–77, 85, 86) |

Die Konstanten stehen in `backend/src/hikesense/agent/weather.py`.

- **Horizont:** heute bis heute + 14 Tage, nie darüber. Keine Klimastatistik, keine Wetterwarnungen.
- **Ein Punkt:** Eine Tagestour wird am Startort bewertet (bei einem Gebiet in der Mitte der Box), eine Mehrtagestour am Tagesziel jeder Etappe. Bei Mehrtagestouren sucht der Code Starttage, an denen alle Tage passen; passt keiner, nennt der Satz, wie viele Tage höchstens passen.
- **Ehrlichkeit:** Passt kein Tag, steht das so da („In den nächsten 14 Tagen passt kein Tag …“), dazu die am ehesten passenden Tage. Es wird nichts geschätzt und keine Vorhersage erfunden. Fehlen Werte, heißt es „lässt sich nicht sagen“, ist Open-Meteo nicht erreichbar, „Wetter gerade nicht abrufbar“. Alle Zahlen kommen aus Open-Meteo und laufen durch die Zahlenprüfung oder stehen in vom Code geschriebenen Sätzen. Ohne Wetterwunsch ändert sich nichts.
- **Anzeige:** Die Karte „Tage für …“ steht im Chat über den Touren, im Admin-Detail als Block „Wetter-Tagesfinder“. Der Smoke-Test (Fälle 15–18) prüft nur die Form, nicht bestimmte Tage, weil sie vom echten Wetter abhängen.

### Online-Gang mit Supabase Cloud (Reihenfolge)

1. **Projekt anlegen** (Region EU) und lokal verknüpfen: `npx supabase link --project-ref <ref>`.
2. **Schema:** `npx supabase db push` spielt alle Migrationen aus `supabase/migrations/` ein (Tabellen, RLS, Trigger für `app_users`, Bucket `uploads`).
3. **Auth einstellen** (Dashboard → Authentication): E-Mail-Bestätigung an; *Site URL* = öffentliche Adresse; *Redirect URLs* = `<adresse>/anmelden/bestaetigt` und `<adresse>/passwort-neu`; eigenes SMTP eintragen (der eingebaute Versand ist stark begrenzt); Mailtexte für Bestätigung und Passwort-Reset anpassen (sonst englische Standardtexte).
4. **`.env` für den Server:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` (bzw. JWKS über `SUPABASE_URL`) und `SUPABASE_DB_URL` (Verbindungs-String aus dem Dashboard) aus dem Cloud-Projekt; `make admin-secrets` für Backend-Passwort, Sitzungsgeheimnis und `HIKESENSE_GUEST_SALT` (neu erzeugen, nicht die lokalen Werte übernehmen); `HIKESENSE_TRUSTED_PROXY_HOPS` = Zahl der Proxys vor der Web-App (z. B. 1); `HIKESENSE_ALLOWED_ORIGINS` = öffentliche Adresse; `OPENROUTER_API_KEY`.
5. **Daten laden:** `make import`, `make places`, `make knowledge`, `make tags` gegen die Cloud-Datenbank (dauert; die Wissensdatenbank `chroma/` liegt neben der API, nicht in Supabase).
6. **Bestehende Konten** nur beim Umzug aus einer alten Datenbank: `make users-migrate` (bestätigt alte Konten, löscht das alte Admin-Konto). Bei einem leeren Projekt entfällt der Schritt.
7. **API und Web starten** (Docker Compose oder Hosting). Der Web-Container bekommt nur `SUPABASE_URL`, `SUPABASE_ANON_KEY` und `API_INTERNAL_URL`, nie die geheimen Schlüssel. `NEXT_PUBLIC_SUPABASE_URL` und `NEXT_PUBLIC_API_URL` bleiben leer (alles läuft über den Proxy der Web-App).
8. **Prüfen:** `make smoke-user && make smoke`; dann im Browser registrieren, bestätigen, merken, unter `/backend` anmelden, das Konto sperren und entsperren.

## Auf dem Handy (HTTPS-Tunnel)

Die Ortung („Unterwegs“) und die Installation als App brauchen HTTPS: Browser geben den Standort nur auf sicheren Seiten frei (`localhost` zählt, die Adresse im WLAN wie `http://192.168.…:3000` nicht). Ein Tunnel gibt der lokalen Web-App eine HTTPS-Adresse:

```sh
make up
cloudflared tunnel --url http://localhost:3000
```

`cloudflared` gibt eine Adresse `https://….trycloudflare.com` aus; sie öffnest du auf dem Handy und wählst „Zum Startbildschirm hinzufügen“ bzw. „App installieren“. Die Installation nutzt `web/public/manifest.webmanifest` und einen kleinen Service Worker (`web/public/sw.js`), der nur die App-Hülle zwischenspeichert, keine Karten und keine Antworten der API; er wird nur im Produktionsbuild (`npm run build && npm start`) angemeldet, nicht in `npm run dev`.

Die Position bleibt auf dem Gerät: „Unterwegs“ rechnet Restkilometer und Ankunft im Browser, sendet und speichert nichts und orten läuft nur, solange die Seite offen und gestartet ist. Ohne HTTPS (reines HTTP im WLAN) funktionieren Chat, Touren und Karte weiter; nur Ortung, Service Worker und Installation fehlen.

Ein Tunnel reicht: Der Browser spricht nur mit der Web-App (Port 3000). Für die Gast-Grenzen und die Backend-Anmeldebremse `HIKESENSE_TRUSTED_PROXY_HOPS=1` in `.env` setzen, solange der Tunnel der einzige Zugang ist (Cloudflare hängt die echte Client-IP an `X-Forwarded-For` an); sonst teilen sich alle Gäste eine Zählung, und fünf falsche Backend-Anmeldungen von irgendwem sperren die Anmeldung für alle 15 Minuten. Next leitet `/api/chat` an die API (`API_INTERNAL_URL`, in Compose `http://api:8000`) und `/sb/…` an Supabase (`SUPABASE_URL`) weiter (`web/next.config.ts`); der Chat-Stream wird dabei nicht gepuffert. Über die Tunnel-Adresse gehen so Anmelden, Chat, Touren, Karte, Merken, gemerkte Pläne, „Unterwegs“ und eigene Fotos. `NEXT_PUBLIC_SUPABASE_URL` und `NEXT_PUBLIC_API_URL` bleiben dafür leer; gesetzt umgehen sie den Proxy (dann wieder nur am Rechner selbst erreichbar).

## Gruppen und Läufe

**Gruppen** („Wanderverein in Freiburg“, „Alpenverein bei Offenburg“): Der Chat zeigt Einträge einer kuratierten Liste (`data/curated/groups.csv`, Import mit `make groups`) im Umkreis von 25 km, nach Abstand sortiert. Je Gruppe stehen nur Name, Art, Ort, Link, Quelle und Prüfdatum in der Liste, keine Personen und keine Termine; Treffzeiten stehen auf den Seiten der Gruppen. Die Antwort nennt „Stand: <Prüfdatum>“ und wie geprüft wurde: „von Hand geprüft“ nur bei Status „geprüft“, sonst „automatisch geprüft (Seite und Name abgerufen), noch nicht von Hand bestätigt“. Einträge mit Prüfdatum älter als 180 Tage sind als „veraltet“ markiert. Die Routenseite zeigt zusätzlich „Gruppen in der Nähe“. Das ist die einzige Ausnahme von „keine Community-Funktionen“ (Spec §3).

Die Liste hat 24 Einträge (Schwarzwaldverein-Ortsgruppen und DAV-Sektionen). Was dort fehlt, steht unter [Bekannte Lücken](#bekannte-lücken).

**Läufe** („Halbmarathon im Frühjahr bei Freiburg“): Der Chat sucht live im Web (OpenRouter-Websuche, etwa 0,007 USD je Suche, zählt ins Budget der Nachricht) und liest höchstens 3 Seiten von Veranstaltern (eigener User-Agent `HIKESENSE_USER_AGENT`, `robots.txt` wird beachtet, 10 s Zeitlimit, höchstens 1 MB je Seite).

- **Quellenpflicht:** Jedes Feld (Name, Datum, Ort, Distanzen, Anmeldelink, Anmeldeschluss, Startgebühr) erscheint nur mit wörtlichem Zitat von der Seite des Laufs, sonst steht „nicht angegeben“. Läufe mit Datum in der Vergangenheit werden nicht gezeigt. Lässt sich kein Lauf belegen, zeigt der Chat Links zu Laufkalendern (`data/events/calendars.yaml`) statt einer Liste. Dazu der Hinweis „Angaben ohne Gewähr – bitte beim Veranstalter prüfen“.
- **Keine Speicherung:** Ergebnisse landen weder in der Datenbank noch in einem Datei-Cache; jede Frage sucht neu.
- **Ausgeschlossene Portale:** `laufen.de`, `marathon.de`, `d-u-v.org`, `ultra-marathon.org`, `ladv.de` und `hdsports.org` werden weder gesucht noch abgerufen (höchstens als Kalender-Link genannt).

## Bekannte Lücken

**Daten**

- **Basel und Schaffhausen gehören zu keiner Region.** Der Schwarzwald liest nur den Extrakt Baden-Württemberg; die Schweiz ist nur für das Bodensee-Gebiet importiert. Die Wegenden von Westweg (Basel) und Ostweg (Schaffhausen) heißen zwar so, aber dort fehlen Unterkünfte und Haltestellen. „Ab Basel“ lässt sich nicht auflösen, Schaffhausen liegt mehr als 2 km vom Linienende.
- **Nicht jeder Etappenort lässt sich als Startort auflösen.** Beim Westweg sind es 7 von 17 Etappenorten (es fehlen u. a. Unterstmatt, Alexanderschanze, Kalte Herberge, Basel), beim Mittelweg 8 von 10 (es fehlen Zwieselberg und Kalte Herberge), beim Ostweg 10 von 13 (Schramberg und Villingen nur nach Rückfrage, Schaffhausen nicht am Weg). Beim Pfälzer Waldpfad lösen sich 4 von 9 direkt auf: Johanniskreuz ist in OSM keine Ortschaft, Schopp und Erlenbach liegen mehr als 2 km von der Linie, Heltersberg und Hauenstein gehen nach Rückfrage (Ort/Gipfel). Beim Weinsteig schreibt die Etappenquelle „Neustadt a. d. Weinstraße“ und „St. Martin“, OSM „Neustadt an der Weinstraße“ und „Sankt Martin“; die Rückfrage bietet die richtige Schreibweise an. Neukirch (Jubiläumsweg) ist mehrdeutig (vier Dörfer dieses Namens); gleich benannte Orte gleicher Art nennen in der Rückfrage die nächste Stadt („Neukirch (Ort bei Tettnang)“), und „Neukirch bei Furtwangen“ geht auch als freie Eingabe. Bei den übrigen hilft ein Ort in der Nähe als Startangabe. Nach einem Ort, der nicht am Weg liegt, fragt der Chat und bietet nur Etappenorte an, die sich auflösen. <!-- Prüfung 2026-10-31: für jede trail_id stage_places(conn, id) aus hikesense.agent.tools, je Name _is_point(_resolve_start(vocab, name)) aus hikesense.agent.understand; Westweg = Vereinigung von westweg-west und westweg-ost (17 verschiedene Namen) -->
- **Ostweg: 7 von 12 Etappen weichen um mehr als 5 % von den offiziellen km ab.** Am stärksten betroffen ist Etappe 5, Freudenstadt – Alpirsbach, mit 16,7 statt 22,5 km. Der Grund liegt darin, wo die Etappenenden auf der Linie gesetzt sind. Die Etappen 5 bis 7 zusammen weichen nur um 2,7 % ab (66,2 statt 68 km), die ganze Linie hat 244,4 km Etappensumme gegenüber 245,5 km offiziell. Der Wegverlauf selbst ist also nicht kürzer. <!-- select seq, length_km from stages where trail_id='ostweg' order by seq; offizielle km: data/curated/trails.yaml (km je Etappe) -->
- **Mittelweg: 4 von 9 Etappen weichen um mehr als 5 % ab** (Etappen 4, 5, 7 und 9; die OSM-Linie ist dort kürzer als die offiziellen Angaben). Die Quelle ist selbst nicht einheitlich: Sie nennt 249 km Gesamtlänge, ihre Etappen ergeben 233 km. <!-- select seq, length_km from stages where trail_id='mittelweg' order by seq -->
- **Nur eine Variante je Weg, außer beim Westweg.** Angeboten werden der Mittelweg über Häusern (westliche Variante) und der Ostweg ohne die Variante über Loßburg. Beim Westweg gibt es West- und Ostvariante.
- **Haltestellen sind nur Bahnhöfe und Haltepunkte der Bahn.** Bushaltestellen sind nicht importiert. Die Regenvariante führt deshalb immer zu einem Bahnhof oder Haltepunkt am Weg. Eine berechnete Wegvariante über OpenRouteService (Spec §8) ist nicht gebaut.
- **Lauftreffs fehlen in der Gruppenliste ganz**, weil keiner mit eigener, prüfbarer Seite gefunden wurde. „Lauftreff in Freiburg“ beantwortet der Chat deshalb ehrlich mit „In meiner Liste gibt es keine Gruppe (Lauftreff) …“ und erfindet keine.
- **Die 24 Gruppen sind automatisch geprüft, aber noch nicht von Hand.** Alle haben den Status „vorschlag“: Seite und Name wurden am Prüfdatum abgerufen. Die App sagt das bei jeder Antwort dazu.

**Agent**

- **Falsche Unerfüllbarkeits-Behauptungen fängt der Code nur in erkennbarer Form ab.** Bis zum Fix vom 2026-10-31 schrieb das Modell „Keine Tour erfüllt alle Wünsche“ auch bei erfüllbaren Anfragen, weil der Prompt den Satz zitierte ([Befunde](evaluation/README.md#befunde)). Jetzt nennt der Prompt ihn nicht mehr, und ohne Ausweichen entfernt der Code Sätze mit „kein…“, „erfüll…“ und „alle Wünsche/Bedingungen/Anforderungen/Kriterien …“. Eine anders formulierte Behauptung („Leider passt nichts ganz“) bliebe stehen. Verlässlich sind die Karten mit ✓/✗.
- **Eine Streckentour ohne Signalwort verliert die Bedingung.** Das Rundweg-Feld zählt nur, wenn die Nachricht es nennt (Rundweg, Runde, Schleife, Strecke, „von … nach …“ u. a.). Ein Wunsch wie „bis zum Titisee“ ohne eines dieser Wörter wird deshalb verworfen. Für den Rundweg gilt dasselbe: „zurück zum Start“, „im Kreis“ oder „Start und Ziel gleich“ werden nicht erkannt. Die Bedingung fehlt dann sichtbar im Verständnis-Echo (siehe [Befunde der Evaluation](evaluation/README.md#befunde)).
- **Die Evaluation deckt ein Modell und einen selbst geschriebenen Testsatz ab.** Es gab je Konfiguration einen Lauf, siehe [Evaluation](#evaluation).

**Oberfläche**

- **„Unterwegs“ zeigt auf der Karte keine Unterkünfte.** Die Karte zeigt dort nur Weg und Position, ohne Unterkunftsebene ([Screenshot](showcase/11-unterwegs-karte-handy.jpg)).
- **Auf dem Handy steht die E-Mail-Adresse nicht in der Kopfzeile.** Damit die Kopfzeile auf 390 px passt, erscheint sie erst ab 640 px Breite; „Abmelden“ bleibt sichtbar ([Screenshot](showcase/12-startseite-handy.jpg)).

## Offene Prüfungen (vor Abgabe)

Diese Prüfungen kann nur Ali selbst machen. Der Abschnitt wird danach entfernt.

- [ ] Die 24 Gruppen in `data/curated/groups.csv` von Hand prüfen (`geprüft` setzen, `make groups`) und danach die Angaben zu „vorschlag“ in diesem README anpassen.
- [ ] Ein echtes Foto hochladen und prüfen, dass EXIF- und GPS-Daten im gespeicherten Bild fehlen.
- [ ] „Unterwegs“ auf dem Handy über `cloudflared` testen, mit echter Ortung. Die Screenshots oben nutzen eine simulierte Position.
- [ ] Die 389 Ablehnungen in `data/curated/day_hikes.csv` (`manual_decision = rejected`, Grund „Vorschlag Claude: …“) durchsehen. Sie sind von Claude vorgeschlagen, noch nicht von Ali bestätigt. Besonders die 84 mit „Regionsausgleich“: Das ist eine Dichteregel (höchstens zwei Touren je 0,1°-Feld im Schwarzwald), keine Qualitätsregel; ohne sie hätte der Schwarzwald 206 statt 122 Tagestouren. Danach die Angabe in [Daten und Lizenzen](#daten-und-lizenzen) anpassen.
