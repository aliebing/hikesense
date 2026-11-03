import type { Photo } from "./data";

/**
 * Background photos should be landscapes. Commons file names are the only hint we have, so a photo
 * counts as landscape when its file name says so (Blick, Aussicht, See, Tal, Wasserfall, …) and
 * names nothing that is clearly not one (buildings, transmitters, animals, a bank card, …).
 */
const LANDSCAPE =
  /(blick|aussicht|panorama(?!io)|landschaft|landscape|\bview|sunset|sonnenuntergang|sonnenaufgang|sunrise|nebel|[a-zäöü]tal(\b|_|-)|valley|[a-zäöü]see(\b|_|-)|lake|wasserfall|waterfall|schlucht|gorge|hochmoor|gipfel|summit|feldberg|belchen|hornisgrinde|schauinsland|kandel|herzogenhorn|nationalpark)/i;
const NOT_LANDSCAPE =
  /(sender|werk|kirche|church|kapelle|chapel|haus|museum|bahnhof|station|rathaus|denkmal|schloss|burg|castle|hotel|gasthof|reiher|maestro|n26|\biss\d|earth|mapillary|streetview|freileitung)/i;

function fileName(p: Photo): string | null {
  if (!p.page_url) return null;
  const raw = p.page_url.split("File:")[1];
  if (!raw) return null;
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

export function isLandscape(p: Photo): boolean {
  const name = fileName(p);
  return !!name && LANDSCAPE.test(name) && !NOT_LANDSCAPE.test(name);
}

/** Stable small hash, so a tour always gets the same pool photo. */
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

/** The tour's own first landscape photo, else a steady pick from the pool (by `key`), else none. */
export function pickBackdrop(own: Photo[], pool: Photo[], key: string): Photo | null {
  const mine = own.find(isLandscape);
  if (mine) return mine;
  return pool.length ? pool[hash(key) % pool.length] : null;
}
