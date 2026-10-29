# Laufveranstaltungen im Schwarzwald: Datenquellen und Import-Machbarkeit

Stand: 2026-10-29 · Quelle: Primärseiten der Anbieter (Verbände, Portale, Tourismus, Anmeldeplattformen), Abruf am 2026-10-29. Was sich nicht an der Primärseite bestätigen ließ, ist als **unverifiziert** markiert. Keine Rechtsberatung.

Ziel: Zu einem Weg oder Startort offizielle Läufe (10 km, Halbmarathon, Marathon, Trail) mit Datum, Ort, Distanzen, Anmeldelink, Anmeldeschluss, Startgebühr zeigen. Harte Regel: nichts erfinden, jede Angabe mit Quelle und „Stand".

## 1. Kurzfazit

- Es gibt **keine** offene, vollständige, maschinenlesbare Quelle mit allen sechs Feldern für den Schwarzwald. Anmeldeschluss und Startgebühr stehen in keiner Sammelquelle zuverlässig; sie liegen nur bei den Veranstaltern bzw. der Anmeldeplattform.
- Die Verbands- und Portalkalender (BLV, WLV, laufen.de, marathon.de, HDsports, LADV) sind **nur Webseiten ohne dokumentierte API/Export**; die Nutzungsbedingungen von LADV, marathon.de und laufen.de untersagen oder binden Kopieren/Datenbank-Übernahme an schriftliche Zustimmung.
- Einzige Quelle mit **ausdrücklich offener Lizenz** im Schwarzwald: Veranstaltungen in `mein.toubiz` / Schwarzwald Tourismus (Lizenz je Datensatz, z. B. CC BY-SA). Ein dokumentierter öffentlicher API-Zugang ist aber nicht belegt (siehe 2.1).

## 2. Quellen im Einzelnen

