# Autonomous Research Analyst

A multi-agent system that takes a research question, plans an investigation, gathers
evidence from the web and a private document corpus, critiques and fact-checks its own
findings, and produces a fully cited report.

See [`PRD.md`](./PRD.md) for the product spec.

## Quickstart (Phase 0)

```bash
# Bring up the API + Postgres (with pgvector)
docker-compose up --build

# Liveness check
curl localhost:8000/health   # -> {"status":"ok"}
```

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # fill in keys

uvicorn app.main:app --reload # http://localhost:8000/docs
pytest                        # run the test suite
```
