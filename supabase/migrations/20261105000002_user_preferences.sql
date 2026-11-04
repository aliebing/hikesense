-- Standing preferences of a signed-in user ("Vorlieben"): per feature tag prefer or avoid, weight 1–5.
-- A blocked account (is_active_user, 20261104000001) can read but not change them.
-- They only re-sort day-hike results (like a chat wish), never filter; a wish written in the chat wins.
create table user_preferences (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  tag_id text not null,
  mode text not null check (mode in ('prefer', 'avoid')),
  weight int not null default 2 check (weight between 1 and 5),
  updated_at timestamptz not null default now(),
  primary key (user_id, tag_id)
);

alter table user_preferences enable row level security;
create policy user_preferences_select on user_preferences for select to authenticated using (user_id = auth.uid());
create policy user_preferences_insert on user_preferences for insert to authenticated with check (user_id = auth.uid() and public.is_active_user());
create policy user_preferences_update on user_preferences for update to authenticated using (user_id = auth.uid() and public.is_active_user()) with check (user_id = auth.uid());
create policy user_preferences_delete on user_preferences for delete to authenticated using (user_id = auth.uid() and public.is_active_user());
revoke all on user_preferences from anon, authenticated;
grant select, insert, update, delete on user_preferences to authenticated;
