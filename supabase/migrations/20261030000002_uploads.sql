-- Private photo uploads: bucket `uploads` (private) and own rows in `photos`.
-- Objects live under <auth.uid()>/<trail_id>/<uuid>.jpg; only that user can read, write or delete them.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('uploads', 'uploads', false, 10485760, array['image/jpeg'])
on conflict (id) do update set public = false, file_size_limit = 10485760, allowed_mime_types = array['image/jpeg'];

create policy uploads_select on storage.objects for select to authenticated
  using (bucket_id = 'uploads' and (storage.foldername(name))[1] = auth.uid()::text);
create policy uploads_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'uploads' and (storage.foldername(name))[1] = auth.uid()::text);
create policy uploads_delete on storage.objects for delete to authenticated
  using (bucket_id = 'uploads' and (storage.foldername(name))[1] = auth.uid()::text);

alter table photos alter column owner set default auth.uid();

-- photos_select (Commons rows, source <> 'upload') stays untouched; uploads are visible to their owner only.
create policy photos_owner_select on photos for select to authenticated
  using (source = 'upload' and owner = auth.uid());
create policy photos_owner_insert on photos for insert to authenticated
  with check (source = 'upload' and owner = auth.uid());
create policy photos_owner_delete on photos for delete to authenticated
  using (source = 'upload' and owner = auth.uid());

-- Supabase default privileges may grant more: reset, then exactly select (public, as before) + insert/delete for signed-in users.
revoke all on photos from anon, authenticated;
grant select on photos to anon, authenticated;
grant insert, delete on photos to authenticated;
grant usage on sequence photos_id_seq to authenticated;
