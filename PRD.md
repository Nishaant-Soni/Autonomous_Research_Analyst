# Product Requirements Document — Autonomous Research Analyst

**One-liner:** A multi-agent system that takes a research question, plans an investigation, gathers evidence from the web and a private document corpus, critiques and fact-checks its own findings, and produces a fully cited report. *"Perplexity + Deep Research + a diligent analyst intern."*

---

## 1. Why this project exists

### 1.1 Problem
Answering a serious research question ("What's the competitive landscape for on-device LLM inference?", "Summarize the last two years of RAG evaluation literature") is slow and fragmented. A person has to search, open dozens of tabs, read, cross-check claims, discard low-quality sources, and write it all up with citations. Single-shot LLM answers fail here because they hallucinate, can't access current information, and provide no traceable evidence.

### 1.2 Solution
An orchestrated team of specialized agents that mirrors how a good analyst works: plan → gather → criticize → revise → write → verify. Every claim in the final report traces back to a real source. The system is autonomous (runs end-to-end without hand-holding) but transparent (you can watch every agent step and inspect the evidence).

### 1.3 Why it's a strong portfolio piece
It demonstrates, in one project, the exact bundle of skills entry-level AI/ML engineering roles screen for: agent orchestration, tool calling, retrieval (RAG), self-evaluation and fact-checking loops, citation grounding, observability/tracing, and production deployment. The evaluation harness in particular is what separates a demo from an engineered system, and most candidate projects skip it.

---

## 2. Goals and non-goals

### 2.1 Goals
1. Accept a natural-language research question and autonomously produce a structured, cited report (Markdown, with optional slide export).
2. Combine *live web search* and *private document RAG* as evidence sources.
3. Run a critic/fact-check loop so the system improves its own draft before returning it.
4. Guarantee citation integrity: every factual claim maps to a retrievable source, validated programmatically.
5. Be fully observable (per-agent traces) and measurable (an automated eval suite with real metrics).
6. Ship as a containerized service with a clean API and a simple UI.

### 2.2 Non-goals (deliberately out of scope for v1)
- Multi-tenant auth, billing. *(Single-user JWT auth with per-user data isolation was added in Phase 6 to round out the full-stack story.)*
- Fine-tuning or training models.
- Real-time collaborative editing of reports.
- Supporting every LLM provider simultaneously (one default, swappable — not a model marketplace).
- A polished consumer-grade frontend. A clean, functional React UI is enough to demo and record a walkthrough — not a design-system-grade product.

---

## 3. Users and primary use case

**Primary user:** the developer/demoer (you) and technical reviewers (recruiters, hiring managers) evaluating the system.

**Core flow:**
1. User submits a question, optionally uploads reference documents first.
2. System returns a streamed progress view (which agent is doing what) and, on completion, a cited report.
3. User can inspect the evidence behind any claim and view the full execution trace.

---

## 4. Functional requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Submit a research question via API and UI | Must |
| FR-2 | Planner decomposes the question into sub-questions and a research plan | Must |
| FR-3 | Web search agent retrieves and extracts current web content | Must |
| FR-4 | RAG agent retrieves relevant chunks from an ingested document corpus | Must |
| FR-5 | Document ingestion endpoint (chunk + embed + store) | Must |
| FR-6 | Critic agent reviews draft findings and can request another research pass (bounded loop) | Must |
| FR-7 | Report writer synthesizes evidence into a structured Markdown report | Must |
| FR-8 | Citation validator deterministically confirms each cited claim maps to a stored source | Must |
| FR-9 | Async job execution with status polling (research runs take 30s–3min) | Must |
| FR-10 | Per-step progress streaming (SSE) | Should |
| FR-11 | Full execution trace viewable (via LangSmith) | Should |
| FR-12 | Export report to slides (.pptx) | Could |
| FR-13 | Automated evaluation suite runnable via CLI | Must |

---

## 5. System architecture

