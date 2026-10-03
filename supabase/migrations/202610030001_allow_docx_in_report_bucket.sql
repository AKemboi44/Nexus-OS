-- The research-dossiers bucket only allowed xlsx, so cached Word reports
-- (proposal / full_starter) were rejected with "mime type ... is not supported".
update storage.buckets
set allowed_mime_types = array[
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
]
where id = 'research-dossiers';
