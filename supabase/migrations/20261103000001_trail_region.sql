-- Region of a trail; all existing trails are Black Forest.
alter table trails add column region text not null default 'black_forest'
  check (region in ('black_forest','palatinate','lake_constance'));
-- New rows must set the region explicitly.
alter table trails alter column region drop default;
