"use client";

import { useState } from "react";
import type { Photo } from "../lib/data";

// A soft-edged rectangle (not an oval): opaque in the middle, fading gently at the sides and
// the bottom. Two linear masks, intersected.
const SIDES =
  "linear-gradient(to right, transparent 0%, rgb(0 0 0 / 0.25) 9%, rgb(0 0 0 / 0.65) 18%, #000 27%, #000 73%, rgb(0 0 0 / 0.65) 82%, rgb(0 0 0 / 0.25) 91%, transparent 100%)";
const BOTTOM = "linear-gradient(to bottom, #000 0%, #000 45%, rgb(0 0 0 / 0.55) 65%, rgb(0 0 0 / 0.2) 80%, transparent 92%)";
const MASK = `${SIDES}, ${BOTTOM}`;

/**
 * A landscape photo behind the page: opaque in the middle, softened into the dark green towards
 * the edges. Decorative only (aria-hidden); the caller shows the photo's credit.
 * Sits in the PageFrame's `relative isolate` box, never fixed to the viewport.
 */
export default function Backdrop({ photo }: { photo: Photo | null }) {
  const [broken, setBroken] = useState<string | null>(null);
  if (!photo || broken === photo.url) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[115vh] overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={photo.url}
        alt=""
        onError={() => setBroken(photo.url)}
        className="h-full w-full object-cover object-[center_65%]"
        style={{ maskImage: MASK, WebkitMaskImage: MASK, maskComposite: "intersect", WebkitMaskComposite: "source-in" }}
      />
    </div>
  );
}
