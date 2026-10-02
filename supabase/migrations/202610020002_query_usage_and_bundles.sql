-- Migration: Add user query usage tracking and bundle entitlement columns

alter table public.entitlements 
    add column if not exists bundle_queries_remaining integer default null,
    add column if not exists total_queries_used integer default 0;

create table if not exists public.user_query_usage (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    period_month text not null,
    query_count integer default 0,
    last_queried_at timestamptz not null default now(),
    unique (user_id, period_month)
);

create index if not exists user_query_usage_user_period_idx
    on public.user_query_usage (user_id, period_month);

alter table public.user_query_usage enable row level security;

revoke all on public.user_query_usage from anon, authenticated;
grant all on public.user_query_usage to service_role;
grant usage, select on sequence public.user_query_usage_id_seq to service_role;
