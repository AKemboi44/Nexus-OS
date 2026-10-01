insert into public.saved_dossiers (user_id, title, payload)
select
    runs.user_id,
    left(coalesce(nullif(runs.query, ''), 'Research dossier'), 200),
    jsonb_build_object(
        'research_run_id', runs.id,
        'query', runs.query,
        'status', runs.result ->> 'status',
        'discovery_report_name', runs.result ->> 'discovery_report_name',
        'included_count',
            case
                when jsonb_typeof(runs.result -> 'included') = 'array'
                    then jsonb_array_length(runs.result -> 'included')
                else 0
            end,
        'excluded_count',
            case
                when jsonb_typeof(runs.result -> 'excluded') = 'array'
                    then jsonb_array_length(runs.result -> 'excluded')
                else 0
            end
    )
from public.research_runs as runs
where not exists (
    select 1
    from public.saved_dossiers as dossiers
    where dossiers.user_id = runs.user_id
      and dossiers.payload ->> 'research_run_id' = runs.id::text
);
