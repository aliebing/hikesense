create extension if not exists postgis;

create table sources (
  id text primary key,
  name text,
  url text,
  license text,
  retrieved_at date
);

create table trails (
  id text primary key,
  name text,
  kind text check (kind in ('long_distance', 'day_hike')),
  roundtrip boolean,
  osm_relation_id bigint,
  length_km numeric,
  ascent_m int,
  descent_m int,
  profile jsonb,  -- [[km, elevation_m], ...], max 300 points
  geom geometry(LineString, 4326),
  source_id text references sources (id)
);

create table stages (
  id text primary key,
  trail_id text references trails (id),
  seq int,
  name text,
  start_name text,
  end_name text,
  length_km numeric,
  ascent_m int,
  descent_m int,
  profile jsonb,  -- [[km, elevation_m], ...], max 300 points
  geom geometry(LineString, 4326),
  source_id text references sources (id),
  unique (trail_id, seq)
);

create table lodgings (
  id bigint primary key,  -- OSM node/way id, ways negative
  name text,
  kind text,
  website text,
  geom geometry(Point, 4326),
  source_id text references sources (id)
);

create table trail_lodgings (
  trail_id text references trails (id),
  lodging_id bigint references lodgings (id),
  dist_m int,
  along_km numeric,
  primary key (trail_id, lodging_id)
);

create table photos (
  id bigserial primary key,
  trail_id text references trails (id),
  stage_id text references stages (id),
  source text check (source in ('commons', 'upload')),
  url text,
  thumb_url text,
  author text not null,
  license text not null,
  license_url text,
  page_url text,
  geom geometry(Point, 4326),
  owner uuid,
  unique (trail_id, url)
);

create index trails_geom_idx on trails using gist (geom);
create index stages_geom_idx on stages using gist (geom);
create index lodgings_geom_idx on lodgings using gist (geom);
create index photos_geom_idx on photos using gist (geom);

alter table sources enable row level security;
alter table trails enable row level security;
alter table stages enable row level security;
alter table lodgings enable row level security;
alter table trail_lodgings enable row level security;
alter table photos enable row level security;

create policy sources_select on sources for select to anon, authenticated using (true);
create policy trails_select on trails for select to anon, authenticated using (true);
create policy stages_select on stages for select to anon, authenticated using (true);
create policy lodgings_select on lodgings for select to anon, authenticated using (true);
create policy trail_lodgings_select on trail_lodgings for select to anon, authenticated using (true);
create policy photos_select on photos for select to anon, authenticated
  using (source <> 'upload');

grant select on all tables in schema public to anon, authenticated;
