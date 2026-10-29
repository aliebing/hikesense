-- Read-only views for the web app (Task 10): geometry as GeoJSON and a
-- trail overview with a cover photo (first photo of the middle stage for
-- long-distance trails, so the variants get different covers; first photo
-- otherwise). security_invoker = true so the RLS
-- policies of the underlying tables apply (e.g. uploads stay hidden).

create view trails_geojson with (security_invoker = true) as
select id, st_asgeojson(geom, 6)::jsonb as geom
from trails;

create view stages_geojson with (security_invoker = true) as
select id, trail_id, seq, st_asgeojson(geom, 6)::jsonb as geom
from stages;

create view trail_overview with (security_invoker = true) as
select
  t.id,
  t.name,
  t.kind,
  t.length_km,
  t.ascent_m,
  t.descent_m,
  t.source_id,
  st_y(st_centroid(t.geom)) as center_lat,
  (select count(*) from stages s where s.trail_id = t.id)::int as stage_count,
  (select count(*) from photos p where p.trail_id = t.id)::int as photo_count,
  c.url as cover_url,
  c.thumb_url as cover_thumb_url,
  c.author as cover_author,
  c.license as cover_license,
  c.license_url as cover_license_url,
  c.page_url as cover_page_url
from trails t
left join lateral (
  select p.url, p.thumb_url, p.author, p.license, p.license_url, p.page_url
  from photos p
  left join stages s on s.id = p.stage_id
  where p.trail_id = t.id
  order by
    abs(s.seq - (select ceil(max(s2.seq) / 2.0) from stages s2 where s2.trail_id = t.id)) nulls last,
    s.seq,
    p.id
  limit 1
) c on true;

grant select on trails_geojson, stages_geojson, trail_overview to anon, authenticated;
