# Evaluation google/gemini-2.5-flash-lite – 2026-11-03

- Modell: `google/gemini-2.5-flash-lite`
- Datum des Laufs: 2026-11-03; festes „heute“ im Chat: 2026-11-02 (Wetter aus data/eval/weather.json, Open-Meteo.com, CC BY 4.0)
- Fälle: 42 / 64 bestanden
- Gesamtkosten: 0,0190 USD

## SMART-Ziele

| Ziel | Ist-Wert | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0,0 % (0 von 95 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen im Text) | erreicht |
| ≤ 2 % nicht belegte Zahlen | 0,5 % (2 von 372 Zahlen) | erreicht |
| 100 % offen benannte Unerfüllbarkeit | 100,0 % (10 von 10 Fällen) | erreicht |
| Recall@5 ≥ 0,8 | 0,30 (3 von 10 Fällen) | nicht erreicht |

Falsche Unerfüllbarkeits-Behauptungen: 0 von 30 erfüllbaren Fällen (Ziel 0); vom Code vorher entfernt: 0

## Gruppen

| Gruppe | bestanden / gesamt |
|---|---|
| erfuellbar | 18 / 18 |
| unerfuellbar | 9 / 10 |
| mehrtag | 3 / 12 |
| aenderung | 0 / 5 |
| wissen | 3 / 10 |
| eingabeschutz | 6 / 6 |
| gruppen_laeufe | 3 / 3 |

## Abgleich mit OSM

82 Touren verglichen (Tourkarten und Mehrtagesplan-Tage; Karte gegen Datenbank gegen gespeicherte OSM-Linie), 0 mit Abweichung > 2 %.

## Nicht bestandene Fälle

- m03-westweg-hinterzarten-regen: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.
- m04-mittelweg-schiltach: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan; kein Plan
- m05-mittelweg-pforzheim-datum: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 2 Tage; kein Plan; kein Plan; kein Plan
- m06-mittelweg-besenfeld: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan; kein Plan
- m07-ostweg-freudenstadt: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan; kein Plan
- m08-ostweg-pforzheim: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 4 Tage; kein Plan; kein Plan
- m09-ostweg-alpirsbach-luecke: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan; kein Plan
- a01-westweg-tag3-kuerzer: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein geänderter Plan; kein geänderter Plan
- a02-mittelweg-tag2-kuerzer: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan zum Vergleichen; kein Plan zum Vergleichen
- a03-ostweg-tag3-laenger: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan zum Vergleichen; kein Plan zum Vergleichen
- a04-ostweg-tag4-laenger: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 4 Tage; kein Plan zum Vergleichen; kein Plan zum Vergleichen
- a05-westweg-tag1-laenger: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 3 Tage; kein Plan zum Vergleichen
- w01-westweg-markierung: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „rote“; Antwort ohne „Raute“
- w02-mittelweg-markierung: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „Balken“
- w03-ostweg-wegzeichen: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „schwarz-rot“
- w04-wutachschlucht-nebenschlucht: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „Gauchach“
- w05-mummelsee-berg: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „Hornisgrinde“
- w06-wetter-gepaeck: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „Regenschutz“
- w07-triberg-fluss: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Quelle; Antwort ohne „Gutach“
- u10-dahn-flach-lang: 2 unbelegte Zahlen
- m11-weinsteig-bad-duerkheim: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Rückfrage; keine Option mit „(Ort)“ zum Antworten
- m12-en-weinsteig-annweiler: Fehler-Ereignis: The planning assistant is not available right now. Please try again later.; kein Plan, erwartet 3 Tage; kein Plan; kein Plan
