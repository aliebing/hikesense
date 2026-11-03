# Modell- und Temperaturvergleich

## Stand 2026-11-03: 64 Fälle, Wiederholungen, zweites Modell

Testsatz mit 64 Fällen (52 + 12 neue, nicht an gpt-4o-mini entwickelt), gleiche Erwartungen,
gespeicherte Wetterdaten. Jede Konfiguration lief mindestens zweimal.

| Kennzahl | gpt-4o-mini (3 Läufe + 1 nach dem Grounding-Fix) | gpt-4.1-mini vor dem Fix (2 Läufe) | gpt-4.1-mini nach dem Fix (2 Läufe) | gemini-2.5-flash-lite (2 Läufe, Anbieterstörung) |
|---|---|---|---|---|
| Fälle bestanden | 64, 64, 64 / 64; nach Fix 64 / 64 | 59, 58 / 64 | 60, 61 / 64 | 42, 55 / 64 (davon 21 bzw. 9 „nicht erreichbar“) |
| erfundene Touren | 0 von 110 | 0 von 108–109 | 0 von 108–110 | 0 von 95–99 |
| nicht belegte Zahlen | 0,0 % | 2,7 % / 4,5 % | 0,6 % / 0,0 % | 0,5 % / 0,0 % |
| Unerfüllbarkeit offen benannt | 10 / 10 | 9 / 10, 10 / 10 | 9 / 10, 8 / 10 | 10 / 10, 8 / 10 |
| Recall@5 | 1,00 | 1,00 | 1,00 | 0,30 / 1,00 (Ausfälle) |
| falsche Unerfüllbarkeits-Behauptungen | 0 von 30 | 0 von 30 | 0 von 30 | 0 von 30 |
| OSM-Abweichungen > 2 % | 0 von 116 | 0 | 0 | 0 |
| Kosten je Lauf | 0,032–0,035 USD | 0,064–0,072 USD | 0,063–0,064 USD | – (Ausfälle) |

Berichte: gpt-4o-mini [Lauf 1](bericht-2026-11-03-openai-gpt-4o-mini-lauf1.md),
[2](bericht-2026-11-03-openai-gpt-4o-mini-lauf2.md), [3](bericht-2026-11-03-openai-gpt-4o-mini-lauf3.md),
[nach Fix](bericht-2026-11-03-openai-gpt-4o-mini-nach-fix.md); gpt-4.1-mini
[vor Fix 1](bericht-2026-11-03-openai-gpt-4-1-mini-vor-fix-lauf1.md), [vor Fix 2](bericht-2026-11-03-openai-gpt-4-1-mini-vor-fix-lauf2.md),
[Lauf 1](bericht-2026-11-03-openai-gpt-4-1-mini-lauf1.md), [Lauf 2](bericht-2026-11-03-openai-gpt-4-1-mini-lauf2.md);
Gemini [Lauf 1](bericht-2026-11-03-google-gemini-2-5-flash-lite-lauf1.md),
[Lauf 2](bericht-2026-11-03-google-gemini-2-5-flash-lite-lauf2.md).

**Gemini war am 2026-11-03 nicht verlässlich erreichbar.** OpenRouter meldete HTTP 429 („temporarily
rate-limited upstream“, gemeinsamer Pool von Google AI Studio), auch zwischen den Läufen. Die App
zeigte dann „Der Planungs-Assistent ist gerade nicht erreichbar“ und erfand nichts. Von den Fällen,
die Gemini beantwortete, bestanden 42 von 43 und 55 von 55; der eine echte Fehler war u10 mit zwei
Zahlen, die das Grounding als unbelegt markierte. Zwei frühere Gemini-Läufe desselben Abends
(vor dem Sprach-Fix der Kennzahlen, ebenfalls mit 429) sind nicht eingecheckt.

**Zweites Modell gpt-4.1-mini.** Weil Gemini ausfiel und das Konto andere Anbieter per Guardrail
sperrt (Mistral, Llama, DeepSeek, Qwen; siehe unten), lief zusätzlich `openai/gpt-4.1-mini` – ein
neueres, rund doppelt so teures Modell desselben Anbieters. Es fand zwei echte Schwächen:

- **Grounding-Fehlalarm, behoben** (Commit `c74ae21`). gpt-4.1-mini schreibt „902 m Anstieg“ statt
  „902 Hm“. Das Grounding las „m“ im Deutschen immer als Länge und ersetzte den richtigen Wert durch
  „?“ (6 von 6 Zahlen je Mehrtagesplan, 2,7–4,5 % unbelegt). Im Englischen galt „540 m of ascent“
  schon als Anstieg. Jetzt zählen Meter neben Anstieg/Abstieg/Aufstieg auch im Deutschen als
  Höhenmeter, „86 m vom Weg“ bleibt eine Länge. Danach 0,6 % und 0,0 %; gpt-4o-mini weiter 64/64.
- **Ortsangabe falsch herausgelöst, nicht behoben.** gpt-4.1-mini übernimmt „near Überlingen“ (u09)
  bzw. „Pfälzer Weinsteig ab Bad Dürkheim“ (m11) als Ortsnamen und liest „über 25 km“ teils als
  „≈ 25 km“ (u10). Der Code erfindet daraufhin nichts: Er fragt nach dem Ort bzw. zeigt das
  Verständnis-Echo („Länge 21,25–28,75 km (≈ 25 km)“). Ein Fix (Präpositionen vor dem Ort
  abschneiden) wäre an diesem Modell entwickelt; er ist als nächster Schritt notiert.

