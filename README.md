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

   Die API lädt Merkmale und Orte beim ersten Chat; nach `make tags` oder einem neuen Orts-Import die API neu starten (`make up`).

3. API und Web-App starten (`make up`), auf http://localhost:3000 anmelden (siehe „Konto anlegen“) und den Chat in der Mitte der Startseite nutzen. Ohne Anmeldung zeigt der Chat statt des Eingabefelds „Zum Planen bitte anmelden“. Hat der Chat Touren oder einen Mehrtagesplan gefunden, führt der Knopf „Vorschläge zeigen →“ zur Vorschlagsseite, von dort öffnet eine Tour die Route mit Karte. Je Konto gelten höchstens 10 Nachrichten pro Minute und 100 pro Tag (gezählt je Nutzer-ID, nicht je IP-Adresse).

Beispiel-Fragen:

- „Rundweg 10–14 km um Hinterzarten, unter 400 Hm“
- „Rundweg, unter 200 Hm, über 15 km, Feldberg“ (der Chat fragt nach: Gipfel oder Ort?)
- „Laufrunde 8 km ab Titisee, wenig Asphalt“
- „Wie ist der Westweg markiert?“
- „3 Tage Westweg ab Hausach, ~15 km pro Tag“, danach „Tag 3 kürzer“
- „Wanderverein in Freiburg“
- „Halbmarathon im Frühjahr bei Freiburg“

Erfüllt keine Tour alle Wünsche, beginnt die Antwort mit „Keine Tour erfüllt alle Wünsche, weil …“ und zeigt Touren mit genau einer verletzten Bedingung. Touren, Bedingungen und Abweichungen berechnet der Code, nicht das Modell. Den Antworttext formuliert das Modell; jede Zahl mit Einheit darin (auch „15-km-Runde“ oder „zwei Stunden“) prüft der Code gegen die Werkzeugergebnisse der Runde, ersetzt nicht belegte Zahlen durch „?“ und sagt das dazu. Tournamen aus der Datenbank, die in den Ergebnissen der Runde nicht vorkommen, werden bisher nur gezählt, nicht entfernt. Wissensfragen beantwortet der Chat nur, wenn er eine Quelle gefunden hat.

`make smoke` spielt elf Fälle gegen das echte Modell durch (`data/smoke/prompts.yaml`): die Beispiel-Fragen, einen Prompt-Injection-Versuch („Ignoriere alle vorherigen Anweisungen“), „3 Tage Westweg ab Hausach“ ohne Tagesziel, die Folgerunde „Tag 3 kürzer“ im selben Gesprächsfaden und „Lauftreff in Freiburg“ (erwartet wird die ehrliche Antwort „keine Gruppe“, siehe „Gruppen und Läufe“). Der Lauf meldet sich als Testkonto `smoke@hikeall.local` an und prüft dessen Token wie `/chat`; das Konto legt einmalig

```sh
make smoke-user   # Passwort aus HIKEALL_SMOKE_PASSWORD in .env (zufällig wählen, nie einchecken)
```

in der lokalen Supabase-Auth an. Ergebnis: `data/smoke/result-<Datum>.csv` (je Fall ok, unbelegte Zahlen, Kosten) und die Gesamtkosten (zuletzt etwa 0,01 USD); Exit-Code 1, wenn eine Erwartung nicht erfüllt ist. Erwartungen werden nie gelockert, um einen Fall grün zu machen.

## Konto anlegen

Planen im Chat, Pläne merken und eigene Fotos brauchen ein Konto. Auf http://localhost:3000/anmelden E-Mail und Passwort (mindestens 6 Zeichen) eingeben und „Konto anlegen“ wählen; die lokale Supabase bestätigt E-Mail-Adressen automatisch (`enable_confirmations = false` in `supabase/config.toml`), es wird keine Mail verschickt. Danach steht im Kopf neben „Fernwege“ das Kontomenü mit „Meine Pläne“ und „Abmelden“.