### 2.1 Schwarzwald Tourismus GmbH / mein.toubiz / TMBW Open Data Pool
- **API/Export:** Standard-Schnittstellen nur zwischen Partnern (TMBW, ADAC); „Die Seite beschreibt keine öffentliche API". Anbindung externer Datenbanken kostet einmalig plus monatlich ([Daten-Drehscheibe](https://www.schwarzwald-tourismus.info/partnernet/digitalisierung/daten-drehscheibe)). Ein TMBW-Forum-Foliensatz nennt „Generierung API-Key" mit Voraussetzung „Offene Lizenz CC0, CC BY oder CC …" ([Forum Mai 2025, PDF](https://www.schwarzwald-tourismus.info/_Resources/Persistent/e032f96ed0bc397a4548afa9d1ba2e1246aa581d/STG%20mein.toubiz%20Forum_Mai%202025.pdf)); Endpunkt, Format, Zugang für Dritte: **unverifiziert**.
- **Lizenz:** Anbieter vergeben je Datensatz Open-Data-Lizenzen; „von jedermann zu jedem Zweck genutzt, weiterverbreitet und weiterverwendet" ([Open Data](https://www.schwarzwald-tourismus.info/partnernet/digitalisierung/mein-toubiz-datenbank-1/open-data)). Einträge mit „Alle Rechte vorbehalten" werden bei TMBW nicht ausgespielt; TMBW empfiehlt „CC BY oder CC BY-SA" ([Forum-PDF](https://www.schwarzwald-tourismus.info/_Resources/Persistent/e032f96ed0bc397a4548afa9d1ba2e1246aa581d/STG%20mein.toubiz%20Forum_Mai%202025.pdf)). Beispiel Freiburg Marathon: Seitenfuß „Freiburg · CC BY-SA", „von Schwarzwald Tourismus GmbH" ([Eintrag](https://www.schwarzwald-tourismus.info/veranstaltungen/mein-freiburg-marathon-2027-3a72b8ae7b)). Daraus folgt: Lizenz ist **pro Eintrag** zu lesen, nicht pauschal. Haftung: „keine Gewähr für die Aktualität, Richtigkeit, Vollständigkeit" ([Impressum](https://www.schwarzwald-tourismus.info/impressum)).
- **Felder (Beispiel-Eintrag):** Datum, Ort/Adresse, Beschreibung mit Distanzen, Link „Weitere Informationen". **Keine** Koordinaten, Preis, Anmeldung, kein Stand-Datum sichtbar ([Eintrag](https://www.schwarzwald-tourismus.info/veranstaltungen/mein-freiburg-marathon-2027-3a72b8ae7b)).
- **Abdeckung/Pflege:** Veranstalter bzw. Orte pflegen selbst; Veranstaltungssuche hat nur Freitext und Datum, keinen Sport-Filter, kein RSS/iCal ([Veranstaltungen](https://www.schwarzwald-tourismus.info/veranstaltungen)). Vollständigkeit für Läufe: unverifiziert.
- **TMBW-Seite `tourismus-bw.de/open-data`:** leitet auf `visit-bw.com/de` um, dort kein Open-Data-Hinweis ([visit-bw.com](https://www.visit-bw.com/de)). Aktuelle Spezifikation des „Open Data Pool BW": **unverifiziert**. Kontakt laut Seite: info@tourismus-bw.de.
- **Verdikt:** *Nutzbar mit Namensnennung (CC BY / BY-SA je Eintrag), technischer Zugang ungeklärt.* Nur Basisdaten (Datum, Ort, Link). Bei BY-SA: Ableitungen/Anzeige-Datenbank wären zu prüfen (Share-Alike), unverifiziert.

### 2.2 LADV (Leichtathletik-Datenverarbeitung) – Quelle der Verbandskalender
- **API:** „LADV API 2" für Ausschreibungen, Ergebnisse, Athleten; API-Key nötig; Zugriff muss „im Vorfeld von Verantwortlichen der Organisationseinheit freigegeben werden"; Nutzung durch Apps/Webseiten/andere Projekte „i. d. R. nicht möglich" ([Entwickler](https://ladv.de/entwickler)).
- **Terms:** Automatisiertes Abrufen („Bots, Roboter, Spider oder Scraper") ohne schriftliche Genehmigung untersagt; auch programmgestützte Extraktion/Weiterverarbeitung wesentlicher Inhalte genehmigungspflichtig; Ausnahme nur für Vereine/Verbände auf eigenen Seiten ([Nutzungsbedingungen](https://ladv.de/page/view/nutzungsbedingungen.htm), § 5 Nr. 11/12, sinngemäß wiedergegeben).
- **Felder:** Ausschreibungen; ob Anmeldeschluss/Gebühr strukturiert enthalten: unverifiziert.
- **Verdikt:** *Nicht erlaubt ohne schriftliche Genehmigung* (Anfrage an LADV möglich).

### 2.3 BLV (Baden) und WLV (Württemberg)
- **BLV:** Kalender „stadionferne Veranstaltungen" (Straße, Trail, Cross) mit Datum, Name, Ort; Detail: Veranstalter, Homepage, Startort, Wettbewerbe. Kein Export, kein Stand-Datum ([BLV Termine](https://www.blv-online.de/laeufe/veranstaltungstermine)). Der „Laufkalender BW" (~500 Läufe, jährlich gedruckt) verlangt LADV-Anmeldung bis Ende Oktober des Vorjahres und verweist auf BLV, WLV und DLV-Kalender ([Laufkalender BW](https://www.blv-online.de/laeufe/laufkalender-baden-wuerttemberg)). Anfrage an Geschäftsstelle: gs@blv-online.de.
- **WLV:** Kalender unter [Veranstaltungstermine](https://www.wlv-sport.de/home/breitensport/laufveranstaltungen/veranstaltungstermine); Export/Lizenz auf der Startseite nicht erwähnt. Der Schwarzwald liegt überwiegend in Baden, teils in Württemberg (Nordschwarzwald/Ostrand).
- **Impressum/AGB beider Verbände:** nicht gelesen, **unverifiziert**. Ohne ausdrückliche Lizenz gilt Urheber-/Datenbankrecht.
- **Verdikt:** *Nur manuell nutzbar (als Prüfquelle) / Zustimmung erfragen.* Kein Scraping.

### 2.4 laufen.de (Laufkalender, DLV-nah)
- Betreiber DLM RunMedia GmbH; Veranstaltungen über die DLV-Landesverbände; Suche nach Ort/PLZ + Radius, Streckenlänge, Zeitraum; kein BW-Filter; Anmeldelink/Frist/Gebühr in der Übersicht nicht ausgewiesen; kein Export/API erwähnt ([Laufkalender](https://www.laufen.de/laufkalender)).
- **AGB § 11:** „Eine Veränderung, Vervielfältigung, Veröffentlichung, Weitergabe an Dritte" nur mit vorheriger schriftlicher Zustimmung, ausdrücklich inkl. „Datenbanken"; nur „ein einfaches Nutzungsrecht zu privaten Zwecken" ([AGB](https://www.laufen.de/agb)).
- **Verdikt:** *Nicht erlaubt* (Import); Verlinkung auf die Kalenderseite ist möglich.

### 2.5 marathon.de
- Kalender mit Datum, Distanz, Ort, Filter Marathon/Halbmarathon/10 km; keine API/Export erwähnt ([Startseite](https://www.marathon.de/)).
- **Impressum:** „Kein Teil dieses Online-Angebotes darf ohne ausdrückliche schriftliche Genehmigung in irgendeiner Form kopiert" werden; verboten ist auch „die Aufnahme in elektronische Datenbanken oder anderen Websites" ([Impressum](https://www.marathon.de/impressum)).
- **Verdikt:** *Nicht erlaubt.*

### 2.6 HDsports Laufkalender
- >10 000 Events; Felder: Name, Datum (fixiert/nicht fixiert), Ort, Distanzen (teils mit Höhenmetern), teils „Jetzt anmelden"; kein Export/API erwähnt ([Laufkalender](https://www.hdsports.org/laufen)).
- Nutzungsbedingungen: keine Klausel zu Wiederverwendung/Scraping; nur „Alle Rechte vorbehalten … Urheberrechtsschutz" ([Nutzungsbedingungen](https://www.hdsports.org/nutzungsbedingungen)). „AGB für Vermarktung" (PDF) nicht gelesen: unverifiziert.
- **Verdikt:** *Nicht erlaubt ohne Rückfrage* (Rechte vorbehalten, keine Lizenz).

### 2.7 DUV (Ultramarathon-Kalender/Statistik)
- Kalender unter `statistik.d-u-v.org/calendar.php` verlinkt ([DUV](https://www.ultra-marathon.org/)); Inhalt und Felder nicht geprüft: **unverifiziert**.
- Nutzungsbedingungen: „Die unerlaubte Vervielfältigung oder Weitergabe einzelner Inhalte oder kompletter Seiten ist nicht gestattet"; Speichern in Datenbanken erfasst ([Nutzungsbedingungen](https://www.ultra-marathon.org/2-uncategorised/5-nutzungsbedingungen)).
- **Verdikt:** *Nicht erlaubt* (Import). Nur für Ultras >42 km relevant.

### 2.8 Outdooractive Data API (Typ `event`)
- API mit Projekt- + API-Key; Inhaltstypen `tour|poi|event|offer` ([Data API](https://developers.outdooractive.com/API-Reference/Data-API.html)). Event-Felder und Lizenz je Objekt dort nicht dokumentiert: unverifiziert.
- API-AGB: nur Darstellung „innerhalb seiner Applikation"; Speicherung nur wenn „zwingend nötig", Aktualisierung „mindestens alle 24 Stunden", Quelle/Autor angeben, nur Unternehmer als Nutzer ([API-AGB](https://corporate.outdooractive.com/de/api-agb)). Kosten: unverifiziert.
- **Verdikt:** *Für ein lokales Hobby-Projekt nicht passend* (Unternehmer-Vertrag, Live-Abruf-Pflicht, kein dauerhaftes Ablegen mit „Stand"-Anspruch).

### 2.9 Anmeldeplattformen (RaceResult u. a.)
- RaceResult „Simple API" gibt Daten eines Event-Files über statische Links frei – vom Veranstalter konfiguriert, kein öffentlicher Event-Index dokumentiert ([Support](https://www.raceresult.com/en/support/kbexport2?id=35643)). Für Dritte kein Weg, „alle Läufe" zu listen.
- mika:timing, davengo, RaceID: nicht geprüft, **unverifiziert**.
- **Verdikt:** *Nur als Ziel für Anmeldelinks* (Link zur Veranstalter-Anmeldung), nicht als Datenquelle.

### 2.10 Landes-/Bundes-Open-Data (daten.bw, GovData, MobiDataBW)
- Suche ergab keinen Veranstaltungs- oder Laufdatensatz; BW hat keine Pflicht zur Open-Data-Bereitstellung ([IM BW](https://im.baden-wuerttemberg.de/de/digitalisierung/open-data-fuer-baden-wuerttemberg)). Direkte Prüfung der Portale selbst: **unverifiziert** (nur Suchergebnis).
- **Verdikt:** *Keine Quelle gefunden.*

### 2.11 Nicht prüfbar
- ITRA-Rennsuche/-API: Seiten lieferten keinen Inhalt, **unverifiziert**.
- runnersworld.de-Laufkalender, trail-magazin: nicht geprüft, **unverifiziert**.

## 3. Beispielrennen: wo die Daten wirklich liegen

| Rennen | Datum/Ort/Distanzen | Anmeldung | Frist | Gebühr | Stand |
|---|---|---|---|---|---|
| Schwarzwald-Marathon Bräunlingen | 9./10.10.2027, Bräunlingen; Marathon, Halb, 10 km u. a. ([Startseite](https://www.schwarzwaldmarathon.de/)) | RaceResult `my.raceresult.com/425427` ([Anmeldung](https://schwarzwaldmarathon.de/anmeldung)) | „Die Online-Anmeldung schließt am 07.10.2027" (ebd.) | auf der Seite nicht aufgeführt (ebd.) | kein Datum |
| Mein Freiburg Marathon | 4.4.2027, Messe Freiburg; Marathon, Halb, 10 km ([Startseite](https://www.mein-freiburgmarathon.de/)) | Übersichtsseite Anmeldung (ebd.) | Anmeldeschluss nicht genannt; Ummeldung bis 1.4.2027; Schülerlauf-Datum widerspricht (ebd.) | nur als PDF ([Gebührenübersicht](https://mein-freiburgmarathon.de/wp-content/uploads/2026/08/Gebuehrenuebersicht-Freiburg-Marathon-2027.pdf)), Inhalt nicht gelesen | kein Datum |

- Lehre: Datum/Ort/Distanzen sind kaum strittig; **Frist und Gebühr stehen nur beim Veranstalter** (Seite, PDF, Plattform), uneinheitlich und teils widersprüchlich. Ein Import dieser Felder wäre nicht verlässlich; sie müssten je Lauf mit Quelle + Prüfdatum erfasst werden.
- Freiburg: `www.freiburg-marathon.de/.com` lieferten Zertifikatsfehler; als Datenquelle ohnehin irrelevant.
- Trail-Veranstaltungen im Schwarzwald: kein Beispiel geprüft, **unverifiziert**.

## 4. Empfehlung

**Beste Import-Quelle:** Schwarzwald-Tourismus-/TMBW-Eventdaten aus `mein.toubiz` (offene CC-Lizenz je Eintrag) – aber nur nach geklärtem API-Zugang (Anfrage an Schwarzwald Tourismus GmbH, Tel. +49 761 896460, bzw. info@tourismus-bw.de) und nur für Basisfelder (Datum, Ort, Link). Heute **nicht** automatisch importierbar belegt.

**Fallback (Plan 3, realistisch): handgepflegte Liste** `running_events` mit wenigen Dutzend Läufen (Marathon/Halb/10 km/Trail im Schwarzwald), Felder: Name, Datum, Ort (+ Koordinate selbst gesetzt), Distanzen, `source_url`, Anmeldelink (Verweis auf Veranstalter/Plattform), `registration_deadline` und `fee` **nullable** („nicht angegeben" zeigen, nie schätzen), `checked_at` als „Stand". Quelle immer die Veranstalterseite; Verbandskalender nur zum Auffinden.

**Plan 3:**
- Tabelle + Anzeige „Läufe in der Nähe" (Radius um Weg/Startort), Anzeige mit Quelle und Stand; Hinweis „Bitte beim Veranstalter prüfen".
- Veralterungsregel: Lauf mit Datum in der Vergangenheit oder Prüfdatum älter als z. B. 90 Tage wird als „veraltet" markiert, nicht gelöscht (Schwellenwert ist ein Vorschlag).

**Next steps:**
- Anfrage bei Schwarzwald Tourismus / TMBW zu API-Zugang, Lizenz, Schema (Eventdaten, Sport-Kategorie).
- Anfrage bei BLV/LADV zur schriftlichen Erlaubnis (Ausschreibungen/Termine).
- Wenn beides klappt: Importer mit Lizenzfeld je Eintrag, Nur-CC-Filter, Namensnennung.
- Nicht verfolgen: Scraping von laufen.de, marathon.de, HDsports, DUV, LADV (siehe 2.2–2.7).

## 5. Nicht verifiziert (Übersicht)

- Technischer Zugang/Endpunkt zum Open Data Pool BW und zur toubiz-Schnittstelle für Dritte; aktuelle TMBW-Seite `open-data`.
- Impressum/AGB von BLV und WLV; HDsports „AGB für Vermarktung".
- Felder in LADV-Ausschreibungen; LADV-API-Key-Bedingungen (`/entwickler/apikeys`).
- DUV-Kalenderinhalt, ITRA, runnersworld, trail-magazin, mika:timing, davengo, RaceID.
- Outdooractive: Event-Felder, Lizenz je Objekt, Kosten.
- daten.bw/GovData/Mobilithek (nur über Suchergebnis geprüft).
- Gebühren der Läufe (Gebührenübersicht-PDF nicht gelesen); Trail-Beispielrennen.

## 6. Entscheidung (Nutzer, 2026-10-29)

Keine handgepflegte Liste. Plan 3 bekommt eine Live-Suche des Agenten (A) mit Links auf Laufkalender als Rückfall (B) – Details in `2026-10-29-plan-02-inputs-from-hikeai.md`, Punkt 7.
