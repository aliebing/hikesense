-- Plans a signed-in user saved ("Merken"): a day-hike TourCard or a MultidayPlan, stored exactly as sent.
create table saved_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind text not null check (kind in ('day_hike', 'multiday')),
  title text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create index saved_plans_user_idx on saved_plans (user_id, created_at desc);

alter table saved_plans enable row level security;
create policy saved_plans_select on saved_plans for select to authenticated using (user_id = auth.uid());
create policy saved_plans_insert on saved_plans for insert to authenticated with check (user_id = auth.uid());
create policy saved_plans_delete on saved_plans for delete to authenticated using (user_id = auth.uid());
-- no access for anon (Supabase default privileges would grant it) and no update (a plan is saved or deleted, never edited)
revoke all on saved_plans from anon;
grant select, insert, delete on saved_plans to authenticated;
