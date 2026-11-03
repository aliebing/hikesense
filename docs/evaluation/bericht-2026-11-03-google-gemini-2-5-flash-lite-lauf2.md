# Evaluation google/gemini-2.5-flash-lite – 2026-11-03

- Modell: `google/gemini-2.5-flash-lite`
- Datum des Laufs: 2026-11-03; festes „heute“ im Chat: 2026-11-02 (Wetter aus data/eval/weather.json, Open-Meteo.com, CC BY 4.0)
- Fälle: 55 / 64 bestanden
- Gesamtkosten: 0,0237 USD

## SMART-Ziele

| Ziel | Ist-Wert | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0,0 % (0 von 99 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen im Text) | erreicht |
| ≤ 2 % nicht belegte Zahlen | 0,0 % (0 von 497 Zahlen) | erreicht |
| 100 % offen benannte Unerfüllbarkeit | 80,0 % (8 von 10 Fällen) | nicht erreicht |
| Recall@5 ≥ 0,8 | 1,00 (10 von 10 Fällen) | erreicht |

Falsche Unerfüllbarkeits-Behauptungen: 0 von 30 erfüllbaren Fällen (Ziel 0); vom Code vorher entfernt: 0

## Gruppen

| Gruppe | bestanden / gesamt |
|---|---|
| erfuellbar | 14 / 18 |
| unerfuellbar | 8 / 10 |
| mehrtag | 9 / 12 |
| aenderung | 5 / 5 |
| wissen | 10 / 10 |
| eingabeschutz | 6 / 6 |
| gruppen_laeufe | 3 / 3 |

## Abgleich mit OSM

104 Touren verglichen (Tourkarten und Mehrtagesplan-Tage; Karte gegen Datenbank gegen gespeicherte OSM-Linie), 0 mit Abweichung > 2 %.

## Nicht bestandene Fälle

- e01-rundweg-hinterzarten: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.
- e02-rundwanderung-freudenstadt: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.
- e17-en-meersburg: Fehler-Ereignis: The planning assistant is not available right now. Please try again later.
- e18-en-hinterzarten: Fehler-Ereignis: The planning assistant is not available right now. Please try again later.; 0 Treffer, erwartet mindestens 1; nicht alle Bedingungen erfüllt: keine Treffer
- u09-en-ueberlingen-30km: Fehler-Ereignis: The planning assistant is not available right now. Please try again later.; kein fallback_reason; kein fallback_reason; Antwort beginnt nicht mit „No tour meets all your wishes“
- u10-dahn-flach-lang: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein fallback_reason; kein fallback_reason; Antwort beginnt nicht mit „Keine Tour erfüllt alle Wünsche“
- m10-seegang-wallhausen: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; kein Plan, erwartet 2 Tage; kein Plan; kein Plan
- m11-weinsteig-bad-duerkheim: Fehler-Ereignis: Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.; keine Rückfrage; keine Option mit „(Ort)“ zum Antworten
- m12-en-weinsteig-annweiler: Fehler-Ereignis: The planning assistant is not available right now. Please try again later.; kein Plan, erwartet 3 Tage; kein Plan; kein Plan
