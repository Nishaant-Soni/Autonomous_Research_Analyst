# Autonomous Research Analyst

A multi-agent system that takes a research question, plans an investigation, gathers
evidence from the web and a private document corpus, critiques and fact-checks its own
findings, and produces a fully cited report.

See [`PRD.md`](./PRD.md) for the product spec.

## Status

Built so far:

- **Foundation** — FastAPI service + Postgres (pgvector), one-command bring-up, local embedding model baked into the image.
- **Retrieval layer** — document ingestion (chunk + embed + store), pgvector similarity search (RAG), and Tavily web search. Both retrievers return structured `Evidence`.
- **Agent-graph foundation** — the shared `ResearchState` contract and `Critique` model (`app/graph/state.py`), with an additive reducer so evidence accumulates across the critic loop.
- **Planner & Citation-validator nodes** — the Planner (`app/agents/planner.py`) decomposes a question into 3–6 sub-questions via one LLM call; the Citation validator (`app/agents/citation_validator.py`) is pure code that confirms every `[n]` marker resolves to a real evidence item and, when one doesn't, drops the whole unsupported claim, then renumbers and rebuilds the sources list so the report stays self-consistent.

Not yet built: the Researcher/Critic/Writer nodes and their graph wiring, the
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

# Full suite, including DB ingestion/retrieval, the real embedding model, live web,
# and a live LLM call. Needs Postgres running; the schema is created by the fixtures.
docker compose up -d db
RUN_DB_TESTS=1 RUN_MODEL_TESTS=1 RUN_WEB_TESTS=1 RUN_LLM_TESTS=1 pytest -q
```

- `RUN_DB_TESTS=1` enables tests that need Postgres (`DATABASE_URL` must point at it).
- `RUN_MODEL_TESTS=1` enables tests that load the real embedding model.
- `RUN_WEB_TESTS=1` enables the live Tavily web-search test (needs a real `TAVILY_API_KEY`).
- `RUN_LLM_TESTS=1` enables the live LLM test (Planner) — needs a real `OPENAI_API_KEY`.

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
| `TAVILY_API_KEY` | Web search (Tavily) — the `web_search` retriever and live web test |
| `LANGSMITH_API_KEY` | Optional tracing |
| `EMBEDDING_MODEL` | Local embedding model (default `BAAI/bge-small-en-v1.5`) |
| `MAX_ITERATIONS` | Hard cap on the critic loop (default `2`) |
