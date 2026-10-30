-- Read-only view of the groups list with coordinates, for the trail page ("Gruppen in der Nähe").
-- security_invoker = true so the RLS policy of `groups` applies.
create view groups_geo with (security_invoker = true) as
select id, name, kind, place, url, source_url, checked_at, status, st_x(geom) as lon, st_y(geom) as lat
from groups;

grant select on groups_geo to anon, authenticated;
