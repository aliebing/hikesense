-- groups_geo got `grant select` without the reset: Supabase default privileges may grant more. Reset, then select only.
revoke all on groups_geo from anon, authenticated;
grant select on groups_geo to anon, authenticated;
