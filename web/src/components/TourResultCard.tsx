import Link from "next/link";
import type { ConstraintResult, Labels, TourCard } from "../lib/chat";
import { duration } from "../lib/format";
import Attribution from "./Attribution";

const nf1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });

const LABEL: Record<string, string> = {
  length_km: "Länge",
  ascent_m: "Höhenmeter",
  duration_h: "Dauer",
  radius_km: "Entfernung",
  roundtrip: "Rundweg",
};

function Row({ r, deviation }: { r: ConstraintResult; deviation: string | null }) {
  const label = LABEL[r.kind] ?? r.kind;
  if (r.ok === true) {
    return (
      <li>
        <span aria-label="erfüllt">✓</span> {label}: {r.bound}
      </li>
    );
  }
  if (r.ok === false) {
    return (
      <li className="text-red-800">
        <span aria-label="verletzt">✗</span> {label}: {deviation ?? `nicht erfüllt (${r.bound})`}
      </li>
    );
  }
  return (
    <li className="text-wald-dunkel/80">
      <span aria-label="unbekannt">?</span> {label}: unbekannt, nicht prüfbar ({r.bound})
    </li>
  );
}

/** One proposed tour with its key figures, per-condition verdicts and preferences. */
export default function TourResultCard({
  card,
  runWithoutPace = false,
  labels = {},
}: {
  card: TourCard;
  runWithoutPace?: boolean;
  labels?: Labels;
}) {
  const name = (ids: string[]) => ids.map((t) => labels[t] ?? t).join(", ");
  const photo =
    card.cover_thumb_url && card.cover_author && card.cover_license
      ? {
          url: card.cover_thumb_url,
          thumb_url: card.cover_thumb_url,
          author: card.cover_author,
          license: card.cover_license,
          license_url: card.cover_license_url,
          page_url: card.cover_page_url,
        }
      : null;
  const firstViolated = card.results.findIndex((r) => r.ok === false);
  const p = card.preference;
  let time: string | null = null;
  if (card.duration_h !== null) time = `Zeit: ${duration(card.duration_h)}`;
  else if (runWithoutPace) time = "Zeit: Tempo angeben";
  const facts = [
    card.length_km === null ? "Länge: unbekannt" : `${nf1.format(card.length_km)} km`,
    card.ascent_m === null ? "Höhenmeter: unbekannt" : `↑ ${nf0.format(card.ascent_m)} m`,
    ...(time ? [time] : []),
    `Entfernung: ${nf1.format(card.distance_km)} km`,
  ];
  return (
    <article className="flex flex-col gap-1 rounded-xl bg-papier/95 p-3 text-sm text-wald-dunkel">
      {photo && (
        <div className="flex flex-col gap-0.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo.thumb_url} alt="" loading="lazy" className="h-24 w-full rounded-lg object-cover" />
          <Attribution photo={photo} className="text-wald-dunkel/70" />
        </div>
      )}
      <h4 className="font-serif text-base leading-snug">
        <Link href={`/t/${card.trail_id}`} className="underline-offset-2 hover:underline">
          {card.name}
        </Link>
      </h4>
      <p className="tabular-nums">{facts.join(" · ")}</p>
      {card.results.length > 0 && (
        <ul className="flex flex-col gap-0.5">
          {card.results.map((r, i) => (
            <Row key={r.kind + i} r={r} deviation={i === firstViolated ? card.deviation_text : null} />
          ))}
        </ul>
      )}
      {(p.met.length > 0 || p.missing.length > 0 || p.avoided_hit.length > 0) && (
        <ul className="flex flex-col gap-0.5 text-xs">
          {p.met.length > 0 && <li>Erfüllte Vorlieben: {name(p.met)}</li>}
          {p.missing.length > 0 && <li>Fehlende Vorlieben: {name(p.missing)}</li>}
          {p.avoided_hit.length > 0 && <li>Vermiedenes vorhanden: {name(p.avoided_hit)}</li>}
        </ul>
      )}
    </article>
  );
}
