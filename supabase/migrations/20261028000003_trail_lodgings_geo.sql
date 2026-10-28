-- Read-only view for the trail map (Task 11): lodgings near a trail with
-- their distance (trail_lodgings.dist_m, as imported) and coordinates.
-- security_invoker = true so the RLS policies of the underlying tables apply.

create view trail_lodgings_geo with (security_invoker = true) as
select
  tl.trail_id,
  l.id,
  l.name,
  l.kind,
  l.website,
  tl.dist_m,
  tl.along_km,
  st_x(l.geom) as lon,
  st_y(l.geom) as lat
from trail_lodgings tl
join lodgings l on l.id = tl.lodging_id
where l.geom is not null;

grant select on trail_lodgings_geo to anon, authenticated;
