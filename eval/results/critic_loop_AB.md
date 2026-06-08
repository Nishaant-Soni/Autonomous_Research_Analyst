# A/B comparison — Critic loop ON vs Critic loop OFF

- **Critic loop ON:** `20260608T142303Z` (16 items)
- **Critic loop OFF:** `20260608T145138Z` (16 items)

## Headline

**Critic loop ON vs Critic loop OFF on hallucination rate: 5.5% vs 4.8% (Δ 0.7pp — within noise at this n).**

## Headline metrics

| Metric | Critic loop ON | Critic loop OFF | Δ (Critic loop OFF − Critic loop ON) |
|---|---|---|---|
| Faithfulness | 94.5% | 95.2% | +0.7pp ↑ |
| Answer relevancy | 91.5% | 89.9% | -1.5pp ↓ |
| Context recall | 92.7% | 97.9% | +5.2pp ↑ |
| Citation accuracy | 100.0% | 100.0% | 0.0pp — |
| Hallucination rate | 5.5% | 4.8% | -0.7pp ↓ |
| Latency / item | 77.6s | 40.6s | -37.0s |
| Cost / item | $0.0278 | $0.0139 | $-0.0140 |

## Per-item hallucination rate

| Item | Critic loop ON | Critic loop OFF | Δ |
|---|---|---|---|
| `ann-index` | 13.3% | 6.7% | -6.7pp ↓ |
| `chain-of-thought` | 0.0% | 0.0% | 0.0pp — |
| `chunking-tradeoffs` | 11.1% | 16.7% | +5.6pp ↑ |
| `dense-vs-sparse-retrieval` | 4.0% | 5.6% | +1.6pp ↑ |
| `embeddings-semantic-search` | 3.2% | 0.0% | -3.2pp ↓ |
| `hallucination-grounding` | 11.5% | 9.2% | -2.3pp ↓ |
| `inference-cost-techniques` | 7.3% | 4.9% | -2.4pp ↓ |
| `planner-critic-pattern` | 0.0% | 0.0% | 0.0pp — |
| `prompt-injection` | 0.0% | 9.1% | +9.1pp ↑ |
| `quantization-inference` | 0.0% | 2.4% | +2.4pp ↑ |
| `rag-components` | 0.0% | 10.0% | +10.0pp ↑ |
| `rag-eval-metrics` | 5.8% | 3.8% | -1.9pp ↓ |
| `rag-vs-finetuning` | 17.6% | 0.0% | -17.6pp ↓ |
| `react-pattern` | 0.0% | 2.0% | +2.0pp ↑ |
| `reranker-role` | 0.0% | 1.8% | +1.8pp ↑ |
| `untrusted-web-content` | 14.7% | 5.0% | -9.7pp ↓ |
