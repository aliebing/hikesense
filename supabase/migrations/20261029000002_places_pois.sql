-- Id scheme (both tables): OSM node +id, way -id, relation -(10^12 + id); no collisions.
-- Places (start points, peaks, lakes) and points of interest near trails, from OSM (ODbL).

create table places (
  id bigint primary key,  -- OSM node/way id, ways negative, relations -(10^12 + id)
  name text not null,
  kind text not null check (kind in ('town', 'village', 'hamlet', 'peak', 'lake')),
  geom geometry(Point, 4326) not null,
  source_id text not null references sources (id)
);

create table pois (
  id bigint primary key,  -- OSM node/way id, ways negative, relations -(10^12 + id)
  name text,
  kind text not null check (kind in ('viewpoint', 'peak', 'waterfall', 'food', 'hut', 'station')),
  geom geometry(Point, 4326) not null,
  source_id text not null references sources (id)
);

create table trail_pois (
  trail_id text references trails (id),
  poi_id bigint references pois (id),
  dist_m int,
  along_km numeric,
  primary key (trail_id, poi_id)
);

create index places_geom_idx on places using gist (geom);
create index places_name_idx on places (lower(name));
create index pois_geom_idx on pois using gist (geom);

alter table places enable row level security;
alter table pois enable row level security;
alter table trail_pois enable row level security;

create policy places_select on places for select to anon, authenticated using (true);
create policy pois_select on pois for select to anon, authenticated using (true);
create policy trail_pois_select on trail_pois for select to anon, authenticated using (true);

grant select on places, pois, trail_pois to anon, authenticated;
