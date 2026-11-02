-- One profile per auth user; carries the app role. Clients may only read their own row: the role
-- is read by the backend (as table owner) and must never be writable from the browser.
create table profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  email text,
  role text not null default 'user' check (role in ('user', 'admin')),
  created_at timestamptz not null default now()
);

create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id, email) values (new.id, new.email) on conflict do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill users that signed up before this migration.
insert into profiles (user_id, email) select id, email from auth.users on conflict do nothing;

alter table profiles enable row level security;
create policy profiles_select on profiles for select to authenticated using (user_id = auth.uid());

-- Supabase default privileges grant everything (see 20261030000006_saved_plans_grants.sql): reset both
-- roles, then allow only reading.
revoke all on profiles from anon, authenticated;
grant select on profiles to authenticated;

alter table saved_plans drop constraint saved_plans_kind_check,
  add constraint saved_plans_kind_check check (kind in ('day_hike', 'multiday', 'search'));
