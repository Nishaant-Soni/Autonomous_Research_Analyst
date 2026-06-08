# Autonomous Research Analyst

A production-grade multi-agent system that accepts a research question, plans an investigation, gathers evidence from the live web and a private document corpus, critiques and fact-checks its own findings, and delivers a fully cited Markdown report — all in a single API call.

**Stack:** LangGraph · FastAPI · PostgreSQL + pgvector · OpenAI (`gpt-5.4-mini`) · Tavily · React + Vite + TypeScript + Tailwind · LangSmith · Ragas · Docker Compose

---

## Measured results

Evaluated against a [16-item golden dataset](eval/golden.jsonl) covering RAG, LLM inference, and retrieval engineering. All numbers are for the **tightened critic gate** (production config):

| Metric | Score |
|---|---|
| **Citation accuracy** | **100%** |
| **Faithfulness** | **95.9%** |
| **Answer relevancy** | **90.2%** |
| **Context recall** | **96.9%** |
| **Hallucination rate** (1 − faithfulness) | **4.1%** |
| Latency / item | 46.5 s |

### Critic-loop A/B

The critic loop was tuned across three arms. The key finding: the original `needs_more_research` gate was over-eager — it fired on every item and produced a net-wash 7-help / 7-hurt picture at 2× cost. Tightening to **two independent signals** (low groundedness *and* multiple named gaps) cut hallucination by ~25% at near-OFF cost:

| Arm | Hallucination rate | Latency / item |
|---|---|---|
| Original gate (`needs_more_research`) | 5.5% | 77.6 s |
| Gate OFF (no loop-back) | 4.8% | 40.6 s |
| **Tightened** (`groundedness < 0.70 AND gaps ≥ 2`) | **4.1%** | 46.5 s |

The tightened gate fires on exactly 3 of 16 items — precisely where a second research pass is worth paying for. Full 3-way breakdown: [`eval/results/critic_three_way.md`](eval/results/critic_three_way.md)

> **Caveat (n=16).** Run-to-run noise floor on aggregate hallucination is ≈ ±1–2 pp at this dataset size. The direction (tightened ≤ original on hallucination, tightened ≈ OFF on cost) is robust; the magnitude would tighten with a larger eval set.

---

## Architecture

```mermaid
flowchart TD
    UI["React UI\nVite · TypeScript · Tailwind"]

    subgraph backend["FastAPI Backend · Python 3.11"]
        API["REST + SSE Endpoints"]

        subgraph graph["LangGraph StateGraph · bounded critic loop"]
            direction LR
            PL["Planner\n3–6 sub-questions"]
            RS["Researcher\nweb + RAG tools"]
            CR["Critic\ngroundedness judge"]
            WR["Writer\ncited Markdown"]
            CV["Citation Validator\ndrop · renumber"]

            PL --> RS --> CR
            CR -->|"groundedness < 0.70\nAND gaps ≥ 2"| RS
            CR --> WR --> CV
        end

        API --> PL
    end

    subgraph datalayer["Data Layer"]
        direction LR
        DB[("PostgreSQL\n+ pgvector")]
        WEB["Tavily\nWeb Search"]
        LS["LangSmith\n(optional)"]
    end

    UI <-->|"POST /research · GET /stream SSE"| API
    RS -->|"RAG similarity search"| DB
    RS -->|"live web search"| WEB
    API -. "checkpoints" .-> DB
    CV -- "reports & evidence" --> DB
    backend -. "traces" .-> LS
```

**Five agents, one graph:**

| Agent | Role |
|---|---|
| **Planner** | Decomposes the question into 3–6 targeted sub-questions |
| **Researcher** | Tool-using loop over `web_search` + `rag_retrieve`; returns structured `Evidence` |
| **Critic** | LLM-as-judge emitting a groundedness score + coverage gaps |
| **Writer** | Synthesizes a Markdown report citing evidence by `[ev:i]` markers |
| **Citation Validator** | Drops unsupported claims, assigns final `[1..k]` numbering + sources list |

---

## Quick start

Requires Docker and a `.env` file with your keys (copy from `.env.example`):

```bash
cp .env.example .env          # add OPENAI_API_KEY and TAVILY_API_KEY
docker compose up --build
```

That's it. Three services start:

| Service | URL | Purpose |
|---|---|---|
| **React UI** | http://localhost:5173 | Submit questions, stream progress, read cited reports |
| **API** | http://localhost:8000 | FastAPI backend (Swagger at `/docs`) |
| **DB** | localhost:5432 | PostgreSQL + pgvector (schema applied on first boot) |

The API image has the embedding model (`BAAI/bge-small-en-v1.5`, 384-dim) baked in — no download on first run. The frontend container installs `node_modules` into a named volume on first boot (~30 s one-time cost).

```bash
# Ingest a reference document (the UI has a file picker too)
curl -X POST localhost:8000/documents/upload -F "file=@notes.pdf"

# Submit a question directly and get the session ID
curl -s -X POST localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the trade-offs between RAG and fine-tuning?"}' \
  | jq .
```

---

## What's built

