import { useId } from "react";

/** Brand colours of the HikeSense mark. */
export const BRAND = {
  sunFrom: "#f6b04a",
  sunTo: "#e47f1c",
  mountainLight: "#ffffff",
  mountainDark: "#0f3a1f",
  trailLight: "#a6dc7a",
  trailDark: "#4f8f1c",
};

// One geometry for the web component and the generated PWA icons (scripts/make-icons.mjs).
export const MARK_VIEWBOX = "0 -8 120 92";
export const SUN_PATH = "M21 44 A37 37 0 1 1 93 38";
export const MOUNTAIN_PATH = "M3 68 L36 43 L44 52 L67 28 L81 44 L85 42 L117 71";
export const TRAIL_PATH = "M66 50 C 58 53, 54 55, 60 58 C 67 61, 62 66, 52 68 C 42 70, 38 74, 32 79";

/**
 * The HikeSense mark: an orange sun arc over a mountain outline, with a small winding trail.
 * `light` (white mountain) stands on the dark hero and the header; `dark` on light ground.
 * Decorative: the wordmark next to it carries the name.
 */
export function LogoMark({
  variant = "light",
  trail = true,
  className,
}: {
  variant?: "light" | "dark";
  trail?: boolean;
  className?: string;
}) {
  const id = useId().replace(/:/g, "");
  const light = variant === "light";
  return (
    <svg viewBox={MARK_VIEWBOX} aria-hidden="true" focusable="false" className={className} data-logo-mark={variant}>
      <defs>
        <linearGradient id={`sun-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={BRAND.sunFrom} />
          <stop offset="1" stopColor={BRAND.sunTo} />
        </linearGradient>
      </defs>
      <path d={SUN_PATH} fill="none" stroke={`url(#sun-${id})`} strokeWidth="5" strokeLinecap="round" />
      <path
        d={MOUNTAIN_PATH}
        fill="none"
        stroke={light ? BRAND.mountainLight : BRAND.mountainDark}
        strokeWidth="5.5"
        strokeLinejoin="miter"
        strokeLinecap="round"
      />
      {trail && (
        <path
          d={TRAIL_PATH}
          fill="none"
          stroke={light ? BRAND.trailLight : BRAND.trailDark}
          strokeWidth="3"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

/** The wordmark as real text: “Hike” in white (or dark green), “Sense” in light green. */
export function Wordmark({ variant = "light", className = "" }: { variant?: "light" | "dark"; className?: string }) {
  return (
    <span className={`font-brand font-extrabold tracking-[-0.02em] ${className}`}>
      {/* the two colours are visual only; assistive tech reads one word */}
      <span className="sr-only">HikeSense</span>
      <span aria-hidden="true" className={variant === "light" ? "text-white" : "text-[#0f3a1f]"}>Hike</span>
      <span aria-hidden="true" className={variant === "light" ? "text-sense" : "text-[#4f8f1c]"}>Sense</span>
    </span>
  );
}
