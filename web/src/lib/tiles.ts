import type { TourCard } from "./chat";
import { coverOf } from "./chatState";
import type { Photo, TrailSummary } from "./data";

export type Tile = {
  /** trail id */
  id: string;
  name: string;
  /** null: green surface with the name */
  photo: Photo | null;
  /** null = pale and not clickable */
  match: null | { deviation: string | null };
};

const MAX_MATCHES = 5;

function paleTile(t: TrailSummary): Tile {
  return { id: t.id, name: t.name, photo: t.cover, match: null };
}

/**
 * rows × perRow tiles, no trail twice; matches (≤ 5, in card order) are placed round-robin over
 * the rows, each replacing a pale tile (or turning its own pool tile clear); a match not in the
 * pool is built from its TourCard. Pool order (pickSpread) is kept, so the result is deterministic.
 */
export function arrangeTiles(pool: TrailSummary[], matches: TourCard[], rows: number, perRow: number): Tile[][] {
  const seen = new Set<string>();
  const unique = pool.filter((t) => !seen.has(t.id) && !!seen.add(t.id)).slice(0, rows * perRow);
  const grid: Tile[][] = [];
  for (let r = 0; r < rows; r++) {
    const chunk = unique.slice(r * perRow, (r + 1) * perRow).map(paleTile);
    if (chunk.length) grid.push(chunk);
  }
  if (grid.length === 0 && matches.length) grid.push([]);

  const picked = matches.filter((c, i, a) => a.findIndex((d) => d.trail_id === c.trail_id) === i).slice(0, MAX_MATCHES);
  // first mark matches that are already in the pool: they stay in place and must not be overwritten
  const missing: [TourCard, number][] = [];
  picked.forEach((card, i) => {
    const existing = grid.flat().find((t) => t.id === card.trail_id);
    if (existing) existing.match = { deviation: card.deviation_text };
    else missing.push([card, i]);
  });
  missing.forEach(([card, i]) => {
    const match = { deviation: card.deviation_text };
    const tile: Tile = { id: card.trail_id, name: card.name, photo: coverOf(card), match };
    // round-robin start row; fall through to the next rows when it has no pale tile left
    for (let k = 0; k < grid.length; k++) {
      const row = grid[(i + k) % grid.length];
      // spread within the row: later matches in the same row take a different place
      const want = Math.floor(i / grid.length) * 3 + 1;
      for (let j = 0; j < row.length; j++) {
        const at = (want + j) % row.length;
        if (!row[at].match) {
          row[at] = tile;
          return;
        }
      }
    }
    grid[i % grid.length].push(tile);
  });
  return grid;
}
