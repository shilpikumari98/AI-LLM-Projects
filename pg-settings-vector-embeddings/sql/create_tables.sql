-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Insights table stores textual AI recommendations for settings
CREATE TABLE IF NOT EXISTS insights (
    settings_name TEXT PRIMARY KEY,
    ai_insights TEXT
);

-- -- Embeddings table stores vector embeddings of each setting
-- CREATE TABLE IF NOT EXISTS setting_embeddings (
--     settings_name TEXT PRIMARY KEY,
--     embedding vector(384)  -- Using 384-dim embeddings (example: sentence-transformers all-MiniLM-L6-v2)
-- );

-- Embeddings for setting insights
CREATE TABLE IF NOT EXISTS insight_embeddings (
    settings_name TEXT PRIMARY KEY,
    embedding VECTOR(384)
);

-- Embeddings + metadata for settings
CREATE TABLE IF NOT EXISTS pg_settings_metadata_embeddings (
    name TEXT PRIMARY KEY,
    embedding VECTOR(384),
    current_value TEXT,
    default_value TEXT,
    short_desc TEXT,
    context TEXT,
    vartype TEXT,
    min_val TEXT,
    max_val TEXT
);
