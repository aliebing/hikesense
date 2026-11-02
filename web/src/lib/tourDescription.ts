/** True when TourDescription would show at least one line of data. */
export function hasDescription(d: { sentence: string | null; tags: string[]; surface: string | null; profile: [number, number][] | null }): boolean {
  return !!d.sentence || d.tags.length > 0 || !!d.surface || !!d.profile;
}
