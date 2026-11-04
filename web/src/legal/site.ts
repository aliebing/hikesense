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

/** HikeSense's caveat in the Impressum. */
export const APP_NOTE = {
  de: "Antworten des Planungs-Assistenten werden automatisch erzeugt und können Fehler enthalten. Wege, Zustand, Öffnungszeiten und Wetter bitte vor dem Aufbruch vor Ort prüfen.",
  en: "Answers of the planning assistant are generated automatically and can be wrong. Check routes, conditions, opening hours and weather on site before you set off.",
};

/** Month of the last change, shown under both pages. */
export const UPDATED = { de: "November 2026", en: "November 2026" };

export type LegalLocale = "de" | "en";

/** A paragraph, or a bullet list. Email addresses and https links in the text become links. */
export type Block = string | { list: string[] };
export type Section = { h: string; body: Block[] };
export type LegalDoc = { title: string; intro?: string; sections: Section[]; updated: string; bindingNote?: string };
