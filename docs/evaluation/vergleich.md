# Modell- und Temperaturvergleich

Derselbe Testsatz (52 Fälle, `data/eval/cases.yaml`), dieselben Erwartungen, dieselben Prompts, gleiche
gespeicherte Wetterdaten, Lauf am 2026-10-31. Nichts wurde für ein Modell angepasst. Die
Kennzahlen sind wie in [README.md](README.md) definiert. Aufruf: `hikeall eval --model M
--temperature T`; ohne `--temperature` bleibt es bei den festen Werten des Gateways (0,0 für
Verständnis und Werkzeug-Runden, 0,3 für Antworttexte).

| Kennzahl | gpt-4o-mini, Standard (0 / 0,3) | gpt-4o-mini, T = 0 | gpt-4o-mini, T = 0,7 | gemini-2.5-flash-lite (Standard) |
|---|---|---|---|---|
| Fälle bestanden | 52 / 52 | 52 / 52 | 52 / 52 | 51 / 52 |
| erfundene Touren (nicht in der DB) | 0 von 74 | 0 von 74 | 0 von 74 | 0 von 74 |
| unbelegte Tournamen im Text | 0 | 0 | 0 | 0 |
| nicht belegte Zahlen | 0,0 % (0 von 530) | 0,0 % (0 von 521) | 0,0 % (0 von 522) | 0,0 % (0 von 437) |
| Unerfüllbarkeit offen benannt | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| Recall@5 | 1,00 (10 / 10) | 1,00 (10 / 10) | 1,00 (10 / 10) | 1,00 (10 / 10) |
| OSM-Abweichungen > 2 % | 0 von 82 | 0 von 82 | 0 von 82 | 0 von 82 |
| Kosten des Laufs | 0,0264 USD | 0,0263 USD | 0,0263 USD | 0,0216 USD |

Berichte: [Standard](bericht-2026-10-31-openai-gpt-4o-mini.md),
[T = 0](bericht-2026-10-31-openai-gpt-4o-mini-t0.md),
[T = 0,7](bericht-2026-10-31-openai-gpt-4o-mini-t0-7.md),
[Gemini](bericht-2026-10-31-google-gemini-2-5-flash-lite.md). Die Spalte „Standard“ ist der
eingecheckte Basislauf; er hat keine Temperatur im Dateinamen.

## Wahl des zweiten Modells

`google/gemini-2.5-flash-lite` (0,10 USD je Mio. Eingabe-Token, 0,40 USD je Mio. Ausgabe-Token
laut OpenRouter; gpt-4o-mini: 0,15 / 0,60). Gewählt, weil es günstiger ist als der Basislauf,
von einem anderen Anbieter kommt und laut OpenRouter Werkzeugaufrufe und strukturierte Ausgabe
unterstützt; beides braucht der Agent. Vorher versucht und nicht nutzbar: `mistralai/mistral-small-3.2-24b-instruct`
(erster Lauf: 4 von 52, 0 USD). Ursache war kein Modellfehler: Das OpenRouter-Konto der Entwicklung
blockiert dieses Modell über eine Guardrail (HTTP 404, „Model blocked by guardrail“), jeder
Modellaufruf scheiterte. Das gleiche galt für `meta-llama/llama-3.3-70b-instruct`,
`openai/gpt-4.1-nano` und `mistralai/mistral-small-2603`. Der Mistral-Lauf wurde nicht
eingecheckt, weil er nichts über das Modell aussagt; die Guardrail wurde nicht verändert.

## Auswertung

Alle vier SMART-Ziele werden in allen Läufen erreicht. Die Temperatur ändert bei gpt-4o-mini
nichts am Ergebnis: T = 0, Standard und T = 0,7 bestehen alle 52 Fälle, die Zahlen
unterscheiden sich nur in der Anzahl der Zahlen im Text (521 bis 530). Das passt zur Bauweise:
Touren, Längen und Höhenmeter kommen aus der Datenbank und werden vom Code geprüft, das Modell
formuliert nur. Gemini 2.5 Flash Lite ist etwa 18 % billiger und besteht 51 von 52 Fällen; der
eine Fehler (w08, Gründung des Nationalparks) ist ein Wissensfall, in dem die Antwort die
erwartete Jahreszahl „2014“ nicht nennt. Ein Verstoß gegen eines der vier Ziele war es nicht.
Für den Betrieb spricht das für Gemini als Rückfalloption, solange der Preisunterschied (rund
0,005 USD je Lauf) gering bleibt, aber nicht für einen Wechsel des Standardmodells.

Grenzen: Je Konfiguration gibt es genau einen Lauf, ohne Wiederholung und ohne
Konfidenzintervall. Ein Fall mehr oder weniger (hier w08) liegt im Rauschen eines einzelnen
Laufs und ist kein belegter Qualitätsunterschied. Der Testsatz hat 52 Fälle und ist mit gpt-4o-mini
entwickelt worden, was dieses Modell begünstigen kann. Nur ein Modell ohne Guardrail-Sperre
wurde als zweites verglichen; kein größeres Modell.
