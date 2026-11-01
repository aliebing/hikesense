import ElevationProfile from "./ElevationProfile";
import WishChips from "./WishChips";

/**
 * „Beschreibung“ of a day hike, built from data only: the sentence from describeTour, the chat's
 * verdicts for this tour (if any), feature tags, surface shares and the elevation profile.
 */
export default function TourDescription({
  sentence,
  tags,
  surface,
  profile,
  trailId,
}: {
  sentence: string | null;
  tags: string[];
  surface: string | null;
  profile: [number, number][] | null;
  trailId: string;
}) {
  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed">
      {sentence && <p className="text-base">{sentence}</p>}
      <WishChips trailId={trailId} />
      {tags.length > 0 && (
        <ul aria-label="Merkmale" className="flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <li key={t} className="rounded-full border border-wald/30 px-2.5 py-0.5 text-xs">
              {t}
            </li>
          ))}
        </ul>
      )}
      {surface && <p className="text-xs text-wald-dunkel/75">{surface}</p>}
      {profile && <ElevationProfile profile={profile} />}
    </div>
  );
}

/** True when TourDescription would show at least one line of data. */
export function hasDescription(d: { sentence: string | null; tags: string[]; surface: string | null; profile: [number, number][] | null }): boolean {
  return !!d.sentence || d.tags.length > 0 || !!d.surface || !!d.profile;
}
