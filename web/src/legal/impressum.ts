import { OPERATOR, UPDATED, type LegalDoc, type LegalLocale } from "./site";

/** Impressum (§ 5 DDG, § 18 Abs. 2 MStV). `app` is the site's name, `note` its own caveat about automatic answers. */
export function impressum(locale: LegalLocale, app: string, note: { de: string; en: string }): LegalDoc {
  const address = [OPERATOR.name, OPERATOR.street, OPERATOR.city, OPERATOR.country[locale]];
  if (locale === "en") {
    return {
      title: "Legal notice",
      bindingNote: "This is a translation; the German version (Impressum) is binding.",
      updated: UPDATED.en,
      sections: [
        { h: "Provider (Section 5 DDG)", body: [{ list: address }] },
        { h: "Contact", body: [`Email: ${OPERATOR.email}`] },
        { h: "Responsible for the content (Section 18 (2) MStV)", body: [`${OPERATOR.name}, address as above.`] },
        {
          h: "About this site",
          body: [
            `${app} is a private, non-commercial project (final project of a Turing College course). There is no advertising and nothing is sold.`,
            note.en,
          ],
        },
        {
          h: "Links",
          body: ["This site links to external websites. Their operators alone are responsible for their content. At the time of linking, no legal violations were apparent; if any become known, the link will be removed."],
        },
      ],
    };
  }
  return {
    title: "Impressum",
    updated: UPDATED.de,
    sections: [
      { h: "Anbieter (§ 5 DDG)", body: [{ list: address }] },
      { h: "Kontakt", body: [`E-Mail: ${OPERATOR.email}`] },
      { h: "Verantwortlich für den Inhalt (§ 18 Abs. 2 MStV)", body: [`${OPERATOR.name}, Anschrift wie oben.`] },
      {
        h: "Über diese Seite",
        body: [
          `${app} ist ein privates, nicht kommerzielles Projekt (Abschlussprojekt eines Turing-College-Kurses). Es gibt keine Werbung und es wird nichts verkauft.`,
          note.de,
        ],
      },
      {
        h: "Links",
        body: ["Diese Seite verweist auf fremde Webseiten. Für deren Inhalte sind allein deren Betreiber verantwortlich. Zum Zeitpunkt der Verlinkung waren keine Rechtsverstöße erkennbar; werden welche bekannt, wird der Link entfernt."],
      },
    ],
  };
}