### 5.1 High-level flow
```
                ┌─────────────┐
   question ──▶ │   Planner   │  decomposes into sub-questions + plan
                └──────┬──────┘
                       ▼
              ┌──────────────────┐
              │   Researcher     │ ◀── tools: web_search (Tavily)
              │  (tool-using)    │ ◀── tools: rag_retrieve (pgvector)
              └────────┬─────────┘
                       ▼  evidence + draft findings
                ┌─────────────┐
                │   Critic /  │  scores groundedness, gaps, contradictions
                │ Fact-check  │
                └──────┬──────┘
            gaps found │ ok
        loop back ◀────┤────▶ proceed   (max N iterations)
                       ▼
                ┌─────────────┐
                │   Writer    │  synthesizes structured report w/ inline citations
                └──────┬──────┘
                       ▼
                ┌──────────────────┐
                │ Citation         │  deterministic check: every [n] resolves
                │ Validator        │  to a stored source chunk
                └──────┬───────────┘
                       ▼
                  final report
```

### 5.2 Orchestration: LangGraph supervisor pattern
The graph is a `StateGraph` with the agents above as nodes. A shared typed state object flows through every node. The Critic node has a conditional edge: the loop-back fires only when **both** `groundedness < 0.70` **and** `len(gaps) ≥ 2` and the iteration cap has not been reached; otherwise control proceeds to the Writer. This two-signal AND gate was tuned in a 3-arm A/B experiment (see §10) — requiring two independent signals prevents the over-eager loop-back behaviour of a single `needs_more_research` boolean. A hard `max_iterations` cap guarantees termination regardless.

LangGraph checkpoints to Postgres, so a run is resumable and inspectable, and human-in-the-loop pause points can be added later without re-architecting.

### 5.3 Shared state (the contract between agents)
```python
class ResearchState(TypedDict):
    session_id: str
    question: str
    plan: list[str]                 # sub-questions from Planner
    evidence: list[Evidence]        # accumulated, each with source ref
    draft_findings: str
    critique: Critique | None        # gaps, contradictions, groundedness score
    iteration: int
    max_iterations: int             # hard cap, e.g. 2
    report_md: str
    citations_valid: bool
    low_confidence: bool            # set by citation validator: >50% of cited claims stripped
    stripped_fraction: float        # fraction of cited sentences dropped by the validator
    user_id: int | None             # owning user (Phase 6); scopes RAG retrieval per user
```
`Evidence` carries `claim`, `content`, `source_url` or `source_chunk_id`, and `retriever` ("web" | "rag"). Keeping evidence structured from the moment it's gathered is what makes deterministic citation validation possible at the end.

---

## 6. Agent specifications

Each agent is a single LLM call (or tool-using loop) with a tightly scoped system prompt. Keeping each agent narrow is the main complexity-control lever — small, testable units beat one mega-prompt.

**Planner.** Input: the question. Output: 3–6 sub-questions and a short plan stating which need live web data vs. corpus retrieval. No tools. Cheap, fast model is fine here.

**Researcher.** Input: the plan and any prior critique. Tools: `web_search` (Tavily) and `rag_retrieve` (pgvector similarity search). It works each sub-question, collects evidence as structured `Evidence` objects, and writes draft findings. On a loop-back pass it focuses only on the gaps the Critic named.

**Critic / fact-checker.** Input: draft findings + the evidence list. It checks that each claim is actually supported by the cited evidence, flags unsupported claims, contradictions, and missing angles, and emits a JSON object with a groundedness score (0–1), a `needs_more_research` boolean, a `gaps` list, and a `contradictions` list. This is LLM-as-judge used internally, not just for offline eval. The routing gate uses `groundedness` and `len(gaps)` — not the `needs_more_research` boolean — because the two-signal AND was found more selective in the A/B (§10). The boolean is preserved on state for observability.

**Writer.** Input: validated findings + evidence. Output: a structured Markdown report (executive summary, findings by theme, conclusion) with inline numeric citation markers `[1]`, `[2]` and a sources list. It is instructed to cite only from supplied evidence and never introduce new facts.

