-- Share of trail length per surface class and per way type, from OSM way tags.
-- {"paved": 0.4, "unknown": 0.6}; null = not computed. Stages get none (Plan 3, if needed).
alter table trails
  add column surface_shares jsonb,
  add column way_type_shares jsonb;
