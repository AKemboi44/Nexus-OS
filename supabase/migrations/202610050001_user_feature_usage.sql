-- Monthly allowances for small free-tier features (e.g. one Word snapshot per month).
-- Claims are atomic, so two requests at once cannot both take the last credit.

create table if not exists public.user_feature_usage (
    user_id uuid not null references auth.users(id) on delete cascade,
    feature text not null,
    period_month text not null,
    use_count integer not null default 0 check (use_count >= 0),
    updated_at timestamptz not null default now(),
    primary key (user_id, feature, period_month)
);

alter table public.user_feature_usage enable row level security;
revoke all on public.user_feature_usage from public, anon, authenticated;
grant all on public.user_feature_usage to service_role;

-- Returns the new use count, or -1 when the monthly limit is already reached.
create or replace function public.nexus_claim_feature_use(
    p_user_id uuid,
    p_feature text,
    p_period text,
    p_limit integer
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
    claimed_count integer;
begin
    if p_limit <= 0 then
        return -1;
    end if;

    insert into public.user_feature_usage (user_id, feature, period_month, use_count)
    values (p_user_id, p_feature, p_period, 1)
    on conflict (user_id, feature, period_month) do update
        set use_count = public.user_feature_usage.use_count + 1,
            updated_at = now()
        where public.user_feature_usage.use_count < p_limit
    returning use_count into claimed_count;

    if claimed_count is null then
        return -1;
    end if;
    return claimed_count;
end;
$$;

-- Gives a credit back when the feature failed before anything was delivered.
create or replace function public.nexus_release_feature_use(
    p_user_id uuid,
    p_feature text,
    p_period text
)
returns void
language sql
security definer
set search_path = ''
as $$
    update public.user_feature_usage
       set use_count = greatest(0, use_count - 1),
           updated_at = now()
     where user_id = p_user_id and feature = p_feature and period_month = p_period;
$$;

revoke all on function public.nexus_claim_feature_use(uuid, text, text, integer) from public, anon, authenticated;
grant execute on function public.nexus_claim_feature_use(uuid, text, text, integer) to service_role;
revoke all on function public.nexus_release_feature_use(uuid, text, text) from public, anon, authenticated;
grant execute on function public.nexus_release_feature_use(uuid, text, text) to service_role;
