# A/B comparison — Tightened gate vs Original (over-eager)

- **Tightened gate:** `20260608T152024Z` (16 items)
- **Original (over-eager):** `20260608T142303Z` (16 items)

## Headline

**Tightened gate cut hallucination rate from 5.5% to 4.1% (Δ 1.4pp).**

## Headline metrics

| Metric | Tightened gate | Original (over-eager) | Δ (Original (over-eager) − Tightened gate) |
|---|---|---|---|
| Faithfulness | 95.9% | 94.5% | -1.4pp ↓ |
| Answer relevancy | 90.2% | 91.5% | +1.2pp ↑ |
| Context recall | 96.9% | 92.7% | -4.2pp ↓ |
| Citation accuracy | 100.0% | 100.0% | 0.0pp — |
| Hallucination rate | 4.1% | 5.5% | +1.4pp ↑ |
| Latency / item | 46.5s | 77.6s | +31.2s |
| Cost / item | $0.0170 | $0.0278 | +$0.0108 |

## Per-item hallucination rate

| Item | Tightened gate | Original (over-eager) | Δ |
|---|---|---|---|
| `ann-index` | 0.0% | 13.3% | +13.3pp ↑ |
| `chain-of-thought` | 0.0% | 0.0% | 0.0pp — |
| `chunking-tradeoffs` | 0.0% | 11.1% | +11.1pp ↑ |
| `dense-vs-sparse-retrieval` | 2.0% | 4.0% | +2.0pp ↑ |
| `embeddings-semantic-search` | 3.2% | 3.2% | 0.0pp — |
| `hallucination-grounding` | 9.9% | 11.5% | +1.7pp ↑ |
| `inference-cost-techniques` | 0.0% | 7.3% | +7.3pp ↑ |
| `planner-critic-pattern` | 6.7% | 0.0% | -6.7pp ↓ |
| `prompt-injection` | 7.0% | 0.0% | -7.0pp ↓ |
| `quantization-inference` | 2.8% | 0.0% | -2.8pp ↓ |
| `rag-components` | 9.0% | 0.0% | -9.0pp ↓ |
| `rag-eval-metrics` | 5.0% | 5.8% | +0.8pp ↑ |
| `rag-vs-finetuning` | 4.3% | 17.6% | +13.4pp ↑ |
| `react-pattern` | 8.6% | 0.0% | -8.6pp ↓ |
| `reranker-role` | 0.0% | 0.0% | 0.0pp — |
| `untrusted-web-content` | 7.3% | 14.7% | +7.4pp ↑ |
