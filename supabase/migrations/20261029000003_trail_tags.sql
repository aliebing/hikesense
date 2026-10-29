-- Feature and surface tags per trail (controlled vocabulary, see backend/src/hikeall/tags).
-- Place and area tags are checked spatially at query time and are not stored here.
create table trail_tags (
  trail_id text not null references trails (id) on delete cascade,
  tag_id text not null,
  primary key (trail_id, tag_id)
);

create index trail_tags_tag_idx on trail_tags (tag_id);

alter table trail_tags enable row level security;
create policy trail_tags_select on trail_tags for select to anon, authenticated using (true);
grant select on trail_tags to anon, authenticated;
