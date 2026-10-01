create table if not exists public.dossier_download_usage (
    user_id uuid primary key references auth.users(id) on delete cascade,
    download_count integer not null default 0 check (download_count between 0 and 3),
    updated_at timestamptz not null default now()
);

alter table public.dossier_download_usage enable row level security;
revoke all on public.dossier_download_usage from public, anon, authenticated;
grant all on public.dossier_download_usage to service_role;

create or replace function public.nexus_claim_dossier_download(p_user_id uuid)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
    claimed_count integer;
begin
    insert into public.dossier_download_usage (user_id, download_count)
    values (p_user_id, 1)
    on conflict (user_id) do update
        set download_count = public.dossier_download_usage.download_count + 1,
            updated_at = now()
        where public.dossier_download_usage.download_count < 3
    returning download_count into claimed_count;

    if claimed_count is null then
        return -1;
    end if;
    return 3 - claimed_count;
end;
$$;

revoke all on function public.nexus_claim_dossier_download(uuid) from public, anon, authenticated;
grant execute on function public.nexus_claim_dossier_download(uuid) to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'research-dossiers',
    'research-dossiers',
    false,
    26214400,
    array['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
