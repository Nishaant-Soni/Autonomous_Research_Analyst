# Autonomous Research Analyst

A multi-agent system that takes a research question, plans an investigation, gathers
evidence from the web and a private document corpus, critiques and fact-checks its own
findings, and produces a fully cited report.

See [`PRD.md`](./PRD.md) for the product spec.

## Status

Built so far:

- **Foundation** — FastAPI service + Postgres (pgvector), one-command bring-up, local embedding model baked into the image.
- **Retrieval layer** — document ingestion (chunk + embed + store) and pgvector similarity search returning structured `Evidence`.

Not yet built: the agent graph (planner/researcher/critic/writer/validator), the
`/research` endpoints, evaluation harness, and UI.

## HTTP endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/documents` | Ingest a document: chunk + embed + store |

Interactive API docs render at `http://localhost:8000/docs`.

## Quickstart (Docker)

Brings up the API + Postgres (with pgvector). The DB schema is applied automatically on
first start (fresh volume); the API image has the embedding model baked in, so there's
no download on first run.

```bash
docker-compose up --build

# Liveness check
curl localhost:8000/health            # -> {"status":"ok"}

# Ingest a document
curl -X POST localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Paris is the capital of France.", "title": "geo"}'
# -> {"document_id": 1, "chunks": 1}
```

## Local development

Requires a running Postgres with pgvector. The easiest path is to run just the DB in
Docker and the app on the host:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                  # fill in keys (OpenAI/Tavily); embeddings need none

docker compose up -d db               # Postgres + pgvector on localhost:5432
uvicorn app.main:app --reload         # http://localhost:8000/docs
```

The first embedding call downloads the model (`BAAI/bge-small-en-v1.5`, 384-dim) into
the local Hugging Face cache.

## Tests

```bash
# Fast unit tests (DB- and model-dependent tests are skipped)
pytest -q

# Full suite, including DB ingestion/retrieval and the real embedding model.
# Needs Postgres running; the schema is created automatically by the test fixtures.
docker compose up -d db
RUN_DB_TESTS=1 RUN_MODEL_TESTS=1 pytest -q
```

- `RUN_DB_TESTS=1` enables tests that need Postgres (`DATABASE_URL` must point at it).
- `RUN_MODEL_TESTS=1` enables tests that load the real embedding model.

CI runs the full suite (Postgres service container + cached model) on push/PR to `main`.

## Lint / format

```bash
ruff check .          # lint
ruff format .         # apply formatting (CI runs `ruff format --check .`)
```

## Configuration

All settings come from environment variables / `.env` (see [`.env.example`](./.env.example)):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `OPENAI_API_KEY` | LLM agents (added in a later phase) |
| `TAVILY_API_KEY` | Web search (added in a later phase) |
| `LANGSMITH_API_KEY` | Optional tracing |
| `EMBEDDING_MODEL` | Local embedding model (default `BAAI/bge-small-en-v1.5`) |
| `MAX_ITERATIONS` | Hard cap on the critic loop (default `2`) |
```