**Citation validator.** Pure code, no LLM. Parses every `[n]` marker, confirms it resolves to a real entry in the evidence/sources table, and flags orphan citations or sources never cited. Deterministic, fast, and the cheapest possible guard against the most embarrassing failure mode.

---

## 7. Tech stack and rationale

The guiding principle is *one well-chosen tool per job*. The original brief listed several options per layer; below is the committed choice and why, optimizing for simplicity and a clean story.

| Layer | Choice | Why this and not the alternatives |
|-------|--------|-----------------------------------|
| Orchestration | **LangGraph** | Already familiar; graph + checkpointing + conditional loops map exactly to this design. Picking one of LangGraph/CrewAI/AutoGen shows decisiveness, not indecision. |
| LLM | **OpenAI (default), via a thin provider interface** | Mature SDK and first-class tool-calling, which the Researcher leans on. The interface keeps Claude/Gemini swappable without committing ops to all three. |
| Web search | **Tavily** | Built for agents: returns clean, extractable content and search in one API. SerpAPI returns raw SERPs you then have to scrape. |
| Vector store | **pgvector (inside Postgres)** | The single biggest simplification: app data, agent checkpoints, *and* embeddings all live in one Postgres instance. No extra managed service, no extra cost, fewer moving parts. Pinecone/Weaviate documented as the scale-up path if corpus exceeds ~1M chunks. |
| Embeddings | **Local HuggingFace `sentence-transformers`** (default `BAAI/bge-small-en-v1.5`, 384-dim) | Runs in-process on CPU — zero API cost, zero per-call latency, no key to manage. Demonstrates local model-serving. Weights cached into the Docker image at build so the container doesn't download on first run. |
| API | **FastAPI** | Async-native (fits long-running agent jobs), auto OpenAPI docs. |
| Datastore | **Postgres** | One store for relational data + pgvector + LangGraph checkpoints. |
| UI | **React + Vite + TypeScript + Tailwind** | A real frontend that consumes the SSE progress stream via `EventSource` and shows full-stack range. Vite keeps the toolchain light; Tailwind avoids CSS sprawl. shadcn/ui optional for ready-made components. |
| Observability | **LangSmith** | Native LangGraph tracing — per-agent inputs/outputs/latency/cost out of the box. Huge for the demo. |
| Evaluation | **Ragas + custom checks** | Purpose-built RAG/agent metrics (faithfulness, answer relevance, context recall) so you don't reinvent LLM-as-judge plumbing. |
| Packaging | **Docker + docker-compose** | One `docker-compose up` brings up API + Postgres + React frontend. |

---

## 8. Data model

```
documents      (id, source_uri, title, raw_text, metadata jsonb, user_id fk?, created_at)
chunks         (id, document_id fk, chunk_index, content, embedding vector(384))
research_sessions (id, question, status, plan jsonb, low_confidence bool,
                   stripped_fraction float, error text, user_id fk?, created_at, completed_at)
evidence       (id, session_id fk, claim, content, source_url, source_chunk_id fk?,
                retriever, created_at)
reports        (id, session_id fk, report_md, citations_valid bool,
                faithfulness float, answer_relevancy float, hallucination_rate float,
                created_at)
users          (id, email unique, hashed_pw, created_at)
refresh_tokens (jti pk, user_id fk, issued_at, expires_at, used bool)
```
The `users` and `refresh_tokens` tables and the (nullable) `user_id` FK columns on `documents` and `research_sessions` were added in Phase 6 for JWT auth and per-user data isolation (§9, §12). `user_id` is nullable so pre-auth rows migrate cleanly; new writes always set it. `chunks` carries no `user_id` — ownership is resolved by joining to `documents`.
`research_sessions.low_confidence` and `stripped_fraction` are set by the citation validator node and surfaced on `GET /research/{id}`. `research_sessions.error` holds the exception string on failed runs. The three float columns on `reports` are nullable (populated only when per-run Ragas scoring is enabled; disabled by default).
An HNSW or IVFFlat index on `chunks.embedding` handles similarity search. The vector dimension (384, for `bge-small-en-v1.5`) must match the chosen embedding model and be identical at ingest and query time — changing models means re-embedding the corpus and altering the column. Model-specific note: `bge-small-en-v1.5` reaches its best retrieval scores when *queries* (not stored documents) are prefixed with a short instruction such as `"Represent this sentence for searching relevant passages: "`. Apply the prefix only on the query path. `all-MiniLM-L6-v2` (also 384-dim, so drop-in compatible) needs no prefix, which makes it a friction-free baseline. `evidence.source_chunk_id` links corpus-derived claims back to exact chunks; web-derived claims carry `source_url`. This dual path is what lets the citation validator verify both source types uniformly.

