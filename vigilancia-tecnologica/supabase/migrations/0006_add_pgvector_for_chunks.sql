-- Habilita la extensión pgvector para búsquedas semánticas y similitud de coseno.
create extension if not exists vector;

-- Agrega la columna de embeddings a los fragmentos de documento.
-- Dimensiones: 768 (text-embedding-004 de Gemini).
alter table document_chunks 
add column if not exists embedding vector(768);

-- Crea un índice HNSW para optimizar búsquedas por similitud de coseno.
create index if not exists document_chunks_embedding_cosine_idx 
on document_chunks 
using hnsw (embedding vector_cosine_ops);

-- Función RPC para buscar fragmentos similares desde Supabase.
create or replace function match_document_chunks (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  filter_document_ids uuid[] default null
)
returns table (
  id uuid,
  document_id uuid,
  content text,
  page_number int,
  section_title text,
  sheet_name text,
  row_reference text,
  similarity float
)
language sql stable
as $$
  select
    document_chunks.id,
    document_chunks.document_id,
    document_chunks.content,
    document_chunks.page_number,
    document_chunks.section_title,
    document_chunks.sheet_name,
    document_chunks.row_reference,
    1 - (document_chunks.embedding <=> query_embedding) as similarity
  from document_chunks
  where 1 - (document_chunks.embedding <=> query_embedding) > match_threshold
    and (filter_document_ids is null or document_chunks.document_id = any(filter_document_ids))
  order by document_chunks.embedding <=> query_embedding
  limit match_count;
$$;