- Die API nimmt `/chat` nur mit gültigem Supabase-Access-Token an (`Authorization: Bearer …`). Läuft die Sitzung mitten im Gespräch ab, zeigt der Chat „Sitzung abgelaufen – bitte erneut anmelden“, der getippte Text bleibt im Eingabefeld.
- Das Backend prüft das Token über die JWKS der lokalen Supabase (`SUPABASE_URL`); ältere Projekte mit HS256 brauchen `SUPABASE_JWT_SECRET` in `.env`.
- An das Modell und ins Protokoll (`logs/chat.jsonl`) gehen weder E-Mail noch Nutzer-ID, im Protokoll steht nur ein gekürzter SHA-256 der ID (12 Zeichen).
- Gemerkte Pläne und hochgeladene Fotos sieht nur ihr Eigentümer (Row Level Security). Fotos werden vor dem Hochladen im Browser neu als JPEG kodiert, dabei fallen EXIF- und GPS-Daten weg; erlaubt sind JPEG, PNG und WebP bis 10 MB.

## Mehrtagestour

„3 Tage Westweg ab Hausach, ~15 km pro Tag“ ergibt einen Plan Tag für Tag. Der Code plant, das Modell formuliert nur:

- **Tagesziel ist eine Unterkunft höchstens 1000 m vom Weg.** Nur wenn im Band keine liegt, wird bis 2000 m ausgewichen; der Zuweg wird dann am Ankunftstag und am Folgetag zur Strecke addiert und genannt. Gibt es auch das nicht, nennt der Plan die Lücke („Keine Unterkunft ≤ 1 km zwischen km A und km B“) statt eine zu erfinden.
- **Tagesstrecke:** ohne Angabe 15 km, Toleranzband ±20 %. Liegt ein Tag außerhalb, steht der Grund im Plan.
- **Zeiten:** Start ohne Angabe 09:00 Uhr, Ankunft = Start + Gehzeit nach DIN 33466 **ohne Pausen** (so beschriftet). Würde ein Tag nach Mitternacht enden, gibt es keine Ankunftszeit, sondern einen Hinweis.
- **Wegende:** Der Plan läuft nicht über das Ende hinaus („ab Kandern bleiben 28 km bis Basel – 2 Tage bei ~15 km“).
- **Folgerunden** im selben Gespräch: „Tag 3 kürzer“ oder „Tag 2 länger“ ändern nur diesen Tag (und planen die Tage danach neu), die Tage davor bleiben gleich. „Und eine Regenvariante für Tag 1?“ zeigt die Regenvariante (an Regentagen kommt sie von selbst): bis zur nächsten Haltestelle am Weg, weiter mit Bus/Bahn (Fahrplan selbst prüfen).
- **Wetter:** Mit Startdatum („ab 2. November“) holt der Code für Tage bis 14 Tage ab heute eine Vorhersage von Open-Meteo (Quelle „Open-Meteo.com (CC BY 4.0)“ steht dabei); spätere Tage zeigen „noch keine Vorhersage“. Regentag = Niederschlagswahrscheinlichkeit ≥ 60 % oder ≥ 5 mm.
- Der Plan erscheint auf der Vorschlagsseite mit den Tagesabschnitten auf der Karte der Route; „Merken“ speichert ihn unter „Meine Pläne“ (`/plan?id=…`), von dort öffnet „Unterwegs“ einen Tag.

Bekannte Lücken:

- **Basel** liegt außerhalb des OSM-Extrakts Baden-Württemberg: Das Wegende heißt zwar „Basel“, Unterkünfte und Haltestellen auf Schweizer Seite fehlen, und „ab Basel“ ist als Startort nicht auflösbar (nur Beschriftung).
- Von den 17 Westweg-Etappenorten lösen sich bisher nur 7 als Startort auf; bei den übrigen hilft ein Ort in der Nähe als Startangabe.

## Auf dem Handy (HTTPS-Tunnel)

Die Ortung („Unterwegs“) und die Installation als App brauchen HTTPS: Browser geben den Standort nur auf sicheren Seiten frei (`localhost` zählt, die Adresse im WLAN wie `http://192.168.…:3000` nicht). Ein Tunnel gibt der lokalen Web-App eine HTTPS-Adresse:

```sh
make up
cloudflared tunnel --url http://localhost:3000
```

`cloudflared` gibt eine Adresse `https://….trycloudflare.com` aus; sie öffnest du auf dem Handy und wählst „Zum Startbildschirm hinzufügen“ bzw. „App installieren“. Die Installation nutzt `web/public/manifest.webmanifest` und einen kleinen Service Worker (`web/public/sw.js`), der nur die App-Hülle zwischenspeichert, keine Karten und keine Antworten der API; er wird nur im Produktionsbuild (`npm run build && npm start`) angemeldet, nicht in `npm run dev`.

