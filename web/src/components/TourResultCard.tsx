import Link from "next/link";
import type { ConstraintResult, Labels, TourCard } from "../lib/chat";
import { useLocale, useT } from "../i18n";
import type { Messages } from "../i18n/en";
import { duration, hm, km } from "../lib/format";
import { coverOf } from "../lib/chatState";
import Attribution from "./Attribution";
import MerkenButton from "./MerkenButton";

const KIND_KEYS = { length_km: "length", ascent_m: "ascent", duration_h: "duration", radius_km: "distance", roundtrip: "roundWalk" } as const;

/** Label of a constraint kind in the active language (unknown kinds show as they are). */
export const kindLabel = (kind: string, t: Messages): string => {
  const key = KIND_KEYS[kind as keyof typeof KIND_KEYS];
  return key ? t.chat[key] : kind;
};

/** Unit shown after the bound ("" for kinds without a unit). */
export const kindUnit = (kind: string, t: Messages): string =>
  ({ length_km: "km", ascent_m: t.chat.unitAscent, duration_h: "h", radius_km: "km" })[kind as "length_km"] ?? "";

function Row({ r, deviation, near = false }: { r: ConstraintResult; deviation: string | null; near?: boolean }) {
  const t = useT();
  const label = kindLabel(r.kind, t);
  const unit = kindUnit(r.kind, t);
  // the backend's text for a round walk is German ("Rundweg"): label and verdict say it all
  const bound = r.kind === "roundtrip" ? "" : unit && r.bound ? `${r.bound} ${unit}` : r.bound;
  const colon = bound ? `: ${bound}` : "";
  const paren = bound ? ` (${bound})` : "";
  if (r.ok === true) {
    return (
      <li>
        <span aria-label={t.results.met}>✓</span> {label}{colon}
      </li>
    );
  }
  if (r.ok === false && near) {
    // the miss is named once, in the yellow reason line above the title
    return (
      <li className="text-amber-900">
        <span aria-label={t.results.narrow}>~</span> {label}: {t.results.narrow}{paren}
      </li>
    );
  }
  if (r.ok === false) {
    return (
      <li className="text-red-800">
        <span aria-label={t.results.violated}>✗</span> {label}: {deviation ?? `${t.results.notMet}${paren}`}
      </li>
    );
  }
  return (
    <li className="text-tinte/80">
      <span aria-label={t.results.unknown}>?</span> {label}: {t.results.unknown}, {t.results.notCheckable}{paren}
    </li>
  );
}

/** One proposed tour with its key figures, per-condition verdicts and preferences. */
export default function TourResultCard({
  card,
  runWithoutPace = false,
  labels = {},
  size = "compact",
  from,
}: {
  card: TourCard;
  runWithoutPace?: boolean;
  labels?: Labels;
  size?: "compact" | "large";
  from?: "chat";
}) {
  const t = useT();
  const { locale } = useLocale();
  const large = size === "large";
  const name = (ids: string[]) => ids.map((t) => labels[t] ?? t).join(", ");
  const photo = coverOf(card);
  const firstViolated = card.results.findIndex((r) => r.ok === false);
  const p = card.preference;
  let time: string | null = null;
  if (card.duration_h !== null) time = t.results.time(duration(card.duration_h, locale));
  else if (runWithoutPace) time = t.results.timePace;
  const facts = [
    card.length_km === null ? t.results.unknownLength : km(card.length_km, locale),
    card.ascent_m === null ? t.results.unknownAscent : hm(card.ascent_m, locale),
    ...(time ? [time] : []),
    card.distance_km === null ? t.results.inArea : t.results.distanceKm(km(card.distance_km, locale)),
  ];
  return (
    <article
      className={`flex flex-col gap-1 rounded-md p-3 text-sm text-tinte ${
        card.near_miss ? "ring-2 ring-amber-400 focus-within:ring-4 focus-within:ring-amber-600 " : ""
      }${
        from ? `relative bg-papier/80 backdrop-blur-sm shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl${card.near_miss ? "" : " focus-within:ring-2 focus-within:ring-amber-400"}` : "bg-papier/95"
      }`}
    >
      {!photo && large && (
        <div aria-hidden="true" className="grid h-48 w-full place-items-center rounded-sm wald-verlauf p-3 text-center font-serif text-lg text-papier">
          {card.name}
        </div>
      )}
      {photo && (
        <div className="flex flex-col gap-0.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo.thumb_url} alt="" loading="lazy" className={`${large ? "h-48" : "h-24"} w-full rounded-sm object-cover`} />
          {/* above the card-wide link so its licence links stay clickable */}
          <Attribution
            photo={photo}
            label={card.cover_nearby ? t.tour.photoNearby : undefined}
            className="relative z-10 text-tinte/70"
          />
        </div>
      )}
      {card.near_miss && (
        <div className="flex flex-col gap-0.5">
          <span className="w-fit rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-400">{t.results.nearMiss}</span>
          {card.deviation_text && <p className="text-xs text-amber-900">{card.deviation_text}{t.results.nearSuffix}</p>}
        </div>
      )}
      <h4 className={`font-serif leading-snug ${large ? "text-xl" : "text-base"}`}>
        <Link
          href={from ? `/t/${card.trail_id}?von=${from}` : `/t/${card.trail_id}`}
          className={`underline-offset-2 hover:underline ${from ? "after:absolute after:inset-0" : ""}`}
        >
          {card.name}
        </Link>
      </h4>
      <p className="tabular-nums">{facts.join(" · ")}</p>
      {card.results.length > 0 && (
        <ul className="flex flex-col gap-0.5">
          {card.results.map((r, i) => (
            <Row key={r.kind + i} r={r} near={!!card.near_miss} deviation={i === firstViolated ? card.deviation_text : null} />
          ))}
        </ul>
      )}
      {(p.met.length > 0 || p.missing.length > 0 || p.avoided_hit.length > 0) && (
        <ul className="flex flex-col gap-0.5 text-xs">
          {p.met.length > 0 && <li>{t.results.metPrefs}: {name(p.met)}</li>}
          {p.missing.length > 0 && <li>{t.results.missingPrefs}: {name(p.missing)}</li>}
          {p.avoided_hit.length > 0 && <li>{t.results.avoidedHit}: {name(p.avoided_hit)}</li>}
        </ul>
      )}
      {from && (
        <p aria-hidden="true" className="mt-auto pt-1 text-sm font-medium text-wald">
          {t.results.detailsMap}
        </p>
      )}
      {/* above the card-wide link overlay, so it is clickable and does not navigate */}
      <MerkenButton kind="day_hike" title={card.name} payload={card} className="relative z-10 mt-1" />
    </article>
  );
}
