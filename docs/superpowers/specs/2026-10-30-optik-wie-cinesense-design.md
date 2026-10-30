# Optik wie CineSense – Design

Stand: 2026-10-30 · ergänzt `2026-10-28-hike-all-about-design.md` §10 (Oberfläche) · kommt **vor** Plan 3

Kennzeichnung: **[Ali]** = vom Nutzer entschieden, **[Claude]** = meine Entscheidung (beim Review änderbar), **[Builder]** = bewusst offen.

## 1. Warum

Die jetzige Startseite ist ein Panorama-Bild mit Chat und darunter Kartenreihen (Fernwege, Tagestouren) und Ergebniskarten direkt im Chat. Ali möchte die Wirkung von CineSense (`~/projects/CineSenseAi/web`): eine ruhige Bühne mit Bewegung, auf der man **nur chattet**, und die Vorschläge kommen erst auf einer eigenen Seite. Das Planen soll sich wie ein Gespräch anfühlen, nicht wie eine Datenbankliste – derselbe Grund wie bei CineSense („feels like a database rather than going to the movies“).

Die Umsetzung kommt vor Plan 3, damit dessen Oberflächenteile (Tagesetappen, Merken, Unterwegs) gleich in das neue Layout gebaut werden **[Ali]**.

## 2. Ablauf

1. **Startseite [Ali]:** Chatbox links. Rechts ziehen Kachelreihen langsam vorbei; jede Kachel ist ein Thumbnail mit Transparenz, **nicht anklickbar**.
2. **Während des Chats [Ali]:** Kacheln, die zu den Wünschen passen, werden **einzeln klarer und anklickbar**; die übrigen bleiben blass. Ein Klick auf eine passende Kachel öffnet die Routenansicht (Schritt 4).
3. **Knopf „Vorschläge zeigen →“ [Ali]** wie „Show results →“ bei CineSense: erscheint, sobald der Chat Touren gefunden hat; der Nutzer entscheidet, wann er wechselt. Kein automatischer Seitenwechsel.
4. **Vorschlagsseite [Ali]:** die vorgeschlagenen Routen als anklickbare Bildkarten.
5. **Routenansicht [Ali]:** nach Klick auf eine Route deren Ansicht mit Karte (heute `/t/[trailId]`).

## 3. Bewegung [Ali]

Beides, wie bei CineSense:
- **Hintergrund:** große Schwarzwald-Landschaften (Commons-Fotos der Touren/Fernwege) blenden langsam ineinander und zoomen leicht (Ken-Burns), dazu Nebel/Licht, der sich langsam bewegt.
- **Kachelreihen:** 2–3 Reihen, die gleichmäßig und endlos vorbeiziehen, Reihen in wechselnder Richtung.

## 4. Einzelheiten

**Startseite**
- Kacheln zeigen **echte Touren aus der Datenbank** mit Commons-Foto und Namen, keine erfundenen Beispiele **[Claude]**. Auswahl: Touren mit Foto, gestreut über die Region (vorhandenes `pickSpread`); keine Tour doppelt in den Reihen **[Claude]**.
- „Passend“ = Tour ist unter den Touren, die der Chat in der letzten Antwort geliefert hat (`TourCard`s des Streams). Fehlt eine passende Tour in den Reihen, wird sie hineingenommen (ersetzt eine blasse Kachel), damit jede gefundene Tour sichtbar wird **[Claude]**.
- Ausweichtouren („Keine Tour erfüllt alle Wünsche …“) gelten ebenfalls als passend, bekommen aber an der Kachel einen dezenten Hinweis auf die verletzte Bedingung **[Claude]** – sonst wirkte eine Ausweichtour wie ein Volltreffer (Anti-Ziel „still lockern“).
- Der Chat zeigt keine Ergebniskarten mehr; seine Antworttexte, Rückfragen (Optionen) und Chips bleiben **[Claude]**.
- Die bisherigen Kartenreihen „Fernwege/Tagestouren“ auf der Startseite entfallen. Fernwege bleiben über eine schlichte Navigation oben erreichbar (wie „🔍 Search · Credits“ bei CineSense) **[Claude]**.
- Titel und Untertitel bleiben (Serifenschrift), Farben aus Spec §10: Schwarzwaldgrün, warmes Papierweiß **[Claude]**.

**Vorschlagsseite** (eigene Route, z. B. `/vorschlaege`) **[Claude]**
- Oben die verstandenen Wünsche als Chips und der Antwortsatz des Chats; bei Unerfüllbarkeit beginnt er wie heute mit „Keine Tour erfüllt alle Wünsche, weil …“.
- Darunter 3–5 große Bildkarten mit km, Hm, Gehzeit, Entfernung zum Start und – bei Ausweichtouren – der einen Abweichung („340 Hm statt < 200“). Inhalt wie das heutige `TourResultCard`.
- Der Chat bleibt auf der Seite verfügbar (eingeklappt, wie die Chat-Schublade bei CineSense); eine Änderung dort aktualisiert die Karten.
- Wird die Seite ohne vorherigen Chat aufgerufen: freundlicher Hinweis mit Link zur Startseite, keine leere Seite.

