"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { TourCard } from "../lib/chat";
import type { TrailSummary } from "../lib/data";
import { arrangeTiles, type Tile } from "../lib/tiles";

const ROWS = 3;
const PER_ROW = 8;
const DURATIONS = [70, 85, 60]; // seconds per loop, a little different per row

function TileFace({ tile }: { tile: Tile }) {
  return (
    <>
      {tile.photo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={tile.photo.thumb_url} alt="" draggable={false} className="absolute inset-0 h-full w-full object-cover" />
      ) : (
        <span className="absolute inset-0 grid place-items-center wald-verlauf p-3 text-center font-serif text-sm">{tile.name}</span>
      )}
      {(tile.photo || tile.match?.deviation) && (
        <span className="absolute inset-x-0 bottom-0 grid gap-0.5 bg-black/55 px-2 py-1 text-[11px] leading-snug">
          {tile.photo && <span className="truncate font-medium">{tile.name}</span>}
          {tile.match?.deviation && <span className="text-papier/90">{tile.match.deviation}</span>}
        </span>
      )}
    </>
  );
}

const BOX = "relative h-28 w-44 shrink-0 overflow-hidden rounded-lg border transition-all duration-700 sm:h-32 sm:w-52";

function TileView({ tile, copy }: { tile: Tile; copy: 0 | 1 }) {
  if (!tile.match) {
    return (
      <li aria-hidden="true" className={`${BOX} border-transparent opacity-35 saturate-50`}>
        <TileFace tile={tile} />
      </li>
    );
  }
  // matches are links only in the first copy of the row; the second copy is a hidden twin
  return (
    <li className={`${BOX} border-papier/70 opacity-100 shadow-lg`}>
      <Link
        href={`/t/${tile.id}`}
        aria-label={tile.name}
        tabIndex={copy === 0 ? undefined : -1}
        aria-hidden={copy === 0 ? undefined : true}
        className="absolute inset-0 block focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-papier"
      >
        <TileFace tile={tile} />
      </Link>
    </li>
  );
}

/** True below `sm`, where there is one row with the matches first. */
export function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(max-width: 639px)");
    setNarrow(mq.matches);
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return narrow;
}

/** The rows TileRows shows; also used to list exactly these photos in the credits. */
export function layoutTiles(pool: TrailSummary[], matches: TourCard[], narrow: boolean): Tile[][] {
  if (!narrow) return arrangeTiles(pool, matches, ROWS, PER_ROW);
  const [row = []] = arrangeTiles(pool, matches, 1, PER_ROW * 2);
  return [[...row.filter((t) => t.match), ...row.filter((t) => !t.match)]];
}

/**
 * Drifting rows of tour tiles behind the chat. Tiles are pale and not clickable until the chat's
 * last result list contains them; those turn clear and link to /t/<id>. Below `sm` there is one
 * row with the matches first.
 */
export default function TileRows({ pool, matches }: { pool: TrailSummary[]; matches: TourCard[] }) {
  const narrow = useNarrow();
  const rows = useMemo(() => layoutTiles(pool, matches, narrow), [pool, matches, narrow]);

  return (
    <div className="grid gap-3 overflow-hidden">
      {rows.map((row, r) => (
        <div
          key={r}
          className={`hike-drift flex w-max ${r % 2 ? "hike-drift-back" : ""} ${r > 0 ? "hidden sm:flex" : ""}`}
          style={{ animationDuration: `${DURATIONS[r % DURATIONS.length]}s` }}
        >
          {[0, 1].map((copy) => (
            <ul key={copy} className="flex gap-3 pr-3" aria-hidden={copy === 1 ? true : undefined}>
              {row.map((tile) => (
                <TileView key={tile.id} tile={tile} copy={copy as 0 | 1} />
              ))}
            </ul>
          ))}
        </div>
      ))}
    </div>
  );
}
