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

Die ausführliche Capstone-README folgt in Plan 4.
