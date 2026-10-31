# Evaluation google/gemini-2.5-flash-lite – 2026-10-31

- Modell: `google/gemini-2.5-flash-lite`
- Datum des Laufs: 2026-10-31; festes „heute“ im Chat: 2026-11-02 (Wetter aus data/eval/weather.json, Open-Meteo.com, CC BY 4.0)
- Fälle: 51 / 52 bestanden
- Gesamtkosten: 0,0216 USD

## SMART-Ziele

| Ziel | Ist-Wert | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0,0 % (0 von 74 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen im Text) | erreicht |
| ≤ 2 % nicht belegte Zahlen | 0,0 % (0 von 437 Zahlen) | erreicht |
| 100 % offen benannte Unerfüllbarkeit | 100,0 % (8 von 8 Fällen) | erreicht |
| Recall@5 ≥ 0,8 | 1,00 (10 von 10 Fällen) | erreicht |

## Gruppen

| Gruppe | bestanden / gesamt |
|---|---|
| erfuellbar | 12 / 12 |
| unerfuellbar | 8 / 8 |
| mehrtag | 9 / 9 |
| aenderung | 5 / 5 |
| wissen | 9 / 10 |
| eingabeschutz | 5 / 5 |
| gruppen_laeufe | 3 / 3 |

## Abgleich mit OSM

82 Touren verglichen (Tourkarten und Mehrtagesplan-Tage; Karte gegen Datenbank gegen gespeicherte OSM-Linie), 0 mit Abweichung > 2 %.

## Nicht bestandene Fälle

- w08-nationalpark-gruendung: Antwort ohne „2014“
