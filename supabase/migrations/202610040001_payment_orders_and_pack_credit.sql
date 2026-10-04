-- One-time pack purchases: durable orders, retry-safe webhook events, and atomic credit/refund.

create table if not exists public.payment_orders (
    order_id text primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    pack_id text not null,
    amount numeric(10, 2) not null,
    currency text not null,
    status text not null default 'pending'
        check (status in ('pending', 'captured', 'credited', 'refunded', 'failed')),
    capture_id text,
    created_at timestamptz not null default now(),
    captured_at timestamptz,
    credited_at timestamptz,
    refunded_at timestamptz
);

create unique index if not exists payment_orders_capture_idx
    on public.payment_orders (capture_id) where capture_id is not null;
create index if not exists payment_orders_user_idx
    on public.payment_orders (user_id, created_at desc);

alter table public.payment_orders enable row level security;
revoke all on public.payment_orders from public, anon, authenticated;
grant all on public.payment_orders to service_role;

-- A webhook event is final only once it was processed; failed attempts stay retryable.
alter table public.payment_events add column if not exists processed_at timestamptz;

-- Credit a paid order exactly once. The order flip and the entitlement change are one transaction,
-- so a crash cannot leave a paid order uncredited or credit it twice.
create or replace function public.nexus_credit_pack(
    p_order_id text,
    p_user_id uuid,
    p_pack_id text,
    p_scans integer,
    p_validity_days integer,
    p_capture_id text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    flipped text;
    ent public.entitlements%rowtype;
    new_end timestamptz;
begin
    update public.payment_orders
       set status = 'credited',
           capture_id = coalesce(p_capture_id, capture_id),
           captured_at = coalesce(captured_at, now()),
           credited_at = now()
     where order_id = p_order_id
       and user_id = p_user_id
       and status in ('pending', 'captured')
    returning order_id into flipped;

    if flipped is null then
        return jsonb_build_object('credited', false);
    end if;

    select * into ent from public.entitlements where user_id = p_user_id for update;

    if not found then
        new_end := now() + make_interval(days => p_validity_days);
        insert into public.entitlements
            (user_id, provider, provider_id, plan, status, starts_at, ends_at, updated_at,
             bundle_queries_remaining, total_queries_used)
        values
            (p_user_id, 'pack', 'pack_' || p_order_id, p_pack_id, 'ACTIVE', now(), new_end, now(),
             p_scans, 0);
    elsif ent.status = 'ACTIVE'
          and ent.bundle_queries_remaining is null
          and ent.provider not in ('pack', 'bundle') then
        -- An unlimited subscription already covers this user; keep it and record the order as credited.
        return jsonb_build_object('credited', true, 'ends_at', ent.ends_at, 'scans_added', 0, 'unlimited', true);
    else
        new_end := greatest(coalesce(ent.ends_at, now()), now()) + make_interval(days => p_validity_days);
        update public.entitlements
           set provider = 'pack',
               provider_id = 'pack_' || p_order_id,
               plan = p_pack_id,
               status = 'ACTIVE',
               ends_at = new_end,
               bundle_queries_remaining = coalesce(ent.bundle_queries_remaining, 0) + p_scans,
               updated_at = now()
         where user_id = p_user_id;
    end if;

    return jsonb_build_object('credited', true, 'ends_at', new_end, 'scans_added', p_scans);
end;
$$;

-- Undo a credited pack after a full refund or a reversal. Idempotent.
create or replace function public.nexus_refund_pack(
    p_order_id text,
    p_scans integer,
    p_validity_days integer
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    o public.payment_orders%rowtype;
    ent public.entitlements%rowtype;
    remaining integer;
begin
    select * into o from public.payment_orders where order_id = p_order_id for update;
    if not found or o.status not in ('credited', 'captured') then
        return jsonb_build_object('refunded', false);
    end if;

    update public.payment_orders set status = 'refunded', refunded_at = now() where order_id = p_order_id;

    if o.status = 'credited' then
        select * into ent from public.entitlements where user_id = o.user_id for update;
        if found and ent.provider in ('pack', 'bundle') then
            remaining := greatest(0, coalesce(ent.bundle_queries_remaining, 0) - p_scans);
            update public.entitlements
               set bundle_queries_remaining = remaining,
                   ends_at = case
                       when remaining = 0 then now()
                       else greatest(now(), coalesce(ent.ends_at, now()) - make_interval(days => p_validity_days))
                   end,
                   status = case when remaining = 0 then 'CANCELLED' else ent.status end,
                   updated_at = now()
             where user_id = o.user_id;
        end if;
    end if;

    return jsonb_build_object('refunded', true, 'was_credited', o.status = 'credited');
end;
$$;

revoke all on function public.nexus_credit_pack(text, uuid, text, integer, integer, text)
    from public, anon, authenticated;
grant execute on function public.nexus_credit_pack(text, uuid, text, integer, integer, text) to service_role;
revoke all on function public.nexus_refund_pack(text, integer, integer) from public, anon, authenticated;
grant execute on function public.nexus_refund_pack(text, integer, integer) to service_role;