---

## 9. API design

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check (public) |
| POST | `/auth/register` | Create a user (`{email, password}`) → `201` |
| POST | `/auth/login` | Authenticate; sets httpOnly access + refresh cookies |
| POST | `/auth/refresh` | Rotate the token pair (server-side `jti`); old refresh token invalidated |
| POST | `/auth/logout` | Clear cookies and revoke the current refresh token |
| GET | `/auth/me` | Return the current user (state rehydration) |
| POST | `/documents` | Ingest raw text (JSON body): chunk, embed, store |
| POST | `/documents/upload` | Ingest a file upload (`.txt`/`.md`/`.pdf`, ≤ 5 MB): parsed server-side via pypdf |
| POST | `/research` | Start a research session (async) → `{session_id}` |
| GET | `/research?limit=N` | List recent sessions (slim summaries, newest-first) — drives the React sidebar |
| GET | `/research/{id}` | Poll status + final report when ready |
| GET | `/research/{id}/stream` | SSE stream of per-agent progress events |
| GET | `/research/{id}/evidence` | Inspect the evidence behind the report |

All `/research*` and `/documents*` endpoints require a valid access-token cookie (Phase 6); `/health` is the only public data path. Reads are scoped to the authenticated user, and cross-user access to a session returns `404` (indistinguishable from a nonexistent ID — see §12).

Research runs are dispatched as background tasks; the client polls or subscribes to the stream. Status moves through `planning → researching → critiquing → writing → validating → done | failed`.

---

## 10. Evaluation strategy (the differentiator)

A small **golden dataset** of ~15–20 research questions, each with a known set of acceptable source domains and reference key facts. The eval harness runs the full pipeline over the set and reports:

