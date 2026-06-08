# A/B comparison — Tightened gate vs Critic OFF

- **Tightened gate:** `20260608T152024Z` (16 items)
- **Critic OFF:** `20260608T145138Z` (16 items)

## Headline

**Tightened gate vs Critic OFF on hallucination rate: 4.1% vs 4.8% (Δ 0.7pp — within noise at this n).**

## Headline metrics

| Metric | Tightened gate | Critic OFF | Δ (Critic OFF − Tightened gate) |
|---|---|---|---|
| Faithfulness | 95.9% | 95.2% | -0.7pp ↓ |
| Answer relevancy | 90.2% | 89.9% | -0.3pp ↓ |
| Context recall | 96.9% | 97.9% | +1.0pp ↑ |
| Citation accuracy | 100.0% | 100.0% | 0.0pp — |
| Hallucination rate | 4.1% | 4.8% | +0.7pp ↑ |
| Latency / item | 46.5s | 40.6s | -5.9s |
| Cost / item | $0.0170 | $0.0139 | $-0.0031 |

## Per-item hallucination rate

| Item | Tightened gate | Critic OFF | Δ |
|---|---|---|---|
| `ann-index` | 0.0% | 6.7% | +6.7pp ↑ |
| `chain-of-thought` | 0.0% | 0.0% | 0.0pp — |
| `chunking-tradeoffs` | 0.0% | 16.7% | +16.7pp ↑ |
| `dense-vs-sparse-retrieval` | 2.0% | 5.6% | +3.6pp ↑ |
| `embeddings-semantic-search` | 3.2% | 0.0% | -3.2pp ↓ |
| `hallucination-grounding` | 9.9% | 9.2% | -0.7pp ↓ |
| `inference-cost-techniques` | 0.0% | 4.9% | +4.9pp ↑ |
| `planner-critic-pattern` | 6.7% | 0.0% | -6.7pp ↓ |
| `prompt-injection` | 7.0% | 9.1% | +2.1pp ↑ |
| `quantization-inference` | 2.8% | 2.4% | -0.4pp ↓ |
| `rag-components` | 9.0% | 10.0% | +1.0pp ↑ |
| `rag-eval-metrics` | 5.0% | 3.8% | -1.2pp ↓ |
| `rag-vs-finetuning` | 4.3% | 0.0% | -4.3pp ↓ |
| `react-pattern` | 8.6% | 2.0% | -6.6pp ↓ |
| `reranker-role` | 0.0% | 1.8% | +1.8pp ↑ |
| `untrusted-web-content` | 7.3% | 5.0% | -2.3pp ↓ |
