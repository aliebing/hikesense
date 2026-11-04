-- Roles are gone: the admin signs in to /backend on its own, app users live in app_users.
drop trigger if exists on_auth_user_created on auth.users;
drop function if exists public.handle_new_user();
drop table if exists profiles;