- **Faithfulness / groundedness** — fraction of report claims supported by retrieved evidence (Ragas).
- **Answer relevance** — does the report actually address the question (Ragas).
- **Context recall** — did retrieval surface the facts needed (Ragas).
- **Citation accuracy** — % of citation markers that resolve to a real source (deterministic, from the validator).
- **Hallucination rate** — claims with no supporting evidence (inverse of faithfulness, surfaced explicitly because it's the headline number).
- **Latency and cost per run** — pulled from LangSmith.

Results are written to a versioned report so iterations are comparable. A 3-arm experiment (original gate / gate OFF / tightened gate) was run over the 16-item golden set. Key outcome: the tightened gate (`groundedness < 0.70 AND gaps ≥ 2`) cut hallucination rate from **5.5% → 4.1%** (~25% relative reduction) vs. the original over-eager gate, at near-OFF cost. The original gate fired on every item and produced a 7-help / 7-hurt / 2-tied wash; the tightened gate fires on only 3 of 16 items — exactly where a second research pass is worth paying for. Full results: `eval/results/critic_three_way.md`.

---

## 11. Observability and ops

LangSmith captures every agent's prompt, output, token usage, latency, and the full graph trace, so any run is replayable and debuggable. Structured logging at the API layer ties HTTP requests to session IDs. For v1 this is sufficient; Prometheus/Grafana is noted as a later add but deliberately skipped to avoid infra sprawl.

---

## 12. Security, cost, and reliability notes

- API keys (OpenAI, Tavily) via environment variables / `.env`, never committed; documented in `.env.example`. Embeddings run locally, so there's no key on that path.
- Per-session cost is bounded by the `max_iterations` cap and a token budget per agent.
- Web-fetched content is treated as untrusted input; the system never executes instructions found inside retrieved pages (prompt-injection guard in the Researcher system prompt).
- Every agent call wrapped with retry + timeout; a failed agent fails the session cleanly with a status rather than hanging.
- **Auth (Phase 6):** JWT-based auth over httpOnly cookies (opaque to JS, so XSS can't exfiltrate tokens; `SameSite=Strict` closes CSRF). Short-lived access token + long-lived refresh token with *real* server-side rotation backed by the `refresh_tokens` table — a redeemed `jti` is marked `used` and rejected on reuse, bounding the blast radius of a leaked token. Per-user data isolation is enforced on every read and write (including user-scoped RAG retrieval); cross-user access returns `404`, not `403`, so valid session IDs can't be enumerated. `JWT_SECRET` is required (fail-fast at startup); `COOKIE_SECURE` must be `true` over HTTPS in production.

---

## 13. Phased build plan (~2.5 weeks)

**Phase 0 — Foundation (1 day).** Repo, docker-compose (FastAPI + Postgres + pgvector), `.env.example`, provider interface stub, health check.

**Phase 1 — Retrieval layer (2–3 days).** Document ingestion endpoint (chunk + embed + store), pgvector similarity search, Tavily web search wrapper. Verify both retrievers return clean structured evidence independently before wiring agents.

**Phase 2 — Agent graph (3–4 days).** Implement Planner, Researcher, Critic, Writer, Citation validator as LangGraph nodes with the shared state. Wire the conditional critic loop with `max_iterations`. Get one end-to-end run producing a cited report.

**Phase 3 — Service + streaming (2 days).** Async `/research` job execution, status polling, SSE progress stream. LangSmith tracing on.

**Phase 4 — Evaluation (2–3 days).** Build the golden dataset, integrate Ragas, write the eval CLI and versioned results report. Tune prompts; record before/after metrics. Sub-task: A/B the two embedding models (`bge-small-en-v1.5` with query prefix vs. `all-MiniLM-L6-v2`) over the same golden set and pick based on context recall — both are 384-dim, so the swap needs no schema change. **Embedding A/B was deferred** — the 3-arm critic-loop A/B (original / OFF / tightened gate) was prioritised instead as it directly produced the headline hallucination improvement used in the README and interview story.

**Phase 5 — UI + polish (2–3 days).** React (Vite + TS + Tailwind) app: submit question, watch the SSE progress stream live, read the report, inspect the evidence behind any claim. README with architecture diagram, a recorded demo, and the eval numbers up top.

**Phase 6 — Authentication (~2 days).** JWT-based auth (httpOnly cookies, access + refresh tokens with server-side rotation via `refresh_tokens` table), per-user data isolation on all research and document endpoints, React login page + protected routes + transparent token refresh.

---

## 14. Success metrics

The project is "done" and demo-ready when: an end-to-end run completes in under ~3 minutes; citation accuracy is 100% (validator passes); faithfulness exceeds ~0.9 on the golden set; the entire system comes up with one `docker-compose up`; and the README leads with a measured hallucination-rate improvement attributable to the Critic loop.

**Achieved (tightened-gate arm, n=16 golden set):** citation accuracy 100% ✓, faithfulness 95.9% ✓, hallucination rate 4.1% (down from 5.5% with original gate) ✓, latency 46.5 s/item ✓, one-command bring-up verified ✓.

## 15. Key risks and mitigations

The main risks are scope creep (mitigated by the firm non-goals and one-tool-per-layer rule), runaway agent loops (mitigated by the hard iteration cap and per-agent token budgets), and weak retrieval producing a confident-but-wrong report (mitigated precisely by the Critic + citation validator, which is why those two components are non-negotiable rather than stretch goals).