# Hike all about – Design

Stand: 2026-10-28 · Turing College Capstone (KI-Engineering) · Abgabe ca. 2026-11-25

Kennzeichnung: **[Ali]** = vom Nutzer entschieden, **[Claude]** = meine Entscheidung (darf beim Review geändert werden), **[Builder]** = bewusst offen gelassen.

## 1. Warum

Ali hat eine 3-Tage-Wanderung im Schwarzwald geplant: bekannte Routen gesucht (Westweg, Komoot, Schwarzwaldverein), Empfehlungen verglichen, drei Zimmer hintereinander gebucht, sodass jeden Tag ca. 15 km bis zur Unterkunft am späten Nachmittag lagen, mit Plan B für Regen. Es hat gut funktioniert, kostete aber **mehrere Tage Vorbereitung**. Das Schwierige war nicht das Finden eines Weges, sondern dass **Strecke, Übernachtung und Wetter zusammenpassen**.

Vorgänger HikeAI (Sprint 2, Streamlit, `~/projects/HikeAi2`) wurde im Review kritisiert:
- Der Chat ging mit Wünschen falsch um. Beispiel: „Rundweg, unter 200 Hm, über 15 km, Feldberg" ergab erst nichts, dann einen Vorschlag *ohne Rundweg* – **ohne Hinweis**, dass eine Bedingung fallen gelassen wurde.
- Mit den Ergebnissen „kann man nichts machen": keine Route, keine Planung, nur eine Liste.
- Daten kamen fast nur aus OSM, ohne nachvollziehbare Herkunft.

**Hike all about** ist eine neue App, bei der das **Planen** einer Wanderung im Vordergrund steht und der KI-Chat die Hauptbedienung ist.

## 2. Ziele

