-- saved_plans revoked only anon's default privileges: authenticated kept UPDATE, TRUNCATE, … from the
-- Supabase defaults. Reset both, then exactly what the app uses (a plan is saved or deleted, never edited).
revoke all on saved_plans from anon, authenticated;
grant select, insert, delete on saved_plans to authenticated;
