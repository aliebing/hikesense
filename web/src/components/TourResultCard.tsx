import Link from "next/link";
import type { ConstraintResult, Labels, TourCard } from "../lib/chat";
import { duration } from "../lib/format";
import { coverOf } from "../lib/chatState";
import Attribution from "./Attribution";
import MerkenButton from "./MerkenButton";

const nf1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });

export const LABEL: Record<string, string> = {
  length_km: "Länge",
  ascent_m: "Höhenmeter",
  duration_h: "Dauer",
  radius_km: "Entfernung",
  roundtrip: "Rundweg",
};

export const UNIT: Record<string, string> = { length_km: "km", ascent_m: "Hm", duration_h: "h", radius_km: "km" };

function Row({ r, deviation }: { r: ConstraintResult; deviation: string | null }) {
  const label = LABEL[r.kind] ?? r.kind;
  const bound = UNIT[r.kind] && r.bound ? `${r.bound} ${UNIT[r.kind]}` : r.bound;
  if (r.ok === true) {
    return (
      <li>
        <span aria-label="erfüllt">✓</span> {label}: {bound}
      </li>
    );
  }
  if (r.ok === false) {
    return (
      <li className="text-red-800">
        <span aria-label="verletzt">✗</span> {label}: {deviation ?? `nicht erfüllt (${bound})`}
      </li>
    );
  }
  return (
    <li className="text-wald-dunkel/80">
      <span aria-label="unbekannt">?</span> {label}: unbekannt, nicht prüfbar ({bound})
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
  const large = size === "large";
  const name = (ids: string[]) => ids.map((t) => labels[t] ?? t).join(", ");
  const photo = coverOf(card);
  const firstViolated = card.results.findIndex((r) => r.ok === false);
  const p = card.preference;
  let time: string | null = null;
  if (card.duration_h !== null) time = `Zeit: ${duration(card.duration_h)}`;
  else if (runWithoutPace) time = "Zeit: Tempo angeben";
  const facts = [
    card.length_km === null ? "Länge: unbekannt" : `${nf1.format(card.length_km)} km`,
    card.ascent_m === null ? "Höhenmeter: unbekannt" : `↑ ${nf0.format(card.ascent_m)} m`,
    ...(time ? [time] : []),
    card.distance_km === null ? "im Gebiet" : `Entfernung: ${nf1.format(card.distance_km)} km`,
  ];
  return (
    <article
      className={`flex flex-col gap-1 rounded-xl p-3 text-sm text-wald-dunkel ${
        card.near_miss ? "ring-2 ring-amber-400 " : ""
      }${
        from ? "relative bg-papier/80 backdrop-blur-sm shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl focus-within:ring-2 focus-within:ring-amber-400" : "bg-papier/95"
      }`}
    >
      {!photo && large && (
        <div aria-hidden="true" className="grid h-48 w-full place-items-center rounded-lg wald-verlauf p-3 text-center font-serif text-lg text-papier">
          {card.name}
        </div>
      )}
      {photo && (
        <div className="flex flex-col gap-0.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo.thumb_url} alt="" loading="lazy" className={`${large ? "h-48" : "h-24"} w-full rounded-lg object-cover`} />
          {/* above the card-wide link so its licence links stay clickable */}
          <Attribution photo={photo} className="relative z-10 text-wald-dunkel/70" />
        </div>
      )}
      {card.near_miss && (
        <div className="flex flex-col gap-0.5">
          <span className="w-fit rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-400">Knapp daneben</span>
          {card.deviation_text && <p className="text-xs text-amber-900">{card.deviation_text} – sonst passt alles</p>}
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
      {from && (
        <p aria-hidden="true" className="mt-auto pt-1 text-sm font-medium text-wald">
          Details und Karte →
        </p>
      )}
      {/* above the card-wide link overlay, so it is clickable and does not navigate */}
      <MerkenButton kind="day_hike" title={card.name} payload={card} className="relative z-10 mt-1" />
    </article>
  );
}