1. **Mehrtagestour planen [Ali]:** Etappen auf kuratierten Fernwegen (Westweg, Mittelweg, Ostweg) in Tagesabschnitte mit Zielstrecke (z. B. ~15 km) teilen, je Tagesziel passende Unterkünfte vorschlagen, Ankunftszeit berechnen, Wetter berücksichtigen, bei Regen eine Ausweichvariante anbieten.
2. **Tagestouren [Ali]:** 3–5 Vorschläge im eingestellten Umkreis um einen Startpunkt, nicht eine lange Liste.
3. **Ehrlicher Umgang mit Wünschen [Ali]:** Wenn keine Tour alle festen Bedingungen erfüllt, sagt der Agent das mit Begründung und zeigt **ähnliche Touren, bei denen alle übrigen Bedingungen stimmen**, jeweils mit der *einen* verletzten Bedingung und um wie viel (z. B. „340 Hm statt < 200"). Nie stillschweigend lockern.
4. **Chat im Vordergrund [Ali]:** Der Plan entsteht und ändert sich im Gespräch („Tag 3 kürzer", „Unterkünfte mit Halbpension").
5. **Wissensfragen mit Quelle (RAG):** z. B. „Wie ist der Westweg markiert?", „Gibt es auf Etappe 7 Einkehr?" – Antwort mit Quellenangabe.
6. **Unterwegs (PWA) [Ali]:** Auf dem Handy die eigene Position auf der geplanten Etappe sehen, mit Restkilometern und geschätzter Ankunft. Keine Aufzeichnung.
7. **Bilder [Ali]:** Jede Tour/Etappe hat mehrere Bilder (Wikimedia Commons + eigene Uploads), die man durchblättern und als Hintergrund austauschen kann.
8. **Konten [Ali]:** Anmeldung über Supabase Auth; gespeicherte Touren erscheinen auf dem Handy; Fotos hochladen nur angemeldet.
9. **Capstone-Kriterien erfüllen:** README mit Ziel/Problem/Funktionsweise und Showcase-Link oben, Ethik-Abschnitt, Evaluation mit Zahlen, Präsentation in 6 Punkten (10 min).

## 3. Nicht-Ziele

- Keine Verfügbarkeitsprüfung oder Buchung von Zimmern; nur Link nach außen (Website der Unterkunft, sonst Suche) **[Ali]**.
- Kein GPS-Tracking im Hintergrund, keine Aufzeichnung, keine Offline-Karten **[Ali]**.
- Keine native App (React Native) **[Ali]**.
- Keine Region außerhalb des Schwarzwalds **[Ali]**.
- Keine Daten von Komoot, AllTrails oder Booking.com (keine offene Schnittstelle, Scraping widerspricht den Nutzungsbedingungen).
- Keine Community-Funktionen (Bewertungen anderer, öffentliche Fotos fremder Nutzer). Uploads sind privat **[Claude]**. Ausnahme: eine von Hand gepflegte, verlinkte Gruppenliste mit Prüfdatum **[Ali]**.

## 4. Anti-Ziele (Misserfolg, auch wenn es technisch läuft) [Ali]

- **Die KI erfindet Routen oder Zahlen.** Jede Strecke muss aus der Datenbank stammen; jede Zahl (km, Hm, Zeit, Entfernung, Temperatur) aus einem Tool-Ergebnis. Das wird geprüft (Grounding, §8) und gemessen (Evaluation, §9).
- Eine Bedingung wird stillschweigend fallen gelassen (HikeAI-Fehler).
- Daten ohne erkennbare Herkunft.

## 5. Rahmen

- Zeit: 4 Wochen, eine Person mit Claude Code. Umfang muss hart geschnitten werden (§12).
- Kursvorgaben: RAG, LangChain, LangGraph-Agent mit Tools, Prompt Engineering, ChromaDB/Embeddings, Ethik.
- Entwicklung mit Docker **[Ali]**.
- **Betrieb nur lokal [Ali]**, kein öffentliches Hosting. Showcase mit Video und Screenshots. Die PWA-Ansicht „Unterwegs" braucht auf dem Handy HTTPS: Für die Demo wird die lokale App über einen Tunnel (z. B. cloudflared/ngrok) erreichbar gemacht **[Claude]**. Chat nur für angemeldete Nutzer, mit Rate-Limit **[Claude]**.
- Alle Daten mit Quelle und Lizenz; Attribution in der UI (ODbL für OSM, CC BY für basemap.de, Lizenz je Wikimedia-Bild).
- Kosten: Modell über OpenRouter (Standard `openai/gpt-4o-mini` wie in GridLens/HikeAI) **[Claude]**; Budget-Limit je Anfrage.

## 6. Architektur

| Teil | Technik | Entscheidung |
|---|---|---|
| Oberfläche | Next.js (App Router, TypeScript), als PWA installierbar | [Ali] |
| Karte | MapLibre GL mit basemap.de-Vektorkacheln (BKG, CC BY 4.0); Fallback OSM-Kacheln | [Claude] |
| Agent-Backend | Python 3.12, FastAPI, LangGraph + LangChain, Streaming der Antworten an die UI | [Claude] |
| Daten, Auth, Fotos | Supabase (Postgres + PostGIS, Auth, Storage), lokal über Supabase CLI auf Docker | [Ali] |
| Wissenssuche | ChromaDB + BM25 hybrid (Code aus HikeAI `retrieval/` übernehmen) | [Claude] |
| Routing/Varianten | OpenRouteService (Profil foot-hiking), kostenloser Schlüssel | [Claude] |
| Höhen | LGL BW Höhenmodell (offene Daten), vorberechnet beim Import; ORS-Elevation als Fallback | [Claude] |
| Wetter | Open-Meteo (aus HikeAI `tools/weather.py`) | [Claude] |
| Start | `docker compose up` für Web, API, ChromaDB; `supabase start` daneben; ein Makefile/Skript startet beides | [Claude] |

Next.js spricht direkt mit Supabase (Auth, gespeicherte Touren, Fotos) und mit der Python-API (Chat). Die API prüft das Supabase-JWT.

**Übernahme aus HikeAI [Claude]:** Gehzeit nach DIN 33466 (`domain/hiking_time.py`), Wetter (`tools/weather.py`, `domain/weather.py`), Hybrid-Retrieval und RRF (`retrieval/`), Input-Guard und Rate-Limit (`domain/input_guard.py`, `rate_limit.py`), Grounding-Ideen (`pipeline/grounding.py`). Kopiert und angepasst, kein gemeinsames Paket.

## 7. Daten

Alles im Schwarzwald. Jede Zeile trägt `source`, `source_url`, `license`, `retrieved_at`.

| Datenart | Quelle | Umfang |
|---|---|---|
| Fernwege + offizielle Etappen | Wegverlauf: OSM-Relation (Waymarked Trails/Overpass); Etappeneinteilung (Start, Ziel, km): von öffentlichen Etappenseiten übertragen, Link zur Quelle, keine Texte kopiert | Westweg (beide Varianten), Mittelweg, Ostweg |
| Tagestouren | OSM-Wanderrelationen im Schwarzwald (Rundwege und Strecken), gefiltert und **von Hand geprüft** (Lücken im Track, sinnvolle Länge) | **[Builder]** Zielgröße ca. 50–150 Touren |
| Unterkünfte | OSM (`tourism=hotel|guest_house|hostel|alpine_hut|wilderness_hut|camp_site`, Gasthäuser mit Zimmern), Website-Link falls vorhanden | alle im Puffer von 2 km um die Wege |
| Einkehr, Aussichtspunkte, Bahnhöfe/Haltestellen | OSM | im Puffer um die Wege |
| Höhenprofile | LGL-Höhenmodell, beim Import auf jede Linie gerechnet | alle Linien |
| Bilder | Wikimedia Commons (Geo-Suche entlang der Linie; Urheber + Lizenz gespeichert) + eigene Uploads (Supabase Storage, privat) | je Tour mehrere |
| Wissenskorpus (RAG) | Wikivoyage-Artikel zu Schwarzwald/Fernwegen (CC BY-SA; *Verfügbarkeit noch prüfen*), eigene Kurztexte je Etappe (vom Builder geschrieben, mit Quellen), Wegzeichen, Verhalten und Ausrüstung, Hütten-/Einkehrinfos aus OSM-Tags | **[Builder]** |

Import als wiederholbare Python-Skripte (`scripts/import_*`), die einen festen Stand erzeugen. Die App fragt OSM/Overpass **nicht** zur Laufzeit ab.

Kurations-Ergebnis wird als Tabelle versioniert, damit nachvollziehbar ist, welche OSM-Touren aufgenommen oder verworfen wurden und warum.

## 8. Der Agent

### Ablauf (LangGraph) [Claude]

1. **Wünsche verstehen:** Ein Modellaufruf mit strukturierter Ausgabe macht aus der Nachricht eine `HikeRequest`: Art (Tagestour / Mehrtagestour / Wissensfrage / Änderung am Plan), Gebiet oder Startpunkt + Umkreis, Datum/Tage, **feste Bedingungen** (Rundweg, Länge, Hm, Tagesstrecke, Ankunft bis …), **Wünsche** (Aussicht, Einkehr, Halbpension …). Unklares wird nachgefragt, nicht geraten.
2. **Zurückspielen:** Der Agent nennt kurz, was er verstanden hat, und sucht. (HikeAI wartete auf Bestätigung; hier sucht er direkt, der Nutzer kann korrigieren. **[Claude]**)
3. **Suchen und planen (ReAct mit Tools):** Der Agent ruft Tools auf; Zahlen und Treffer kommen nur aus Tools.
4. **Bedingungen prüfen (Code, kein Modell):** Jede vorgeschlagene Tour wird gegen alle festen Bedingungen gemessen. Ergebnis je Bedingung: erfüllt / verletzt um X.
5. **Ausweichen:** Erfüllt keine Tour alle Bedingungen, sucht Code nach Touren, bei denen **genau eine** Bedingung verletzt ist, sortiert nach kleinster Abweichung, je Bedingung höchstens eine Variante. Die Antwort beginnt mit dem ehrlichen Satz „Keine Tour erfüllt alle Wünsche, weil …".
6. **Antwort + Grounding-Prüfung:** Das Modell formuliert die Antwort aus Tool-Ergebnissen. Eine Prüfung im Code sucht jede Zahl und jeden Tour-/Ortsnamen in den Tool-Ergebnissen der Runde. Nicht belegte Zahlen werden entfernt bzw. als Warnung markiert und gezählt (Metrik in §9).
7. **Plan speichern:** Der aktuelle Plan ist Zustand im Graph (Checkpointer) und wird bei angemeldeten Nutzern in Supabase gespeichert. Folgeänderungen („Tag 3 kürzer") arbeiten auf diesem Zustand.

### Tools [Claude]

| Tool | Was es tut |
|---|---|
| `search_day_hikes` | Tagestouren nach Umkreis + Bedingungen (PostGIS); liefert Treffer **und** Abweichungen je Bedingung |
| `plan_multiday` | Teilt einen Fernweg-Abschnitt in Tage: Haltepunkte = Unterkünfte ≤ 1 km vom Weg; wählt die Folge, die der Zieltagesstrecke am nächsten kommt; deterministisch. Gibt es nahe der Zielstrecke keine Unterkunft ≤ 1 km, gilt das wie eine verletzte Bedingung (Ziel 3): Lücke benennen, Ausweichen bis 2 km Abstand (Zuweg wird zur Tagesstrecke addiert) oder kürzere/längere Tagesstrecke anbieten **[Claude]** |
| `find_accommodation` | Unterkünfte um einen Punkt/Etappenziel, Entfernung zum Weg |
| `get_elevation_profile` | Höhenprofil, Hm auf/ab für eine Linie oder einen Ausschnitt |
| `hiking_time` | DIN 33466, Ankunftszeit bei gegebener Startzeit |
| `get_weather` | Open-Meteo für Ort/Tag |
| `route_variant` | ORS-Variante zwischen zwei Punkten, endet immer an der bereits gewählten Unterkunft (siehe „Regenvariante“) |
| `search_knowledge` | Hybride Suche im Wissenskorpus (ChromaDB + BM25) mit Quellen |
| `get_photos` | Bilder zu Tour/Etappe |

**Regenvariante [Claude]:** Eine von ORS berechnete Strecke gilt nicht als „erfunden“: Sie stammt aus einem Tool-Ergebnis und wird als „berechnete Variante (OpenRouteService)“ gekennzeichnet, mit eigener Grounding-Regel (Zahlen müssen aus dem ORS-Ergebnis stammen). Sie endet immer an der schon gewählten Unterkunft, weil Zimmer im Voraus gebucht sind. „Mehr Wald“ und „Einkehr“ werden nicht von ORS gesteuert, sondern über Zwischenpunkte (Einkehr/Waldwege aus der Datenbank) und eine nachträgliche Bewertung mehrerer ORS-Vorschläge. Reicht das nicht, ist die einfache Variante: kürzerer Tag plus Bus/Bahn zur gleichen Unterkunft.

**Wetter-Horizont [Claude]:** Vorhersage nur, wenn die Tour in ≤ 14 Tagen liegt; danach zeigen die Karten „noch keine Vorhersage“, und die Regenvariante kann jederzeit von Hand angefordert werden. Keine Klimamittel.

Limits: max. Tool-Aufrufe, Tokens und Kosten je Nachricht (wie GridLens). Eingaben ohne Wanderbezug werden freundlich abgelehnt (Input-Guard aus HikeAI).

## 9. Evaluation

Ein festes Testset (YAML/CSV), Lauf per Befehl gegen das echte Modell, Ergebnis als CSV + Bericht in `docs/evaluation/` **[Claude]**:

| Gruppe | Beispiel | Gemessen |
|---|---|---|
| Erfüllbare Tagestouren | „Rundweg 10–14 km um Hinterzarten, < 400 Hm" | Alle Bedingungen erfüllt (Code-Prüfung) |
| **Unerfüllbare Wünsche** | „Rundweg < 200 Hm, > 15 km, Feldberg" | Unerfüllbarkeit benannt; jede Ausweichtour verletzt genau eine Bedingung; die genannte Abweichung stimmt |
| Mehrtagestouren | „3 Tage Westweg ab Hausach, ~15 km/Tag" | Tagesstrecken im Toleranzband; Unterkunft ≤ 1 km vom Weg oder Abweichung offen benannt; Ankunftszeit plausibel |
| Änderungen im Gespräch | „Tag 3 kürzer" | Plan geändert, Rest unverändert |
| Wissensfragen (RAG) | „Welche Markierung hat der Westweg?" | Recall@k der richtigen Quelle; Antwort korrekt (Sollantwort) |
| Grounding | alle Fälle | Anteil nicht belegter Zahlen/Namen (Ziel 0 %) |
| Abgleich mit OSM | alle Touren in Antworten | Länge/Hm der Antwort vs. Datenbank vs. OSM-Linie |

Wetterabhängige Fälle laufen mit gespeicherten Wetterdaten (Fixture), damit die Evaluation wiederholbar ist **[Claude]**.

Zielwerte **[Claude]**, als SMART-Ziele für die Präsentation: 0 % erfundene Touren, ≤ 2 % nicht belegte Zahlen, 100 % offen benannte Unerfüllbarkeit, Recall@5 ≥ 0,8. Umfang **[Builder]**: ca. 40–60 Fälle.

Optional, falls Zeit (Fall 7): dasselbe Testset mit 2–3 Modellen/Temperaturen, Ergebnis als CSV.

## 10. Oberfläche

**Layout A „Panorama-Chat" [Ali]** (Entwurf: `.superpowers/brainstorm/…/layout.html` in der Brainstorm-Sitzung):
- Vollflächiges Landschaftsbild der aktuellen Tour als Bühne; Chat-Fenster halbtransparent darüber.
- Etappen/Touren als Bildkarten unten (Tag, Strecke, km, Hm, Zeit, Unterkunft, Wetter).
- Karte und 3-Tage-Wetter klappen auf.
- Bilder je Tour durchblättern, eines als Hintergrund wählen, eigene hochladen **[Ali]**.
- Quellen- und Lizenzhinweise sichtbar an Daten und Bildern.
- Mobil: dieselbe App, Karte im Vordergrund; Taste „Unterwegs" zeigt Position auf der Etappe (Browser-Geolocation, nur während die Seite offen ist), Restkilometer, Ankunft.
- Sprache **[Claude]**: Deutsch zuerst; Englisch nur, wenn Zeit bleibt.
- Feinentwurf (Farben, Schrift) **[Builder]**, im Stil des Entwurfs: Schwarzwaldgrün, warmes Papierweiß, Serifenschrift für Titel.

## 11. Ethik und Datenschutz

- Herkunft und Lizenz jeder Angabe sichtbar; OSM- und BKG-Attribution auf der Karte.
- Standort bleibt im Browser, wird nicht gespeichert oder gesendet.
- Hochgeladene Fotos privat; EXIF-Ortsdaten werden vor dem Speichern entfernt **[Claude]**.
- An das Modell gehen keine Kontodaten (E-Mail).
- Sicherheitshinweis: Wetter, Sperrungen und Gelände vor Ort selbst prüfen; die App ersetzt keine Ortskenntnis.
- Grenzen offen benennen: Verfügbarkeit von Zimmern unbekannt, OSM-Daten können veraltet sein, Bias zugunsten gut kartierter Gebiete.

## 12. Schnitt und Reihenfolge (4 Wochen) [Claude]

| Woche | Ergebnis |
|---|---|
| 1 | Docker/Supabase-Setup, Datenimport (ein Fernweg + erste Tagestouren, Unterkünfte, Höhen), Grundgerüst Next.js mit Layout A und Karte |
| 2 | Agent mit Tools für Tagestouren inkl. Bedingungsprüfung und Ausweichen; Grounding-Prüfung; Chat im UI |
| 3 | Mehrtagestour + Wetter/Regenvariante, Wissenssuche, Auth + gespeicherte Touren, Bilder (Commons + Upload), PWA „Unterwegs" |
| 4 | Restliche Fernwege, Evaluation + Bericht, README, Ethik, Showcase, Präsentation |

Wenn es eng wird, fällt in dieser Reihenfolge weg: Englisch, Parameter-Experimente, Mittel-/Ostweg (nur Westweg), Regenvariante über ORS (dann nur kürzere Etappe), Foto-Upload (nur Commons).

## 13. Dem Builder überlassen

Projektstruktur, Teststrategie (Python-Tests ohne API-Kosten wie in GridLens), genaue DB-Tabellen, Prompt-Texte, Komponentenbibliothek, Feindesign, genaue Größe von Testset und Tourenauswahl.
