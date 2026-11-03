# Evaluation openai/gpt-4o-mini – 2026-11-03

- Modell: `openai/gpt-4o-mini`
- Datum des Laufs: 2026-11-03; festes „heute“ im Chat: 2026-11-02 (Wetter aus data/eval/weather.json, Open-Meteo.com, CC BY 4.0)
- Fälle: 64 / 64 bestanden
- Gesamtkosten: 0,0324 USD

## SMART-Ziele

| Ziel | Ist-Wert | Ergebnis |
|---|---|---|
| 0 % erfundene Touren | 0,0 % (0 von 110 Tour-IDs nicht in der Datenbank, 0 unbelegte Tournamen im Text) | erreicht |
| ≤ 2 % nicht belegte Zahlen | 0,0 % (0 von 690 Zahlen) | erreicht |
| 100 % offen benannte Unerfüllbarkeit | 100,0 % (10 von 10 Fällen) | erreicht |
| Recall@5 ≥ 0,8 | 1,00 (10 von 10 Fällen) | erreicht |

Falsche Unerfüllbarkeits-Behauptungen: 0 von 30 erfüllbaren Fällen (Ziel 0); vom Code vorher entfernt: 0

## Gruppen

| Gruppe | bestanden / gesamt |
|---|---|
| erfuellbar | 18 / 18 |
| unerfuellbar | 10 / 10 |
| mehrtag | 12 / 12 |
| aenderung | 5 / 5 |
| wissen | 10 / 10 |
| eingabeschutz | 6 / 6 |
| gruppen_laeufe | 3 / 3 |

## Abgleich mit OSM

116 Touren verglichen (Tourkarten und Mehrtagesplan-Tage; Karte gegen Datenbank gegen gespeicherte OSM-Linie), 0 mit Abweichung > 2 %.

## Nicht bestandene Fälle

Keine.
