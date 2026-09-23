CREATE TABLE IF NOT EXISTS catalogs (
    id SERIAL PRIMARY KEY,
    catalog_title TEXT NOT NULL,
    table_name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS originaldata_metadata (
    id SERIAL PRIMARY KEY,
    catalogtitle TEXT,
    title TEXT,
    publishdate TEXT,
    doc_type TEXT,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_originaldata_lookup
    ON originaldata_metadata (title, publishdate, catalogtitle);

CREATE TABLE IF NOT EXISTS chat_memory (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_memory_session
    ON chat_memory (session_id, created_at);
