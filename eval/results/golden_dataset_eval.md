# Eval report — `20260608T142303Z` (golden dataset)

- **Items scored:** 16
- **Corpus retrievability:** PASSED

## Headline metrics

| Metric | Mean |
|---|---|
| Faithfulness | 94.5% (n=16) |
| Answer relevancy | 91.5% (n=16) |
| Context recall | 92.7% (n=16) |
| Citation accuracy | 100.0% (n=16) |
| Hallucination rate (1 − faithfulness) | 5.5% (n=16) |
| Latency / item | 77.6s (n=16) |
| Cost / item | $0.0278 (n=16) |

## Per-item breakdown

| Item | Faith. | Ans.Rel. | Ctx.Recall | Cite.Acc. | Hallucination | Latency | Cost |
|---|---|---|---|---|---|---|---|
| `ann-index` | 86.7% | 87.0% | 100.0% | 100.0% | 13.3% | 39.8s | $0.0118 |
| `chain-of-thought` | 100.0% | 95.5% | 100.0% | 100.0% | 0.0% | 57.2s | $0.0200 |
| `chunking-tradeoffs` | 88.9% | 98.5% | 100.0% | 100.0% | 11.1% | 76.8s | $0.0237 |
| `dense-vs-sparse-retrieval` | 96.0% | 94.6% | 100.0% | 100.0% | 4.0% | 81.4s | $0.0270 |
| `embeddings-semantic-search` | 96.8% | 93.5% | 100.0% | 100.0% | 3.2% | 23.3s | $0.0081 |
| `hallucination-grounding` | 88.5% | 90.5% | 50.0% | 100.0% | 11.5% | 99.0s | $0.0384 |
| `inference-cost-techniques` | 92.7% | 90.0% | 100.0% | 100.0% | 7.3% | 115.9s | $0.0495 |
| `planner-critic-pattern` | 100.0% | 88.6% | 100.0% | 100.0% | 0.0% | 86.2s | $0.0395 |
| `prompt-injection` | 100.0% | 89.2% | 100.0% | 100.0% | 0.0% | 83.1s | $0.0351 |
| `quantization-inference` | 100.0% | 98.7% | 100.0% | 100.0% | 0.0% | 88.7s | $0.0335 |
| `rag-components` | 100.0% | 82.5% | 100.0% | 100.0% | 0.0% | 71.2s | $0.0261 |
| `rag-eval-metrics` | 94.2% | 94.9% | 100.0% | 100.0% | 5.8% | 111.7s | $0.0342 |
| `rag-vs-finetuning` | 82.4% | 91.5% | 33.3% | 100.0% | 17.6% | 147.9s | $0.0385 |
| `react-pattern` | 100.0% | 84.2% | 100.0% | 100.0% | 0.0% | 16.8s | $0.0059 |
| `reranker-role` | 100.0% | 92.1% | 100.0% | 100.0% | 0.0% | 59.9s | $0.0259 |
| `untrusted-web-content` | 85.3% | 92.0% | 100.0% | 100.0% | 14.7% | 82.9s | $0.0284 |
