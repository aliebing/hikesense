import Link from "next/link";
import type { Photo, TrailDetail, TrailSummary } from "../lib/data";
import { din33466Hours, duration, hm, hmDown, km } from "../lib/format";
import Attribution from "./Attribution";

/** Key figures separated by " · "; each figure stays on one line. */
export function Facts({ items, className = "" }: { items: string[]; className?: string }) {
  return (
    <p className={`tabular-nums ${className}`}>
      {items.map((f, i) => (
        <span key={f + i}>
          {i > 0 && " · "}
          <span className="whitespace-nowrap">{f}</span>
        </span>
      ))}
    </p>
  );
}

type CardProps = {
  eyebrow: string;
  title: string;
  href?: string;
  photo: Photo | null;
  facts: string[];
};

/** Image card: photo (with attribution) or gradient, title and key figures. */
export function ImageCard({ eyebrow, title, href, photo, facts }: CardProps) {
  return (
    <article className="relative flex w-64 shrink-0 snap-start flex-col overflow-hidden rounded-2xl bg-papier text-wald-dunkel shadow-lg sm:w-72">
      <div className="wald-verlauf relative aspect-[16/9]">
        {photo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photo.thumb_url} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 px-4 pt-3 pb-2">
        <p className="text-xs font-medium tracking-wider text-wald uppercase">{eyebrow}</p>
        <h3 className="font-serif text-lg leading-snug">
          {href ? (
            <Link href={href} className="after:absolute after:inset-0 hover:underline focus-visible:underline">
              {title}
            </Link>
          ) : (
            title
          )}
        </h3>
        <Facts items={facts} className="text-sm text-wald-dunkel/80" />
        {photo && <Attribution photo={photo} className="relative z-10 mt-auto pt-2 text-wald-dunkel/70" />}
      </div>
    </article>
  );
}

function figures(x: { length_km: number; ascent_m: number; descent_m: number }, withTime = true): string[] {
  const f = [km(x.length_km), hm(x.ascent_m), hmDown(x.descent_m)];
  if (withTime) f.push(duration(din33466Hours(x.length_km, x.ascent_m, x.descent_m)));
  return f;
}

export function TrailCard({ trail }: { trail: TrailSummary }) {
  const longDistance = trail.kind === "long_distance";
  return (
    <ImageCard
      eyebrow={longDistance ? `Fernweg · ${trail.stage_count} Etappen` : "Tagestour"}
      title={trail.name}
      href={`/t/${trail.id}`}
      photo={trail.cover}
      facts={figures(trail, !longDistance)}
    />
  );
}

export function CardRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <ul
      aria-label={label}
      className="scrollbar-schmal -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:-mx-6 sm:px-6 [&>li]:flex"
    >
      {children}
    </ul>
  );
}

/** Bottom cards of layout A: one card per stage (long-distance trail) or one card (day hike). */
export default function StageCards({ trail }: { trail: TrailDetail }) {
  if (trail.stages.length === 0) {
    return (
      <CardRow label="Tour">
        <li>
          <ImageCard eyebrow="Tagestour" title={trail.name} photo={trail.cover} facts={figures(trail)} />
        </li>
      </CardRow>
    );
  }
  return (
    <CardRow label="Etappen">
      {trail.stages.map((s) => (
        <li key={s.id}>
          <ImageCard
            eyebrow={`Etappe ${s.seq}`}
            title={`${s.start_name} – ${s.end_name}`}
            photo={s.photos[0] ?? null}
            facts={figures(s)}
          />
        </li>
      ))}
    </CardRow>
  );
}
