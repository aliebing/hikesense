/**
 * Operator data for the legal pages (Impressum, Datenschutz). The whole `legal/` folder is meant to be
 * copied into the operator's other apps (CineSense): this file stays the same, `datenschutz.ts`
 * describes what the respective app actually processes.
 */
export const OPERATOR = {
  name: "Alexander Liebing",
  street: "Panoramaweg 6",
  city: "76189 Karlsruhe",
  country: { de: "Deutschland", en: "Germany" },
  email: "aliebing@gmx.de",
};

/** Supervisory authority for an operator in Baden-Württemberg. */
export const AUTHORITY = {
  name: "Der Landesbeauftragte für den Datenschutz und die Informationsfreiheit Baden-Württemberg",
  address: "Lautenschlagerstraße 20, 70173 Stuttgart",
  url: "https://www.baden-wuerttemberg.datenschutz.de",
};

/** Month of the last change, shown under both pages. */
export const UPDATED = { de: "November 2026", en: "November 2026" };

export type LegalLocale = "de" | "en";

/** A paragraph, or a bullet list. Email addresses and https links in the text become links. */
export type Block = string | { list: string[] };
export type Section = { h: string; body: Block[] };
export type LegalDoc = { title: string; intro?: string; sections: Section[]; updated: string; bindingNote?: string };
