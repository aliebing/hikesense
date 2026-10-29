# Hike all about

Chat-zentrierter Wanderplaner für den Schwarzwald: Westweg (West- und Ostvariante, in Etappen) und Tagestouren mit Unterkünften, Fotos von Wikimedia Commons und einer Karte (basemap.de). Die Daten werden einmalig aus offenen Quellen (OSM, Commons) in eine lokale Supabase-Datenbank importiert; die App selbst fragt diese Quellen zur Laufzeit nicht ab.

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

3. API und Web-App starten (`make up`) und auf http://localhost:3000 den Chat öffnen. Der Chat ist lokal ohne Anmeldung nutzbar und auf 10 Nachrichten pro Minute je Client begrenzt.

Beispiel-Fragen:

- „Rundweg 10–14 km um Hinterzarten, unter 400 Hm“
- „Rundweg, unter 200 Hm, über 15 km, Feldberg“ (der Chat fragt nach: Gipfel oder Ort?)
- „Laufrunde 8 km ab Titisee, wenig Asphalt“
- „Wie ist der Westweg markiert?“
- „3 Tage Westweg ab Hausach“ (Mehrtagestouren folgen; der Chat sagt das ehrlich)

Erfüllt keine Tour alle Wünsche, beginnt die Antwort mit „Keine Tour erfüllt alle Wünsche, weil …“ und zeigt Touren mit genau einer verletzten Bedingung. Zahlen stammen immer aus Werkzeugergebnissen, nie aus dem Modell.

`make smoke` spielt genau diese sechs Fragen gegen das echte Modell durch (`data/smoke/prompts.yaml`), schreibt `data/smoke/result-<Datum>.csv` und gibt die Gesamtkosten aus; Exit-Code 1, wenn eine Erwartung nicht erfüllt ist.

Die ausführliche Capstone-README folgt in Plan 4.