**Routenansicht**
- Die vorhandene Seite `/t/[trailId]` (Bild, Eckdaten, Fotos, Karte, Quellen) im neuen Look; Plan 3 ergänzt dort Tagesetappen, Wetter und „Merken“.
- „Zurück“ führt zur Vorschlagsseite, wenn man von dort kam **[Claude]**.

## 5. Grenzen und Regeln

- Alle Regeln aus Plan 2 gelten weiter: Zahlen und Touren nur aus Code/Datenbank, Ausweichen offen benannt, Quellen und Lizenzen sichtbar. Jedes Hintergrund- und Kachelfoto hat seine Commons-Attribution erreichbar (wie heute beim Panorama).
- **Weniger Bewegung:** bei `prefers-reduced-motion` stehen Hintergrund und Reihen still (ein Bild, statische Reihen) **[Claude]**.
- **Handy [Claude]:** Chat oben, darunter eine Kachelreihe; Nebel aus, Hintergrundwechsel langsamer. Plan 3 („Unterwegs“) baut darauf auf.
- Keine neuen Backend-Endpunkte nötig: Kacheln kommen wie heute direkt aus Supabase, die passenden Touren aus dem Chat-Stream **[Claude]**. Wie der Chatzustand zwischen Startseite und Vorschlagsseite übergeben wird (Context, sessionStorage) **[Builder]**.
- Bestehende Tests für Chat-Protokoll, Grounding-Anzeige und Karte bleiben grün; Komponenten, die entfallen, gehen mit ihren Tests.

## 5a. Festlegungen nach der Builder-Prüfung [Claude]

- **Chatzustand:** Ein Gespräch je Browser-Tab. Es liegt in einem Provider im Root-Layout und wird in `sessionStorage` gespiegelt: Verlauf, Thread-ID, verstandene Wünsche und die Touren der letzten Antwort. So überlebt es den Seitenwechsel und ein Neuladen. Ein neuer Tab beginnt neu. Die Vorschlagsseite nutzt denselben Zustand und dieselbe Chat-Komponente in eingeklappter Form.
- **„Gefunden“:** Maßgeblich ist nur die **letzte** Antwort mit Touren, Ausweichtouren eingeschlossen. Liefert eine spätere Antwort keine Touren, werden die Kacheln wieder blass und der Knopf verschwindet. Eine reine Rückfrage ändert nichts an den Kacheln.
- **Anzahl:** Höchstens 5 passende Kacheln, so viele, wie der Agent liefert. Hat eine passende Tour kein Foto, zeigt die Kachel eine neutrale grüne Fläche mit dem Namen. Auf der Vorschlagsseite gilt dasselbe.
- **Fernwege:** In der Navigation oben ein Eintrag „Fernwege“, der die vorhandenen Fernwege direkt auf `/t/[trailId]` verlinkt (kleines Menü). Es gibt keine neue Listenseite.
- **Zurück:** Die Routenansicht bekommt `?von=vorschlaege`, wenn man von der Vorschlagsseite kommt. Nur dann führt „Zurück“ dorthin, sonst zur Startseite.
- **Bildnachweise:** Das Hintergrundbild nennt seine Attribution wie heute das Panorama. Für die Kacheln gibt es einen Eintrag „Bildnachweise“, der als Overlay alle gerade sichtbaren Fotos mit Autor und Lizenz auflistet. Die Kacheln selbst haben keinen Hover-Nachweis. Auf der Vorschlagsseite trägt jede Karte ihren Nachweis wie heute `TourResultCard`.
- **Handy:** Passende Touren rücken an den Anfang der einen Reihe. Der Hauptweg ist dort der Knopf „Vorschläge zeigen →“.

## 6. Nicht-Ziele

- Kein Vorhang/Kinorahmen, keine Trailer – das Kino-Motiv bleibt bei CineSense.
- Keine Personalisierung (👍/👎) in diesem Schritt.
- Kein neues Ranking; welche Touren passen, entscheidet weiter der Agent.

## 7. Dem Builder überlassen

Komponentenschnitt, Animationstechnik (CSS vs. JS), genaue Geschwindigkeiten und Transparenzwerte, Anzahl Kacheln je Reihe, Übergangsanimation zwischen Seiten, wie viel aus CineSense (`HeroSlides`, `FogLight`, `TileRows`) übernommen oder nachgebaut wird.