Folgerung: gpt-4o-mini bleibt Standardmodell – günstiger und auf diesem Testsatz fehlerfrei. Das
stärkere Modell ist nicht besser, weil die Qualität hier an der Code-Prüfung hängt, nicht an der
Formulierung; seine Abweichungen fängt der Code ab (Rückfrage, „?“), statt sie durchzulassen.

## Stand 2026-10-31

Derselbe Testsatz (52 Fälle, `data/eval/cases.yaml`), dieselben Erwartungen, dieselben Prompts, gleiche
gespeicherte Wetterdaten, Lauf am 2026-10-31.

**Stand:** Die Spalten T = 0, T = 0,7 und Gemini liefen *vor* dem Fix der falschen
Unerfüllbarkeits-Behauptung (Commit `023ba23`, siehe [README.md](README.md#befunde)): mit dem
alten Antwort-Prompt und ohne die Erwartung `no_unsat_claim`. Die Spalte „Standard“ ist der
Basislauf *nach* dem Fix. Die Vergleichsläufe wurden nicht wiederholt; ihre Zeile „falsche
Unerfüllbarkeits-Behauptungen“ ist daher nicht gemessen („–“). Nichts wurde für ein Modell angepasst. Die
Kennzahlen sind wie in [README.md](README.md) definiert. Aufruf: `hikesense eval --model M
--temperature T`; ohne `--temperature` bleibt es bei den festen Werten des Gateways (0,0 für
Verständnis und Werkzeug-Runden, 0,3 für Antworttexte).

| Kennzahl | gpt-4o-mini, Standard (0 / 0,3) | gpt-4o-mini, T = 0 | gpt-4o-mini, T = 0,7 | gemini-2.5-flash-lite (Standard) |
|---|---|---|---|---|
| Fälle bestanden | 52 / 52 | 52 / 52 | 52 / 52 | 51 / 52 |
| falsche Unerfüllbarkeits-Behauptungen | 0 von 21 | – | – | – |
| erfundene Touren (nicht in der DB) | 0 von 74 | 0 von 74 | 0 von 74 | 0 von 74 |
| unbelegte Tournamen im Text | 0 | 0 | 0 | 0 |
| nicht belegte Zahlen | 0,0 % (0 von 518) | 0,0 % (0 von 521) | 0,0 % (0 von 522) | 0,0 % (0 von 437) |
| Unerfüllbarkeit offen benannt | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| Recall@5 | 1,00 (10 / 10) | 1,00 (10 / 10) | 1,00 (10 / 10) | 1,00 (10 / 10) |
| OSM-Abweichungen > 2 % | 0 von 82 | 0 von 82 | 0 von 82 | 0 von 82 |
| Kosten des Laufs | 0,0282 USD | 0,0263 USD | 0,0263 USD | 0,0216 USD |

Berichte: [Standard](bericht-2026-10-31-openai-gpt-4o-mini.md),
[T = 0](bericht-2026-10-31-openai-gpt-4o-mini-t0.md),
[T = 0,7](bericht-2026-10-31-openai-gpt-4o-mini-t0-7.md),
[Gemini](bericht-2026-10-31-google-gemini-2-5-flash-lite.md). Die Spalte „Standard“ ist der
eingecheckte Basislauf (nach dem Fix); er hat keine Temperatur im Dateinamen.

## Wahl des zweiten Modells

`google/gemini-2.5-flash-lite` (0,10 USD je Mio. Eingabe-Token, 0,40 USD je Mio. Ausgabe-Token
laut OpenRouter; gpt-4o-mini: 0,15 / 0,60). Preise laut OpenRouter-Modellseite, abgerufen 2026-10-31. Gewählt, weil es günstiger ist als der Basislauf,
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
unterscheiden sich nur in der Anzahl der Zahlen im Text (518 bis 522; der Basislauf vor dem
Fix hatte 530). Das passt zur Bauweise:
Touren, Längen und Höhenmeter kommen aus der Datenbank und werden vom Code geprüft, das Modell
formuliert nur. Gemini 2.5 Flash Lite ist etwa 18 % billiger als der Basislauf vor dem Fix (0,0264 USD) und besteht 51 von 52 Fällen; der
eine Fehler (w08, Gründung des Nationalparks) ist ein Wissensfall, in dem die Antwort die
erwartete Jahreszahl „2014“ nicht nennt. Ein Verstoß gegen eines der vier Ziele war es nicht.
Ein einzelner Lauf mit 51 von 52 Fällen zeigt nur, dass Gemini mit diesem Agenten grundsätzlich
funktioniert. Ob es als Rückfalloption taugt, müssten wiederholte Läufe zeigen; für einen Wechsel
des Standardmodells spricht er nicht (Preisunterschied rund 0,005 USD je Lauf).

Grenzen: Je Konfiguration gibt es genau einen Lauf, ohne Wiederholung und ohne
Konfidenzintervall. Ein Fall mehr oder weniger (hier w08) liegt im Rauschen eines einzelnen
Laufs und ist kein belegter Qualitätsunterschied. Der Testsatz hat 52 Fälle und ist mit gpt-4o-mini
entwickelt worden, was dieses Modell begünstigen kann. Nur ein Modell ohne Guardrail-Sperre
wurde als zweites verglichen; kein größeres Modell.
