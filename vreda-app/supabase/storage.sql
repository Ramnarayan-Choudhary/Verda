-- Create the storage bucket (PRIVATE — no public access)
insert into storage.buckets (id, name, public)
values ('Research-Paper', 'Research-Paper', false)
on conflict (id) do nothing;

-- RLS: Authenticated users can upload to their own folder
create policy "Authenticated users can upload"
  on storage.objects for insert
  with check (
    bucket_id = 'Research-Paper'
    and auth.role() = 'authenticated'
  );

-- RLS: Users can only view files in their own folder
create policy "Users can view their own files"
  on storage.objects for select
  using (
    bucket_id = 'Research-Paper'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- RLS: Users can only delete files in their own folder
create policy "Users can delete their own files"
  on storage.objects for delete
  using (
    bucket_id = 'Research-Paper'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
