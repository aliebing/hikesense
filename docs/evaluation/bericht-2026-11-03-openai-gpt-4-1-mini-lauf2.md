# Evaluation openai/gpt-4.1-mini – 2026-11-03

- Modell: `openai/gpt-4.1-mini`
- Datum des Laufs: 2026-11-03; festes „heute“ im Chat: 2026-11-02 (Wetter aus data/eval/weather.json, Open-Meteo.com, CC BY 4.0)
- Fälle: 61 / 64 bestanden
- Gesamtkosten: 0,0643 USD

## SMART-Ziele

| Ziel | Ist-Wert | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0,0 % (0 von 110 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen im Text) | erreicht |
| ≤ 2 % nicht belegte Zahlen | 0,0 % (0 von 676 Zahlen) | erreicht |
| 100 % offen benannte Unerfüllbarkeit | 80,0 % (8 von 10 Fällen) | nicht erreicht |
| Recall@5 ≥ 0,8 | 1,00 (10 von 10 Fällen) | erreicht |

Falsche Unerfüllbarkeits-Behauptungen: 0 von 30 erfüllbaren Fällen (Ziel 0); vom Code vorher entfernt: 0

## Gruppen

| Gruppe | bestanden / gesamt |
|---|---|
| erfuellbar | 18 / 18 |
| unerfuellbar | 8 / 10 |
| mehrtag | 11 / 12 |
| aenderung | 5 / 5 |
| wissen | 10 / 10 |
| eingabeschutz | 6 / 6 |
| gruppen_laeufe | 3 / 3 |

## Abgleich mit OSM

114 Touren verglichen (Tourkarten und Mehrtagesplan-Tage; Karte gegen Datenbank gegen gespeicherte OSM-Linie), 0 mit Abweichung > 2 %.

## Nicht bestandene Fälle

- u09-en-ueberlingen-30km: kein fallback_reason; kein fallback_reason; Antwort beginnt nicht mit „No tour meets all your wishes“
- u10-dahn-flach-lang: kein fallback_reason; kein fallback_reason; Antwort beginnt nicht mit „Keine Tour erfüllt alle Wünsche“
- m11-weinsteig-bad-duerkheim: Rückfrage ohne Option mit „Ort“: []; Rückfrage ohne Option mit „Gemeinde“: []; keine Option mit „(Ort)“ zum Antworten
