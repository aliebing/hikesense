import Link from "next/link";
import type { ConstraintResult, TourCard } from "../lib/chat";
import { duration, hm, km } from "../lib/format";

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
export default function TourResultCard({ card, runWithoutPace = false }: { card: TourCard; runWithoutPace?: boolean }) {
  const firstViolated = card.results.findIndex((r) => r.ok === false);
  const p = card.preference;
  let time: string | null = null;
  if (card.duration_h !== null) time = `Zeit: ${duration(card.duration_h)}`;
  else if (runWithoutPace) time = "Zeit: Tempo angeben";
  const facts = [km(card.length_km), hm(card.ascent_m), ...(time ? [time] : []), `Entfernung: ${km(card.distance_km)}`];
  return (
    <article className="flex flex-col gap-1 rounded-xl bg-papier/95 p-3 text-sm text-wald-dunkel">
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
          {p.met.length > 0 && <li>Erfüllte Vorlieben: {p.met.join(", ")}</li>}
          {p.missing.length > 0 && <li>Fehlende Vorlieben: {p.missing.join(", ")}</li>}
          {p.avoided_hit.length > 0 && <li>Vermiedenes vorhanden: {p.avoided_hit.join(", ")}</li>}
        </ul>
      )}
    </article>
  );
}
