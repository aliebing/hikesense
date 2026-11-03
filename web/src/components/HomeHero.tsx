import type { ReactNode } from "react";
import { useT } from "../i18n";
import { LogoMark, Wordmark } from "./Logo";

/**
 * The start page's landscape photo (the owner's own image, no credit needed), full width behind
 * the top of the page and darkened towards the text, header and the dark green below.
 * Sits in the PageFrame's `relative isolate` box like Backdrop.
 */
export function HeroBackdrop({ shown = true }: { /** false: invisible, fades in once true */ shown?: boolean }) {
  return (
    <div
      aria-hidden="true"
      data-hero-backdrop
      className={`pointer-events-none absolute inset-x-0 top-0 -z-10 h-[max(100svh,46rem)] overflow-hidden transition-opacity duration-500 ${shown ? "" : "opacity-0"}`}
    >
      <picture>
        <source media="(max-width: 900px)" srcSet="/hero/start-900.webp" />
        <img src="/hero/start-1920.webp" alt="" fetchPriority="high" className="h-full w-full object-cover object-[58%_40%]" />
      </picture>
      <div className="hero-shade absolute inset-0" />
    </div>
  );
}

/** Logo, wordmark, tagline between two thin green lines, subtitle. */
export function HeroBrand() {
  const f = useT().frame;
  const t = useT().home.hero;
  return (
    <section className="hero-text flex flex-col items-center text-center">
      <LogoMark className="h-20 w-auto sm:h-28" />
      <h1 className="mt-1.5 text-[2.9rem] leading-none sm:text-7xl">
        <Wordmark />
      </h1>
      <p className="mt-3 flex items-center gap-3 font-brand text-base font-medium tracking-[0.04em] text-papier sm:mt-4 sm:gap-5 sm:text-2xl">
        <span aria-hidden="true" className="h-0.5 w-8 rounded-full bg-sense sm:w-16" />
        {f.tagline}
        <span aria-hidden="true" className="h-0.5 w-8 rounded-full bg-sense sm:w-16" />
      </p>
      <p className="mt-3 max-w-[34rem] text-pretty text-[0.95rem] leading-relaxed text-papier/90 sm:mt-4 sm:text-lg">{t.subtitle}</p>
    </section>
  );
}

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const ICONS: Record<"routes" | "lodging" | "weather" | "ai", ReactNode> = {
  routes: (
    <>
      <path {...stroke} d="M7 16.5s-4-4-4-7.2a4 4 0 0 1 8 0c0 3.2-4 7.2-4 7.2z" />
      <circle {...stroke} cx="7" cy="9.3" r="1.3" />
      <path {...stroke} d="M17 11.5s-3-3-3-5.3a3 3 0 0 1 6 0c0 2.3-3 5.3-3 5.3z" />
      <path {...stroke} d="M7 20h7.5a2.25 2.25 0 0 0 0-4.5H17" strokeDasharray="0.1 2.6" strokeWidth={2} />
    </>
  ),
  lodging: (
    <>
      <path {...stroke} d="M3 5.5v14M3 15.5h18v4M21 15.5V13a3 3 0 0 0-3-3h-7.5v5.5" />
      <circle {...stroke} cx="6.8" cy="12" r="1.8" />
    </>
  ),
  weather: (
    <>
      <circle {...stroke} cx="16" cy="8" r="2.8" />
      <path {...stroke} d="M16 2.6v1M20.4 4l-.7.7M21.6 8h-1M11.6 4l.7.7" />
      <path {...stroke} d="M6.5 19.5h9a3.4 3.4 0 0 0 .3-6.8 5 5 0 0 0-9.4 .9 3 3 0 0 0 .1 5.9z" />
    </>
  ),
  ai: (
    <>
      <path {...stroke} d="M10 3.5l1.5 4.6 4.6 1.5-4.6 1.5L10 15.7l-1.5-4.6-4.6-1.5 4.6-1.5z" />
      <path {...stroke} d="M18 13.5l.8 2.1 2.1.8-2.1.8-.8 2.1-.8-2.1-2.1-.8 2.1-.8z" />
      <path {...stroke} d="M18.5 3.5v3M17 5h3" />
    </>
  ),
};

/** What the app does, as four quiet tiles: icon in a rounded dark green square, label below. */
export function HeroFeatures({ className = "" }: { className?: string }) {
  const t = useT().home.hero;
  const items = [
    ["routes", t.routes],
    ["lodging", t.lodging],
    ["weather", t.weather],
    ["ai", t.ai],
  ] as const;
  return (
    <ul aria-label={t.features} className={`grid w-full max-w-3xl grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-4 sm:gap-x-6 ${className}`}>
      {items.map(([key, label]) => (
        <li key={key} className="hero-text flex flex-col items-center gap-2 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-2xl md:h-16 md:w-16 bg-panel/60 text-sense shadow-[0_6px_18px_rgb(0_0_0/0.35)] ring-1 ring-sense/25 sm:h-14 sm:w-14">
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6 sm:h-7 sm:w-7 md:h-8 md:w-8">
              {ICONS[key]}
            </svg>
          </span>
          <span className="max-w-[11rem] text-balance text-sm leading-snug text-papier sm:text-[0.95rem]">{label}</span>
        </li>
      ))}
    </ul>
  );
}
