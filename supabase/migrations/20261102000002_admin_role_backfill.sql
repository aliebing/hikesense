-- Backfill: the admin account created before roles existed (make admin-user) becomes admin.
-- Idempotent: running it again changes nothing.
update profiles set role = 'admin' where email = 'admin@hikeall.local';
