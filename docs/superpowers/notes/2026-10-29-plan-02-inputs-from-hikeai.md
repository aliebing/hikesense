# Eingaben für Plan 2 (und 3): was aus HikeAI übernommen werden soll

Stand: 2026-10-29 · Quelle: Vergleich HikeAI (`~/projects/HikeAi2`, README) mit Hike all about · vom Nutzer bestätigt

Die Kritik an HikeAI betraf stilles Weglassen von Bedingungen, eine reine Ergebnisliste und fehlende Herkunft der Daten – nicht die folgenden Funktionen. Sie sollen beim Schreiben von Plan 2 (Agent + Chat) bzw. Plan 3 berücksichtigt werden.

## 1. Kontrolliertes Tag-Vokabular + Grounding (Plan 2)

- HikeAI: ~500 Tags aus OSM (Merkmale, Belag, Orte, benannte Wege); das Modell darf nur existierende Tag-IDs nennen.
- Für Hike all about: Vokabular aus den importierten Wegen/Tagestouren ableiten; `HikeRequest` (Spec §7, „Wünsche verstehen") referenziert nur Tag-IDs aus diesem Vokabular.
- Passt direkt zum Anti-Ziel „KI erfindet Routen oder Zahlen" und zur Grounding-Prüfung (Spec §8).

## 2. Vorlieben mit bevorzugen/vermeiden (Plan 2)

- HikeAI: bis zu 10 Vorlieben, je *bevorzugen* oder *vermeiden*, Wichtigkeit 1–5; feste Bedingungen filtern, Vorlieben ordnen nur; Punktzahl deterministisch, die KI erklärt nur.
- Für Hike all about: ergänzt „feste Bedingungen" und „Wünsche" der Spec. Feste Bedingungen bleiben hart (nie still lockern, Ausweichen mit genau einer verletzten Bedingung); Vorlieben bestimmen nur die Reihenfolge.
- Erklärung je Vorschlag: erfüllte / fehlende / vermiedene Vorlieben.

## 3. Belag- und Wegtyp-Anteile beim Import (kleiner Nachtrag zu Plan 1, Tasks 5/6)

- HikeAI: Anteile je Route aus den Tags der Mitglieds-Wege (`ingest/routes.py`: `classify_surface`, `classify_way_type`, `compute_shares`).
- Für Hike all about: beim Import von Westweg-Etappen und Tagestouren mitberechnen (die OSM-Wege werden ohnehin geladen), als Spalte(n) in `trails`/`stages`. Ermöglicht Bedingungen wie „wenig Asphalt".

## 4. Prompt-Injection-Schutz + Kosten je Aufruf (Plan 2, Material für Plan 4)

- HikeAI: Eingabeprüfung Deutsch/Englisch, Ausgabeprüfung auf wiederholten System-Prompt; Tokenverbrauch und von OpenRouter abgerechnete Kosten je Aufruf (nie aus einer Preistabelle geschätzt), im Admin-Log.
- Für Hike all about: beides im Agent-Backend; Kosten und Injection-Schutz fließen in Evaluation und Ethik-Abschnitt (Plan 4).

## Bewusst nicht übernommen

- Mehrere Regionen (Nutzerentscheidung: nur Schwarzwald).
- Nutzerbewertungen (Spec: keine Community-Funktionen).
- 16-Tage-Wetter-Tagesfinder: optional für Plan 3, falls Zeit; Spec sieht 3-Tage-Wetter + Regenvariante vor.

## Nachtrag 2026-10-29 (vom Nutzer entschieden)

### 5. Joggen als Aktivitätsart (Plan 2)

- Aktivität „Laufen“ neben „Wandern“: feste Bedingungen und Vorlieben wie Runde, Distanz (z. B. 5–12 km), wenig Steigung, gut laufbarer Belag (nutzt die Belag-/Wegtyp-Anteile aus Punkt 3), Start in der Nähe von X.
- Nur auf vorhandenen importierten Runden/Tagestouren – keine selbst erzeugten Laufrunden (Anti-Ziel „KI erfindet Routen“).

### 6. Gruppenliste (Plan 3)

- Von Hand gepflegte Liste von Wander-/Laufgruppen (z. B. Schwarzwaldverein-Ortsgruppen, Lauftreffs, DAV-Sektionen): Name, Ort, Link, Prüfdatum; App zeigt „Gruppen in der Nähe, Stand: …“ und verlinkt, keine Termine, keine Einzelpersonen.
- Ändert die Spec (bisher „keine Community-Funktionen“): nur verlinkte Liste, keine Community-Funktionen in der App selbst.
- Live-Community/aktuelle Treffen → „Next steps“ in der Präsentation.
### 7. Offizielle Läufe in der Nähe (Plan 3)

- Entscheidung: keine selbst gepflegte Liste und keine gespeicherte Lauf-Datenbank. Quellen-Recherche: `2026-10-29-laufveranstaltungen-datenquellen.md`.
- A (Hauptweg): Agent-Werkzeug sucht bei Anfrage live im Web (z. B. „Halbmarathon im Juni bei Freiburg“), liest einzelne Veranstalter-/Anmeldeseiten und stellt Läufe vor: Name, Datum, Ort, Distanzen, Anmeldelink, Anmeldeschluss, Startgebühr – jede Angabe mit Quellenlink; fehlt etwas auf der Seite → „nicht angegeben“, nie schätzen. Nichts wird gespeichert.
- Kein massenhaftes Abrufen von Portalen, deren Bedingungen Weiterverwendung verbieten (laufen.de, marathon.de, DUV, LADV, HDsports).
- B (Rückfall, wenn die Suche nichts findet): Links auf Laufkalender (z. B. BLV, laufen.de), möglichst nach Region/Monat gefiltert.
- Stoff für Plan 4: Quellenpflicht und Kosten der Live-Suche in Evaluation und Ethik-Abschnitt.
