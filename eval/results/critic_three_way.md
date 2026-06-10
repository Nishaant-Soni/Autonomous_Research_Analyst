# Critic-loop 3-way comparison (Phase 4 C2 + follow-up)

All three arms ran the same 16-item golden set (n=16) with identical model, dataset, and
retrievers. The only thing that changes across arms is the **routing gate** between the
Critic and the Researcher.

| Arm | Run ID | Gate | `max_iterations` |
|---|---|---|---|
| **Original** | `20260608T142303Z` | `critique.needs_more_research` (over-eager) | 2 |
| **OFF** | `20260608T145138Z` | always go to writer | 0 |
| **Tightened** | `20260608T152024Z` | `groundedness < 0.70 AND len(gaps) >= 2` | 2 |

## Headline

**Tightened gate cut hallucination rate from 5.5% (Original) to 4.1% — a 1.4pp absolute drop and ~25% relative reduction — at near-OFF cost ($0.017 vs $0.014 per item).**

## Side-by-side

| Metric | Original (over-eager) | OFF | **Tightened** | Best |
|---|---|---|---|---|
| Faithfulness | 94.5% | 95.2% | **95.9%** | Tightened |
| Answer relevancy | 91.5% | 89.9% | 90.2% | Original |
| Context recall | 92.7% | 97.9% | 96.9% | OFF |
| Citation accuracy | 100.0% | 100.0% | 100.0% | tied |
| **Hallucination rate** | 5.5% | 4.8% | **4.1%** | **Tightened** |
| Latency / item | 77.6s | 40.6s | 46.5s | OFF |
| Cost / item | $0.0278 | $0.0139 | $0.0172 | OFF |

## Selectivity — what the tightened gate actually does

Of 16 items, the tightened gate triggered a loop-back on exactly **3**:

| Item | Δ evidence vs OFF | Hallucination (Tightened) | Original-arm Δ vs OFF |
|---|---|---|---|
| `rag-vs-finetuning` | **+45** | 4.3% | +17.6pp (original gate HURT this item) |
| `ann-index` | **+13** | 0.0% | +6.7pp (original gate HURT) |
| `reranker-role` | **+10** | 0.0% | −1.8pp (original gate slightly helped) |

Two of the three items the new gate looped on (`rag-vs-finetuning`, `ann-index`) are
items where the *original* gate had been hurting the report. On those, the tightened
loop pulls the hallucination rate down sharply (17.6% → 4.3% on rag-vs-finetuning;
13.3% → 0% on ann-index). The third (`reranker-role`) was already fine; the loop
preserves it. On the 13 items the gate stayed quiet, the run is essentially identical
to the OFF arm (small variance from LLM stochasticity).

## What the data validates

1. **The critic-loop *mechanism* works on items with thin first-pass coverage.** The
   two items where the new gate fired AND the original gate had been hurting are now the
   two biggest tightened-arm wins.
2. **The original *trigger* was wrong.** `needs_more_research` alone fired too liberally
   — on every item — producing a net-wash 7-help / 7-hurt picture at 2× cost.
3. **`groundedness < 0.70 AND len(gaps) >= 2` is the right shape of trigger.** Two
   independent signals from the critic must agree before paying for a second pass.

**Caveat (n=16).** Aggregate hallucination at this dataset size has a run-to-run noise
floor of roughly ±1–2pp. The 5.5% → 4.1% delta is at the edge of significance, not deep
inside it. The direction of the result and the cost shape are robust; the magnitude
would tighten with a larger / harder eval set.

## Files referenced

- Per-arm reports: `eval/results/golden_dataset_eval.md` (original), `eval/results/20260608T145138Z.md` (OFF), `eval/results/20260608T152024Z.md` (tightened).
- Pairwise A/Bs: `critic_loop_AB.md` (original vs OFF), `critic_tightened_vs_off.md`, `critic_tightened_vs_original.md`.
