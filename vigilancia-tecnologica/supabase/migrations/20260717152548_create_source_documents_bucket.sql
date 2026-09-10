-- Bucket privado para documentos originales cargados por usuarios.
-- Guarda PDF y Excel fuente antes de la preparacion tecnica.

insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
values (
    'source-documents',
    'source-documents',
    false,
    52428800,
    array[
        'application/pdf',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
