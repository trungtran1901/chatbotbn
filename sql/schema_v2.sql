CREATE SCHEMA IF NOT EXISTS ragv2;

CREATE TABLE IF NOT EXISTS ragv2.catalogs (
    id SERIAL PRIMARY KEY,
    catalog_title TEXT NOT NULL,
    table_name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ragv2.originaldata_metadata (
    id SERIAL PRIMARY KEY,
    catalogtitle TEXT,
    title TEXT,
    publishdate TEXT,
    doc_type TEXT,
    source TEXT,
    source_link TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_originaldata_lookup_v2
    ON ragv2.originaldata_metadata (title, publishdate, catalogtitle);

CREATE TABLE IF NOT EXISTS ragv2.crawl_links (
    id BIGSERIAL PRIMARY KEY,
    link TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crawl_links_status
    ON ragv2.crawl_links (status);

CREATE TABLE IF NOT EXISTS ragv2.chat_memory (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_memory_session_v2
    ON ragv2.chat_memory (session_id, created_at);