| Phase | Status | Summary |
|---|---|---|
| **Foundation** | ✅ | FastAPI + PostgreSQL/pgvector, one-command Docker bring-up, baked embedding model |
| **Retrieval** | ✅ | Document ingestion (chunk + embed + store), pgvector similarity search, Tavily web search |
| **Agent graph** | ✅ | `ResearchState` contract, 5 agent nodes, LangGraph `StateGraph` with bounded critic loop + Postgres checkpointing |
| **Async API** | ✅ | `POST /research` fires background run; SSE streams per-agent progress; full status lifecycle; LangSmith tracing |
| **Reliability** | ✅ | Per-call timeouts + retries, token budgets, clean failure path, startup zombie sweep for in-flight sessions |
| **Eval harness** | ✅ | 16-item golden dataset, self-authored seed corpus, run/score/report pipeline; Ragas faithfulness + answer relevancy + context recall; LangSmith cost tracking |
| **Critic tuning** | ✅ | 3-arm A/B; tightened gate cuts hallucination 5.5% → 4.1% at near-OFF cost |
| **React UI** | ✅ | SSE-driven progress timeline, Markdown report, evidence inspector with citation-click-to-scroll, recent-runs sidebar |

---

## HTTP endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/documents` | Ingest raw text (JSON body) — chunk + embed + store |
| `POST` | `/documents/upload` | Ingest a file (`.txt` / `.md` / `.pdf`, ≤ 5 MB) |
| `POST` | `/research` | Start an async run; returns `session_id` immediately (202) |
| `GET` | `/research?limit=N` | List recent runs — drives the sidebar |
| `GET` | `/research/{id}` | Poll status; returns report + `citations_valid` + `low_confidence` once done |
| `GET` | `/research/{id}/evidence` | Structured evidence for a session |
| `GET` | `/research/{id}/stream` | SSE stream of per-agent progress |

---

## Local development

Run the DB in Docker, the backend and frontend on the host for hot-reload:

```bash
# ── Backend ──────────────────────────────────────────────────────────────────
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                    # fill in OPENAI_API_KEY + TAVILY_API_KEY

docker compose up -d db                 # Postgres + pgvector on localhost:5432
uvicorn app.main:app --reload           # http://localhost:8000

# ── Frontend (separate shell) ─────────────────────────────────────────────────
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

`VITE_API_URL` defaults to `http://localhost:8000`. Override in `frontend/.env.local` if your API port differs.

---

## Eval harness

```bash
docker compose up -d db
pip install -e ".[eval]"                 # Ragas + LangChain judge stack (pinned)

# Full pipeline over all 16 golden items (~30–60 min, costs LLM tokens)
python -m eval.run

# Cheaper alternatives
python -m eval.run --only-retrievability  # corpus check only, no LLM calls
python -m eval.run --limit 2              # smoke: first 2 items only

# Score and render
python -m eval.score                      # all six metric families
python -m eval.score --skip-ragas         # deterministic only (no judge cost)
python -m eval.report                     # writes eval/results/<run-id>.md

# A/B compare two scored runs
python -m eval.compare \
  --a <run-id-a> --b <run-id-b> \
  --name my_experiment \
  --label-a "Variant A" --label-b "Variant B"
```

Artifacts land in `eval/runs/<run-id>/` (gitignored). Per item: `report.md`, `evidence.jsonl`, `result.json`. Run-level: `scores.json`, `meta.json`, `retrievability.json`.

---

## Tests

```bash
# Fast unit tests — no external dependencies required
pytest -q

# Full suite (needs Postgres running)
docker compose up -d db
RUN_DB_TESTS=1 RUN_MODEL_TESTS=1 RUN_WEB_TESTS=1 RUN_LLM_TESTS=1 pytest -q
```

| Flag | What it enables |
|---|---|
| `RUN_DB_TESTS=1` | Tests requiring a live Postgres instance |
| `RUN_MODEL_TESTS=1` | Tests loading the real embedding model |
| `RUN_WEB_TESTS=1` | Live Tavily web-search test (needs `TAVILY_API_KEY`) |
| `RUN_LLM_TESTS=1` | Live LLM call via Planner (needs `OPENAI_API_KEY`) |

Frontend type-check:

```bash
cd frontend && npm run typecheck     # tsc -b --noEmit, must be clean
```

---

## Lint / format

```bash
ruff check .          # lint (CI gate)
ruff format .         # apply formatting
```

---

## Configuration

All settings from environment variables / `.env` (see [`.env.example`](./.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Postgres connection string |
| `OPENAI_API_KEY` | — | LLM agents + Ragas judge |
| `TAVILY_API_KEY` | — | Web search (Researcher node + live test) |
| `LANGSMITH_API_KEY` | *(optional)* | Enable LangSmith tracing |
| `LANGSMITH_PROJECT` | `autonomous-research-analyst` | LangSmith project name |
| `LLM_TIMEOUT_SECONDS` | `120` | Per-call LLM hang ceiling |
| `LLM_MAX_RETRIES` | `2` | LLM retries on transient errors |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local sentence-transformer (384-dim) |
| `MAX_ITERATIONS` | `2` | Hard cap on the critic loop-back |
| `VITE_API_URL` | `http://localhost:8000` | API base URL for the React app |
