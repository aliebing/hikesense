import { AUTHORITY, OPERATOR, UPDATED, type LegalDoc, type LegalLocale } from "./site";

/**
 * Privacy notice of HikeSense. It describes what the code actually does (checked 2026-11-05):
 * guest chat with a salted IP hash (24 h), chat log 30 days (HIKESENSE_LOG_RETENTION_DAYS),
 * accounts on the own server (Supabase Auth + Storage, self-hosted), confirmation mails via GMX,
 * chat to OpenRouter, map from basemap.de (fallback OSM tiles), photos from Wikimedia, position
 * only in the browser, language cookie + localStorage. Change it together with any of these.
 */
export function datenschutz(locale: LegalLocale): LegalDoc {
  const who = `${OPERATOR.name}, ${OPERATOR.street}, ${OPERATOR.city}, ${OPERATOR.country[locale]}, ${OPERATOR.email}`;
  if (locale === "en") {
    return {
      title: "Privacy notice",
      bindingNote: "This is a translation; the German version (Datenschutzerklärung) is binding.",
      updated: UPDATED.en,
      sections: [
        { h: "1. Controller", body: [who] },
        {
          h: "2. Hosting",
          body: [
            "HikeSense runs on a server rented from Contabo GmbH, Aschauer Straße 32a, 81549 Munich, Germany, which processes data on our behalf (Art. 28 GDPR). Accounts, saved plans, uploaded photos and chat logs are stored only on this server.",
            "When you open a page, the server necessarily processes your IP address and the request to deliver it. No access logs with IP addresses are kept.",
          ],
        },
        {
          h: "3. Chat without an account",
          body: [
            "You can use the planning assistant without an account. To limit guest use (10 requests per day per connection), the server stores a keyed hash (HMAC) of your IP address with the time of the request – never the address itself. These entries are deleted after 24 hours. Legal basis: Art. 6 (1) (f) GDPR (preventing misuse and costs).",
          ],
        },
        {
          h: "4. Chat log",
          body: [
            "For each chat request the server writes a log entry: your message and up to five earlier messages of the conversation, the understood request, the answer, the tours considered, the model's prompts and tool calls, duration and cost. With an account, the entry is linked to your account; for guests only a pseudonymous code is stored.",
            "The log serves operation, troubleshooting and improving the answers (Art. 6 (1) (f) GDPR). Only the operator can see it. Entries are deleted automatically after 30 days.",
          ],
        },
        {
          h: "5. AI processing (OpenRouter)",
          body: [
            "To understand and answer your message, it is sent with the conversation context to OpenRouter, Inc. (USA, https://openrouter.ai/privacy), which passes it to the language model's provider (currently OpenAI, USA). The search for events and group dates also runs through OpenRouter's web search. Your IP address, email address and account id are not sent.",
            "This is a transfer to a third country. Please do not enter personal data (names, addresses, health information) in the chat. Legal basis: Art. 6 (1) (f) GDPR (providing the assistant you are using).",
          ],
        },
        {
          h: "6. Account",
          body: [
            "To save plans and searches or to add your own photos you need an account. We store: email address, password (only as a hash), time of registration, confirmation and last sign-in, account status, your saved plans and searches, and photos you upload. Your photos are visible only to you.",
            "Confirmation and password-reset mails are sent through GMX (1&1 Mail & Media GmbH, Brauerstraße 48, 76135 Karlsruhe, Germany).",
            "Legal basis: Art. 6 (1) (b) GDPR (the account and its functions). The data is kept until you ask for your account to be deleted; write to the address above.",
          ],
        },
        {
          h: "7. Data stored in your browser",
          body: [
            "HikeSense uses only storage that is strictly necessary (Section 25 (2) no. 2 TDDDG), so there is no consent banner:",
            {
              list: [
                "Cookie „hikesense.lang“ and a localStorage entry: the language you chose (1 year).",
                "When you are signed in: your session in localStorage (deleted when you sign out).",
                "Your position on the „On the way“ page is computed only in your browser and never sent to the server.",
              ],
            },
            "There is no tracking, no analytics and no advertising.",
          ],
        },
        {
          h: "8. Content loaded from other servers",
          body: [
            "Some content is loaded by your browser directly from other servers, which therefore see your IP address (Art. 6 (1) (f) GDPR, showing maps and photos):",
            {
              list: [
                "Map: basemap.de of the Bundesamt für Kartographie und Geodäsie (BKG), Frankfurt am Main, Germany; if it cannot be reached, map tiles of the OpenStreetMap Foundation (United Kingdom).",
                "Photos: Wikimedia Commons of the Wikimedia Foundation, Inc. (USA).",
              ],
            },
            "Weather forecasts (Open-Meteo) are fetched by our server with the tour's coordinates only; no data about you is sent. Fonts are delivered by our own server.",
          ],
        },
        {
          h: "9. Your rights",
          body: [
            "You have the right to access (Art. 15 GDPR), rectification (Art. 16), erasure (Art. 17), restriction of processing (Art. 18), data portability (Art. 20) and to object to processing based on Art. 6 (1) (f) (Art. 21). Write to the address above.",
            `You can also complain to a supervisory authority, for example: ${AUTHORITY.name}, ${AUTHORITY.address}, ${AUTHORITY.url}.`,
          ],
        },
      ],
    };
  }
  return {
    title: "Datenschutzerklärung",
    updated: UPDATED.de,
    sections: [
      { h: "1. Verantwortlicher", body: [who] },
      {
        h: "2. Hosting",
        body: [
          "HikeSense läuft auf einem gemieteten Server der Contabo GmbH, Aschauer Straße 32a, 81549 München, die Daten in unserem Auftrag verarbeitet (Art. 28 DSGVO). Konten, gemerkte Pläne, hochgeladene Fotos und Chat-Protokolle liegen nur auf diesem Server.",
          "Beim Aufruf einer Seite verarbeitet der Server technisch notwendig Ihre IP-Adresse und die Anfrage, um die Seite auszuliefern. Zugriffsprotokolle mit IP-Adressen werden nicht gespeichert.",
        ],
      },
      {
        h: "3. Chat ohne Konto",
        body: [
          "Den Planungs-Assistenten können Sie ohne Konto nutzen. Um die Nutzung durch Gäste zu begrenzen (10 Anfragen pro Tag und Anschluss), speichert der Server einen mit einem geheimen Schlüssel gebildeten Hashwert (HMAC) Ihrer IP-Adresse mit dem Zeitpunkt der Anfrage – nie die Adresse selbst. Diese Einträge werden nach 24 Stunden gelöscht. Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO (Schutz vor Missbrauch und Kosten).",
        ],
      },
      {
        h: "4. Chat-Protokoll",
        body: [
          "Zu jeder Chat-Anfrage schreibt der Server einen Protokolleintrag: Ihre Nachricht und bis zu fünf frühere Nachrichten des Gesprächs, die verstandene Anfrage, die Antwort, die geprüften Touren, die Eingaben und Ausgaben des Sprachmodells, Dauer und Kosten. Mit Konto wird der Eintrag Ihrem Konto zugeordnet, bei Gästen wird nur ein pseudonymes Kürzel gespeichert.",
          "Das Protokoll dient dem Betrieb, der Fehlersuche und der Verbesserung der Antworten (Art. 6 Abs. 1 lit. f DSGVO). Einsehen kann es nur der Betreiber. Einträge werden nach 30 Tagen automatisch gelöscht.",
        ],
      },
      {
        h: "5. KI-Verarbeitung (OpenRouter)",
        body: [
          "Damit der Assistent Ihre Nachricht versteht und beantwortet, wird sie mit dem Gesprächsverlauf an die OpenRouter, Inc. (USA, https://openrouter.ai/privacy) übermittelt, die sie an den Anbieter des Sprachmodells (derzeit OpenAI, USA) weitergibt. Auch die Suche nach Veranstaltungen und Gruppenterminen läuft über die Websuche von OpenRouter. Ihre IP-Adresse, E-Mail-Adresse und Konto-ID werden dabei nicht übermittelt.",
          "Es handelt sich um eine Übermittlung in ein Drittland. Bitte geben Sie im Chat keine personenbezogenen Daten ein (Namen, Anschriften, Gesundheitsangaben). Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO (Bereitstellung des von Ihnen genutzten Assistenten).",
        ],
      },
      {
        h: "6. Benutzerkonto",
        body: [
          "Zum Merken von Plänen und Suchen und für eigene Fotos brauchen Sie ein Konto. Gespeichert werden: E-Mail-Adresse, Passwort (nur als Hashwert), Zeitpunkt von Registrierung, Bestätigung und letzter Anmeldung, Kontostatus, Ihre gemerkten Pläne und Suchen sowie von Ihnen hochgeladene Fotos. Ihre Fotos sehen nur Sie.",
          "Bestätigungs- und Passwort-Mails werden über GMX versandt (1&1 Mail & Media GmbH, Brauerstraße 48, 76135 Karlsruhe).",
          "Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO (Konto und seine Funktionen). Die Daten bleiben gespeichert, bis Sie die Löschung Ihres Kontos verlangen; schreiben Sie dazu an die oben genannte Adresse.",
        ],
      },
      {
        h: "7. Speicherung im Browser",
        body: [
          "HikeSense nutzt nur unbedingt erforderliche Speicherung (§ 25 Abs. 2 Nr. 2 TDDDG), deshalb gibt es kein Einwilligungsbanner:",
          {
            list: [
              "Cookie „hikesense.lang“ und ein localStorage-Eintrag: die gewählte Sprache (1 Jahr).",
              "Wenn Sie angemeldet sind: Ihre Sitzung im localStorage (wird beim Abmelden gelöscht).",
              "Ihr Standort auf der Seite „Unterwegs“ wird nur in Ihrem Browser verarbeitet und nie an den Server gesendet.",
            ],
          },
          "Es gibt kein Tracking, keine Reichweitenmessung und keine Werbung.",
        ],
      },
      {
        h: "8. Inhalte von anderen Servern",
        body: [
          "Einige Inhalte lädt Ihr Browser direkt von anderen Servern, die dabei Ihre IP-Adresse erhalten (Art. 6 Abs. 1 lit. f DSGVO, Anzeige von Karten und Fotos):",
          {
            list: [
              "Karte: basemap.de des Bundesamts für Kartographie und Geodäsie (BKG), Frankfurt am Main; ist es nicht erreichbar, Kartenkacheln der OpenStreetMap Foundation (Vereinigtes Königreich).",
              "Fotos: Wikimedia Commons der Wikimedia Foundation, Inc. (USA).",
            ],
          },
          "Wettervorhersagen (Open-Meteo) ruft unser Server nur mit den Koordinaten der Tour ab; Daten über Sie werden dabei nicht übermittelt. Schriften liefert unser eigener Server aus.",
        ],
      },
      {
        h: "9. Ihre Rechte",
        body: [
          "Sie haben das Recht auf Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung der Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) und Widerspruch gegen Verarbeitungen nach Art. 6 Abs. 1 lit. f (Art. 21). Schreiben Sie dazu an die oben genannte Adresse.",
          `Sie können sich außerdem bei einer Datenschutz-Aufsichtsbehörde beschweren, zum Beispiel: ${AUTHORITY.name}, ${AUTHORITY.address}, ${AUTHORITY.url}.`,
        ],
      },
    ],
  };
}
