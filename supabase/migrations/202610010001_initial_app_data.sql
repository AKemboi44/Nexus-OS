create table if not exists public.research_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    query text not null,
    result jsonb not null,
    created_at timestamptz not null default now()
);

create index if not exists research_runs_user_created_idx
    on public.research_runs (user_id, created_at desc);

create table if not exists public.saved_dossiers (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text not null,
    payload jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists saved_dossiers_user_updated_idx
    on public.saved_dossiers (user_id, updated_at desc);

create table if not exists public.saved_sources (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    source_key text not null,
    source jsonb not null,
    created_at timestamptz not null default now(),
    unique (user_id, source_key)
);

create index if not exists saved_sources_user_created_idx
    on public.saved_sources (user_id, created_at desc);

create table if not exists public.analytics_events (
    id bigint generated always as identity primary key,
    event_name text not null,
    user_id uuid references auth.users(id) on delete set null,
    session_id text not null default 'unknown',
    occurred_at timestamptz not null default now(),
    properties jsonb not null default '{}'::jsonb
);

create index if not exists analytics_events_name_time_idx
    on public.analytics_events (event_name, occurred_at desc);
create index if not exists analytics_events_user_time_idx
    on public.analytics_events (user_id, occurred_at desc);

create table if not exists public.entitlements (
    user_id uuid primary key references auth.users(id) on delete cascade,
    provider text not null,
    provider_id text not null unique,
    plan text,
    status text not null,
    starts_at timestamptz,
    ends_at timestamptz,
    updated_at timestamptz not null default now()
);

create table if not exists public.payment_events (
    event_id text primary key,
    received_at timestamptz not null default now()
);

alter table public.research_runs enable row level security;
alter table public.saved_dossiers enable row level security;
alter table public.saved_sources enable row level security;
alter table public.analytics_events enable row level security;
alter table public.entitlements enable row level security;
alter table public.payment_events enable row level security;

create policy "Users can access their research runs"
    on public.research_runs for all to authenticated
    using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users can access their saved dossiers"
    on public.saved_dossiers for all to authenticated
    using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users can access their saved sources"
    on public.saved_sources for all to authenticated
    using (auth.uid() = user_id) with check (auth.uid() = user_id);

revoke all on public.analytics_events, public.entitlements, public.payment_events
    from anon, authenticated;
grant all on public.analytics_events, public.entitlements, public.payment_events
    to service_role;
grant select, insert, update, delete on public.research_runs,
    public.saved_dossiers, public.saved_sources to authenticated, service_role;
grant usage, select on sequence public.analytics_events_id_seq to service_role;

create or replace function public.nexus_analytics_summary(days integer default 30)
returns jsonb
language sql
security invoker
set search_path = ''
as $$
    with filtered as (
        select event_name, user_id, occurred_at, properties
        from public.analytics_events
        where occurred_at >= now() - make_interval(days => least(greatest(days, 1), 365))
    ),
    totals as (
        select coalesce(jsonb_agg(jsonb_build_object(
            'event_name', event_name,
            'event_count', event_count,
            'unique_users', unique_users
        ) order by event_count desc), '[]'::jsonb) as value
        from (
            select event_name, count(*) as event_count, count(distinct user_id) as unique_users
            from filtered group by event_name
        ) grouped_events
    ),
    errors as (
        select coalesce(jsonb_agg(jsonb_build_object(
            'error_code', error_code,
            'message', message,
            'occurrences', occurrences
        ) order by occurrences desc), '[]'::jsonb) as value
        from (
            select properties ->> 'error_code' as error_code,
                   properties ->> 'message' as message,
                   count(*) as occurrences
            from filtered
            where event_name in ('error', 'scan_failed', 'report_failed', 'payment_failed')
            group by properties ->> 'error_code', properties ->> 'message'
            order by count(*) desc
            limit 25
        ) grouped_errors
    ),
    funnel_stages(stage, label, position) as (
        values
            ('workspace_opened', 'Workspace opened', 1),
            ('scan_started', 'Research scan started', 2),
            ('scan_completed', 'Research scan completed', 3),
            ('report_started', 'Report generation started', 4),
            ('report_completed', 'Report generated', 5),
            ('checkout_started', 'Checkout started', 6),
            ('payment_completed', 'Payment completed', 7)
    ),
    funnel as (
        select coalesce(jsonb_agg(jsonb_build_object(
            'stage', stage,
            'label', label,
            'unique_users', coalesce(user_count, 0),
            'events', coalesce(event_count, 0)
        ) order by position), '[]'::jsonb) as value
        from funnel_stages
        left join lateral (
            select count(distinct user_id) as user_count, count(*) as event_count
            from filtered where event_name = stage
        ) counts on true
    )
    select jsonb_build_object(
        'window_days', least(greatest(days, 1), 365),
        'events', totals.value,
        'common_errors', errors.value,
        'funnel', funnel.value
    )
    from totals, errors, funnel;
$$;

revoke all on function public.nexus_analytics_summary(integer) from public, anon, authenticated;
grant execute on function public.nexus_analytics_summary(integer) to service_role;
