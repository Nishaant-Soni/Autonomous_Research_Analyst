-- Source of truth for the database schema (PRD §8). Plain, idempotent DDL — no Alembic
-- in v1 (see IMPLEMENTATION_PLAN.md 1.1). Keep app/db/models.py in lockstep with this file.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    source_uri  TEXT,
    title       TEXT,
    raw_text    TEXT NOT NULL,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(384)
);

CREATE TABLE IF NOT EXISTS research_sessions (
    id                 BIGSERIAL PRIMARY KEY,
    question           TEXT NOT NULL,
    status             TEXT NOT NULL,
    plan               JSONB,
    low_confidence     BOOLEAN NOT NULL DEFAULT false,
    stripped_fraction  DOUBLE PRECISION NOT NULL DEFAULT 0,
    error              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ
);

-- Schema evolution without Alembic (plan 3.2): existing volumes get new columns via ALTER.
-- Each ALTER mirrors its CREATE column exactly (type/default/nullability); the NOT NULL ones
-- carry a DEFAULT so adding them to an already-populated table succeeds.
ALTER TABLE research_sessions ADD COLUMN IF NOT EXISTS low_confidence BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE research_sessions ADD COLUMN IF NOT EXISTS stripped_fraction DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE research_sessions ADD COLUMN IF NOT EXISTS error TEXT;

CREATE TABLE IF NOT EXISTS evidence (
    id               BIGSERIAL PRIMARY KEY,
    session_id       BIGINT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
    claim            TEXT,
    content          TEXT,
    source_url       TEXT,
    source_chunk_id  BIGINT REFERENCES chunks(id),
    retriever        TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
    id                BIGSERIAL PRIMARY KEY,
    session_id        BIGINT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
    report_md         TEXT,
    citations_valid   BOOLEAN,
    faithfulness      DOUBLE PRECISION,
    answer_relevancy  DOUBLE PRECISION,
    hallucination_rate DOUBLE PRECISION,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Schema evolution: add Ragas per-run metric columns to existing report rows.
ALTER TABLE reports ADD COLUMN IF NOT EXISTS faithfulness DOUBLE PRECISION;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS answer_relevancy DOUBLE PRECISION;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS hallucination_rate DOUBLE PRECISION;

-- Approximate-nearest-neighbour index for similarity search (PRD §8). Cosine ops match
-- the normalized embeddings produced in app/embeddings.py.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Phase 6: Authentication (plan 6.1).
-- `users` and `refresh_tokens` are new tables — CREATE IF NOT EXISTS is fully idempotent.
-- `documents` and `research_sessions` get a nullable `user_id` FK via ALTER (§3.2 pattern).
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    hashed_pw  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    jti        TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    used       BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- Nullable because pre-auth rows have no owner; NOT NULL + DEFAULT would silently diverge
-- on an empty-vs-populated volume (see plan §3.2 caveat).
ALTER TABLE documents         ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE research_sessions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_documents_user_id         ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_research_sessions_user_id ON research_sessions(user_id);
