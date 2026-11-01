-- Read-only view for the trail page (plan 5): points of interest linked to a trail
-- (food, hut, viewpoint, peak, waterfall; stations are left out) with coordinates.
-- security_invoker = true so the RLS policies of the underlying tables apply.

create view trail_pois_geo with (security_invoker = true) as
select
  tp.trail_id,
  p.id,
  p.name,
  p.kind,
  tp.dist_m,
  tp.along_km,
  st_x(p.geom) as lon,
  st_y(p.geom) as lat
from trail_pois tp
join pois p on p.id = tp.poi_id
where p.kind <> 'station';

grant select on trail_pois_geo to anon, authenticated;
