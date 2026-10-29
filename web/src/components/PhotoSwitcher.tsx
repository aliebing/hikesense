"use client";

import { useState } from "react";
import type { Photo } from "../lib/data";
import Attribution from "./Attribution";

/**
 * Full-bleed background photo with prev/next controls and the attribution of
 * the current photo. The background layer is fixed behind the page; the
 * controls render where the component is placed. Without photos (or when an
 * image fails to load) a forest-green gradient is shown instead.
 */
export default function PhotoSwitcher({ photos }: { photos: Photo[] }) {
  const [index, setIndex] = useState(0);
  const [broken, setBroken] = useState<Set<string>>(() => new Set());

  if (photos.length === 0) {
    return <div data-testid="panorama-fallback" aria-hidden className="wald-verlauf fixed inset-0 -z-10" />;
  }

  const current = photos[index % photos.length];
  const go = (step: number) => setIndex((i) => (i + step + photos.length) % photos.length);

  return (
    <>
      <div aria-hidden className="wald-verlauf fixed inset-0 -z-10">
        {!broken.has(current.url) && (
          // Plain <img>: the stored Commons URL is loaded by the browser, never proxied by the server.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={current.url}
            src={current.url}
            alt=""
            className="h-full w-full object-cover"
            onError={() => setBroken((b) => new Set(b).add(current.url))}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/5 to-black/65" />
      </div>
      <div className="flex max-w-full items-center gap-2 rounded-full bg-black/35 py-1 pr-3 pl-1 text-papier backdrop-blur-md">
        {photos.length > 1 && (
          <>
            <button
              type="button"
              aria-label="Vorheriges Bild"
              onClick={() => go(-1)}
              className="grid size-8 shrink-0 place-items-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier"
            >
              ‹
            </button>
            <span className="shrink-0 text-xs tabular-nums opacity-80">
              {(index % photos.length) + 1} / {photos.length}
            </span>
            <button
              type="button"
              aria-label="Nächstes Bild"
              onClick={() => go(1)}
              className="grid size-8 shrink-0 place-items-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier"
            >
              ›
            </button>
          </>
        )}
        <Attribution photo={current} className="min-w-0 pl-2" />
      </div>
    </>
  );
}
