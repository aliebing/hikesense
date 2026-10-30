-- Hand-curated list of hiking and running groups (spec §3 exception): name, kind, place, link, source, check date.
-- No persons, no dates or events. Public read; written only by `hikeall import-groups`.
create table groups (
  id text primary key,
  name text not null,
  kind text not null check (kind in ('wanderverein', 'lauftreff', 'alpenverein', 'sonstige')),
  place text not null,
  geom geometry(Point, 4326) not null,  -- centre of `place` from the places table
  url text not null,
  source_url text not null,
  checked_at date not null,
  status text not null check (status in ('vorschlag', 'geprüft')),
  note text
);

create index groups_geom_idx on groups using gist (geom);

alter table groups enable row level security;
create policy groups_select on groups for select to anon, authenticated using (true);

-- Supabase default privileges may grant more: reset, then select only (public list).
revoke all on groups from anon, authenticated;
grant select on groups to anon, authenticated;