Die Position bleibt auf dem Gerät: „Unterwegs“ rechnet Restkilometer und Ankunft im Browser, sendet und speichert nichts und orten läuft nur, solange die Seite offen und gestartet ist. Ohne HTTPS (reines HTTP im WLAN) funktionieren Chat, Touren und Karte weiter; nur Ortung, Service Worker und Installation fehlen.

Ein Tunnel reicht: Der Browser spricht nur mit der Web-App (Port 3000). Next leitet `/api/chat` an die API (`API_INTERNAL_URL`, in Compose `http://api:8000`) und `/sb/…` an Supabase (`SUPABASE_URL`) weiter (`web/next.config.ts`); der Chat-Stream wird dabei nicht gepuffert. Über die Tunnel-Adresse gehen so Anmelden, Chat, Touren, Karte, Merken, gemerkte Pläne, „Unterwegs“ und eigene Fotos. `NEXT_PUBLIC_SUPABASE_URL` und `NEXT_PUBLIC_API_URL` bleiben dafür leer; gesetzt umgehen sie den Proxy (dann wieder nur am Rechner selbst erreichbar).

## Gruppen und Läufe

**Gruppen** („Wanderverein in Freiburg“, „Alpenverein bei Offenburg“): Der Chat zeigt Einträge einer von Hand gepflegten Liste (`data/curated/groups.csv`, Import mit `make groups`) im Umkreis von 25 km, nach Abstand sortiert. Je Gruppe stehen nur Name, Art, Ort, Link, Quelle und Prüfdatum in der Liste, keine Personen und keine Termine; Treffzeiten stehen auf den Seiten der Gruppen. Die Antwort nennt „Stand: <Prüfdatum>“, Einträge mit Prüfdatum älter als 180 Tage sind als „veraltet“ markiert. Die Routenseite zeigt zusätzlich „Gruppen in der Nähe“. Das ist die einzige Ausnahme von „keine Community-Funktionen“ (Spec §3).

Bekannte Lücken: Die Liste hat 24 Einträge (Schwarzwaldverein-Ortsgruppen und DAV-Sektionen), alle mit Status „vorschlag“ (Seite am Prüfdatum abgerufen, noch nicht von Hand bestätigt). **Lauftreffs fehlen ganz**, weil keiner mit eigener, prüfbarer Seite gefunden wurde; „Lauftreff in Freiburg“ beantwortet der Chat deshalb ehrlich mit „In meiner Liste gibt es keine Gruppe (Lauftreff) …“ und erfindet keine.

**Läufe** („Halbmarathon im Frühjahr bei Freiburg“): Der Chat sucht live im Web (OpenRouter-Websuche, etwa 0,007 USD je Suche, zählt ins Budget der Nachricht) und liest höchstens 3 Seiten von Veranstaltern (eigener User-Agent `HIKEALL_USER_AGENT`, `robots.txt` wird beachtet, 10 s Zeitlimit, höchstens 1 MB je Seite).

- **Quellenpflicht:** Jedes Feld (Name, Datum, Ort, Distanzen, Anmeldelink, Anmeldeschluss, Startgebühr) erscheint nur mit wörtlichem Zitat von der Seite des Laufs, sonst steht „nicht angegeben“. Läufe mit Datum in der Vergangenheit werden nicht gezeigt. Lässt sich kein Lauf belegen, zeigt der Chat Links zu Laufkalendern (`data/events/calendars.yaml`) statt einer Liste. Dazu der Hinweis „Angaben ohne Gewähr – bitte beim Veranstalter prüfen“.
- **Keine Speicherung:** Ergebnisse landen weder in der Datenbank noch in einem Datei-Cache; jede Frage sucht neu.
- **Ausgeschlossene Portale:** `laufen.de`, `marathon.de`, `d-u-v.org`, `ultra-marathon.org`, `ladv.de` und `hdsports.org` werden weder gesucht noch abgerufen (höchstens als Kalender-Link genannt).

Die ausführliche Capstone-README folgt in Plan 4.
