-- App users: one row per Supabase auth user with an account status. Admins are not app users
-- (the backend has its own sign-in). Clients may read only their own row; the status is written by
-- the backend as table owner and must never be writable from the browser.
create table app_users (
  user_id uuid primary key references auth.users (id) on delete cascade,
  email text,
  status text not null default 'aktiv' check (status in ('aktiv', 'gesperrt')),
  created_at timestamptz not null default now(),
  blocked_at timestamptz
);

create function public.handle_new_app_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.app_users (user_id, email, created_at)
  values (new.id, new.email, coalesce(new.created_at, now())) on conflict do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created_app_user after insert on auth.users
  for each row execute function public.handle_new_app_user();

-- Backfill accounts that exist before this migration.
insert into app_users (user_id, email, created_at)
select id, email, coalesce(created_at, now()) from auth.users on conflict do nothing;

alter table app_users enable row level security;
create policy app_users_select on app_users for select to authenticated using (user_id = auth.uid());
revoke all on app_users from anon, authenticated;
grant select on app_users to authenticated;

-- True when the signed-in user exists and is not blocked. Security definer: policies of other tables
-- call it without depending on app_users' own RLS.
create function public.is_active_user() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.app_users where user_id = auth.uid() and status = 'aktiv');
$$;
revoke all on function public.is_active_user() from public;
grant execute on function public.is_active_user() to authenticated;

-- A blocked user's still-valid access token must not write anything.
drop policy saved_plans_insert on saved_plans;
drop policy saved_plans_delete on saved_plans;
create policy saved_plans_insert on saved_plans for insert to authenticated
  with check (user_id = auth.uid() and public.is_active_user());
create policy saved_plans_delete on saved_plans for delete to authenticated
  using (user_id = auth.uid() and public.is_active_user());

drop policy uploads_insert on storage.objects;
drop policy uploads_delete on storage.objects;
create policy uploads_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'uploads' and (storage.foldername(name))[1] = auth.uid()::text and public.is_active_user());
create policy uploads_delete on storage.objects for delete to authenticated
  using (bucket_id = 'uploads' and (storage.foldername(name))[1] = auth.uid()::text and public.is_active_user());

drop policy photos_owner_insert on photos;
drop policy photos_owner_delete on photos;
create policy photos_owner_insert on photos for insert to authenticated
  with check (source = 'upload' and owner = auth.uid() and public.is_active_user());
create policy photos_owner_delete on photos for delete to authenticated
  using (source = 'upload' and owner = auth.uid() and public.is_active_user());

-- Guest chat requests (key = hashed IP /64 or IPv4), counted over 24 h by the backend only.
create table guest_requests (
  id bigserial primary key,
  key text not null,
  ts timestamptz not null default now()
);
create index guest_requests_ts on guest_requests (ts);
create index guest_requests_key_ts on guest_requests (key, ts);
alter table guest_requests enable row level security;
revoke all on guest_requests from anon, authenticated;
revoke all on sequence guest_requests_id_seq from anon, authenticated;
