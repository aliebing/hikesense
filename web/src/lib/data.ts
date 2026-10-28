import type { LineString } from "geojson";
import { getSupabase } from "./supabase";

export type Photo = {
  url: string;
  thumb_url: string;
  author: string;
  license: string;
  license_url: string | null;
  page_url: string | null;
};

export type TrailSummary = {
  id: string;
  name: string;
  kind: "long_distance" | "day_hike";
  /** null when the source has no value — never replaced by 0 */
  length_km: number | null;
  ascent_m: number | null;
  descent_m: number | null;
  stage_count: number;
  /** latitude of the line's centroid, used to spread the home selection */
  center_lat: number | null;
  /** first photo (by stage order); null when the trail has no photo */
  cover: Photo | null;
};

export type Stage = {
  id: string;
  seq: number;
  name: string;
  start_name: string;
  end_name: string;
  length_km: number | null;
  ascent_m: number | null;
  descent_m: number | null;
  geom: LineString | null;
  /** photos taken along this stage (Westweg); empty for day hikes */
  photos: Photo[];
};

export type Source = { id: string; name: string; url: string | null; license: string | null };

export type TrailDetail = TrailSummary & {
  stages: Stage[];
  photos: Photo[];
  geom: LineString | null;
  sources: Source[];
};

export type OverviewRow = {
  id: string;
  name: string;
  kind: TrailSummary["kind"];
  length_km: number | string | null;
  ascent_m: number | null;
  descent_m: number | null;
  stage_count: number | null;
  center_lat: number | null;
  cover_url: string | null;
  cover_thumb_url: string | null;
  cover_author: string | null;
  cover_license: string | null;
  cover_license_url: string | null;
  cover_page_url: string | null;
  source_id: string | null;
};

const OVERVIEW_COLUMNS =
  "id,name,kind,length_km,ascent_m,descent_m,stage_count,center_lat,source_id," +
  "cover_url,cover_thumb_url,cover_author,cover_license,cover_license_url,cover_page_url";
const PHOTO_COLUMNS = "url,thumb_url,author,license,license_url,page_url,stage_id";

export function toSummary(r: OverviewRow): TrailSummary {
  const cover =
    r.cover_url && r.cover_author && r.cover_license
      ? {
          url: r.cover_url,
          thumb_url: r.cover_thumb_url ?? r.cover_url,
          author: r.cover_author,
          license: r.cover_license,
          license_url: r.cover_license_url,
          page_url: r.cover_page_url,
        }
      : null;
  return {
    id: r.id,
    name: r.name,
    kind: r.kind,
    length_km: num(r.length_km),
    ascent_m: num(r.ascent_m),
    descent_m: num(r.descent_m),
    stage_count: r.stage_count ?? 0,
    center_lat: r.center_lat,
    cover,
  };
}

/** numeric columns may arrive as string; missing stays null */
function num(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function fail(what: string, error: { message: string }): never {
  throw new Error(`${what}: ${error.message}`);
}

export async function getTrails(): Promise<TrailSummary[]> {
  const sb = getSupabase();
  const { data, error } = await sb.from("trail_overview").select(OVERVIEW_COLUMNS).order("name");
  if (error) fail("trail_overview", error);
  return (data as unknown as OverviewRow[]).map(toSummary);
}

export async function getTrail(id: string): Promise<TrailDetail | null> {
  const sb = getSupabase();
  const { data: row, error } = await sb
    .from("trail_overview")
    .select(OVERVIEW_COLUMNS)
    .eq("id", id)
    .maybeSingle();
  if (error) fail("trail_overview", error);
  if (!row) return null;
  const overview = row as unknown as OverviewRow;

  const [geo, stages, stageGeo, photos] = await Promise.all([
    sb.from("trails_geojson").select("geom").eq("id", id).maybeSingle(),
    sb
      .from("stages")
      .select("id,seq,name,start_name,end_name,length_km,ascent_m,descent_m,source_id")
      .eq("trail_id", id)
      .order("seq"),
    sb.from("stages_geojson").select("id,geom").eq("trail_id", id),
    sb.from("photos").select(PHOTO_COLUMNS).eq("trail_id", id).order("id"),
  ]);
  if (geo.error) fail("trails_geojson", geo.error);
  if (stages.error) fail("stages", stages.error);
  if (stageGeo.error) fail("stages_geojson", stageGeo.error);
  if (photos.error) fail("photos", photos.error);

  const stageRows = stages.data ?? [];
  const seqById = new Map(stageRows.map((s) => [s.id as string, s.seq as number]));
  const geomById = new Map((stageGeo.data ?? []).map((g) => [g.id as string, g.geom as LineString]));

  // Photos follow the route: stage order first, then trail-level photos.
  const photoRows = [...(photos.data ?? [])].sort(
    (a, b) =>
      (seqById.get(a.stage_id) ?? Number.MAX_SAFE_INTEGER) -
      (seqById.get(b.stage_id) ?? Number.MAX_SAFE_INTEGER),
  );
  const toPhoto = (p: (typeof photoRows)[number]): Photo => ({
    url: p.url,
    thumb_url: p.thumb_url ?? p.url,
    author: p.author,
    license: p.license,
    license_url: p.license_url,
    page_url: p.page_url,
  });

  const sourceIds = [
    ...new Set([overview.source_id, ...stageRows.map((s) => s.source_id as string | null)]),
  ].filter((s): s is string => !!s);
  let sources: Source[] = [];
  if (sourceIds.length) {
    const src = await sb.from("sources").select("id,name,url,license").in("id", sourceIds);
    if (src.error) fail("sources", src.error);
    sources = (src.data ?? []) as Source[];
  }

  return {
    ...toSummary(overview),
    geom: (geo.data?.geom as LineString | undefined) ?? null,
    photos: photoRows.map(toPhoto),
    sources,
    stages: stageRows.map((s) => ({
      id: s.id,
      seq: s.seq,
      name: s.name,
      start_name: s.start_name,
      end_name: s.end_name,
      length_km: num(s.length_km),
      ascent_m: num(s.ascent_m),
      descent_m: num(s.descent_m),
      geom: geomById.get(s.id) ?? null,
      photos: photoRows.filter((p) => p.stage_id === s.id).map(toPhoto),
    })),
  };
}

/** Day hikes eligible for the home selection: with a photo and a known position. */
export function photoPool(trails: TrailSummary[]): TrailSummary[] {
  return trails.filter((t) => t.kind === "day_hike" && t.cover !== null && t.center_lat !== null);
}

/**
 * Home selection: day hikes that have a photo, ordered north → south by the
 * centroid latitude (ties by id), then `n` picks evenly spaced over that list,
 * so the selection covers the whole Black Forest and is deterministic.
 */
export function pickSpread(trails: TrailSummary[], n: number): TrailSummary[] {
  const pool = photoPool(trails).sort((a, b) => b.center_lat! - a.center_lat! || a.id.localeCompare(b.id));
  if (pool.length <= n) return pool;
  if (n <= 1) return pool.slice(0, n);
  return Array.from({ length: n }, (_, i) => pool[Math.round((i * (pool.length - 1)) / (n - 1))]);
}
