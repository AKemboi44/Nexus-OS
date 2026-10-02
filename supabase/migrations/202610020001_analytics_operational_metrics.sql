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
            'event_name', event_name, 'event_count', event_count, 'unique_users', unique_users
        ) order by event_count desc), '[]'::jsonb) as value
        from (
            select event_name, count(*) as event_count, count(distinct user_id) as unique_users
            from filtered group by event_name
        ) grouped_events
    ),
    errors as (
        select coalesce(jsonb_agg(jsonb_build_object(
            'error_code', error_code, 'message', message, 'occurrences', occurrences
        ) order by occurrences desc), '[]'::jsonb) as value
        from (
            select properties ->> 'error_code' as error_code,
                   properties ->> 'message' as message, count(*) as occurrences
            from filtered
            where event_name in ('error', 'scan_failed', 'report_failed', 'payment_failed')
            group by properties ->> 'error_code', properties ->> 'message'
            order by count(*) desc limit 25
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
            'stage', stage, 'label', label, 'unique_users', coalesce(user_count, 0),
            'events', coalesce(event_count, 0)
        ) order by position), '[]'::jsonb) as value
        from funnel_stages
        left join lateral (
            select count(distinct user_id) as user_count, count(*) as event_count
            from filtered where event_name = stage
        ) counts on true
    ),
    operational_metrics as (
        select coalesce(jsonb_agg(jsonb_build_object(
            'event_name', event_name,
            'event_count', event_count,
            'timed_events', timed_events,
            'average_duration_ms', average_duration_ms,
            'cache_hits', cache_hits
        ) order by event_count desc), '[]'::jsonb) as value
        from (
            select event_name,
                   count(*) as event_count,
                   count(*) filter (where properties ? 'duration_ms') as timed_events,
                   round(avg((properties ->> 'duration_ms')::numeric)) as average_duration_ms,
                   count(*) filter (where properties ->> 'cache_hit' = 'true') as cache_hits
            from filtered
            where event_name in (
                'scan_completed', 'scan_failed', 'report_completed', 'report_failed',
                'report_cache_redownload_completed', 'report_cache_redownload_failed',
                'excel_export_completed', 'excel_download_completed', 'excel_download_failed'
            )
            group by event_name
        ) grouped_operational_metrics
    )
    select jsonb_build_object(
        'window_days', least(greatest(days, 1), 365),
        'events', totals.value,
        'common_errors', errors.value,
        'funnel', funnel.value,
        'operational_metrics', operational_metrics.value
    )
    from totals, errors, funnel, operational_metrics;
$$;

revoke all on function public.nexus_analytics_summary(integer) from public, anon, authenticated;
grant execute on function public.nexus_analytics_summary(integer) to service_role;
