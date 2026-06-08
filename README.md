# Autonomous Research Analyst

A multi-agent system that takes a research question, plans an investigation, gathers
evidence from the web and a private document corpus, critiques and fact-checks its own
findings, and produces a fully cited report.

See [`PRD.md`](./PRD.md) for the product spec.

## Status

Built so far:

- **Foundation** — FastAPI service + Postgres (pgvector), one-command bring-up, local embedding model baked into the image.
- **Retrieval layer** — document ingestion (chunk + embed + store), pgvector similarity search (RAG), and Tavily web search. Both retrievers return structured `Evidence`.
- **Agent-graph foundation** — the shared `ResearchState` contract and `Critique` model (`app/graph/state.py`), with a deduplicating reducer so evidence accumulates across the critic loop without the same source landing twice.
- **All five agent nodes** — Planner (`app/agents/planner.py`, decomposes a question into 3–6 sub-questions), Researcher (`app/agents/researcher.py`, a tool-using loop over `web_search` + `rag_retrieve` that gathers `Evidence` and drafts findings), Critic (`app/agents/critic.py`, LLM-as-judge emitting a groundedness score + `needs_more_research`), Writer (`app/agents/writer.py`, synthesizes a structured report citing evidence by `[ev:i]`), and Citation validator (`app/agents/citation_validator.py`, pure code that drops unsupported claims, then assigns the final `[1..k]` numbering + sources list).
- **The research graph (Phase 2 complete)** — `app/graph/build.py` wires the five nodes into a LangGraph `StateGraph` with a bounded critic loop (`max_iterations`) and Postgres checkpointing. `python -m scripts.run_once "<question>"` runs the whole pipeline end-to-end and prints a cited Markdown report.
- **Async research API (Phase 3 complete)** — `POST /research` creates a session and kicks off the graph run as a background task, returning a `session_id` immediately. A shared runner (`app/graph/runner.py`) drives the session status through `planning → researching → critiquing → writing → validating → done | failed`, persists the report and the citation validator's low-confidence signal, and pushes per-agent progress onto an in-process queue (`app/api/progress.py`). `GET /research/{id}` polls status (and returns the report once done), `GET /research/{id}/evidence` inspects the gathered evidence, and `GET /research/{id}/stream` streams per-agent progress over SSE (status names the currently-running stage, via LangGraph node-start events). `run_once` now shares this runner.
- **Reliability + observability (Phase 3 complete)** — every LLM call has a per-call timeout + automatic retries, and each agent has a token budget (PRD §12); a failed agent fails the session cleanly (`failed` + `error`) rather than hanging. With a `LANGSMITH_API_KEY` set, runs are traced in LangSmith with per-agent node spans plus per-call token usage and latency (`app/observability.py`).
- **Eval dataset + run harness (Phase 4 Group A complete)** — `eval/golden.jsonl` holds 16 schema-validated research questions (10 web + 6 corpus), each with reference key facts used as Ragas ground truth. Corpus items are backed by a committed, self-authored seed corpus (`eval/corpus/*.md`) and the loader enforces that every corpus fact is verbatim-supported by its source doc. `python -m eval.run` ingests the corpus idempotently, runs the full graph per item, persists per-question artifacts (`report.md` / `evidence.jsonl` / `result.json`) to `eval/runs/<run-id>/<item.id>/`, and runs a deterministic retrievability check confirming every corpus fact is actually surfaced by the production embedder + retriever. Run/score/report separation — metrics in Group B read these cached artifacts and never re-run the pipeline.

Not yet built (Phase 4 Group B + C, plus Phase 5): metric scoring (Ragas, citation accuracy, hallucination rate, latency/cost), the versioned aggregate eval report, the embedding A/B, prompt-tuning before/after, and the UI.

## HTTP endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/documents` | Ingest a document: chunk + embed + store |
| POST | `/research` | Start an async research run; returns a `session_id` immediately (202) |
| GET | `/research/{id}` | Poll run status; once `done`, returns the report + `citations_valid` (+ `low_confidence`) |
| GET | `/research/{id}/evidence` | Inspect the structured evidence gathered for the session |
| GET | `/research/{id}/stream` | SSE stream of per-agent progress while the run executes |

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

## Run the research pipeline (end-to-end)

With Postgres up and `OPENAI_API_KEY` + `TAVILY_API_KEY` set in `.env`, run the full
multi-agent graph over a question and get a cited Markdown report:

```bash
docker compose up -d db
python -m scripts.run_once "What are the main benefits of on-device LLM inference?"
```

It creates a `research_sessions` row, runs Planner → Researcher → Critic (bounded loop) →
Writer → Citation validator (checkpointing to Postgres), persists the `evidence` and
`reports` rows, and prints the report with inline `[n]` citations and a sources list.

## Run the eval harness (Phase 4 Group A)

```bash
docker compose up -d db
python -m scripts.run_once "hi"        # one-time: bootstraps the DB schema (any question)
python -m eval.run --only-retrievability   # cheap: confirms every corpus key_fact is surfaced
python -m eval.run --limit 2               # smoke: runs the graph over the first 2 items
python -m eval.run                         # full: all 16 items (costs LLM tokens; ~30-60 min)
```

Artifacts land under `eval/runs/<run-id>/` (gitignored). Per item: `report.md`,
`evidence.jsonl`, `result.json`. Run-level: `meta.json`, `summary.json`,
`retrievability.json`. Failures are isolated per-item (`error.txt`) so one bad item doesn't
sink the run.

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
| `OPENAI_API_KEY` | LLM agents (Planner / Researcher / Critic / Writer) |
| `TAVILY_API_KEY` | Web search (Tavily) — the `web_search` retriever and live web test |
| `LANGSMITH_API_KEY` | Optional — set to enable LangSmith tracing (per-agent spans, token usage, latency) |
| `LANGSMITH_PROJECT` | LangSmith project name (default `autonomous-research-analyst`) |
| `LLM_TIMEOUT_SECONDS` | Per-call LLM timeout, a hang ceiling (default `120`) |
| `LLM_MAX_RETRIES` | LLM retries for transient errors (default `2`) |
| `EMBEDDING_MODEL` | Local embedding model (default `BAAI/bge-small-en-v1.5`) |
| `MAX_ITERATIONS` | Hard cap on the critic loop (default `2`) |
