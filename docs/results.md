# Results

All numbers are BIRD execution accuracy (EX) on the frozen **eval split: 150 MiniDev questions**, stratified by database and difficulty, with `qwen3.5:9b` (thinking off, temperature 0) via Ollama on an M3 Pro with 18 GB.
Because every config answers the same questions, comparisons are **paired**: an exact McNemar test on the questions where the two configs disagree, plus a paired bootstrap 95% CI for the difference.
Generated tables are in `results/*_analysis.md`. This page interprets them.

---

## Experiment 01 — Metadata ladder (paper Table 1)

Single LLM call per question, full schema. Only the column metadata in the prompt changes (D10).

| Config | Metadata in prompt | EX no hints | EX with hints | Prompt tok/q | sec/q | Valid SQL (no hints) | Paper (GPT-4o, no hints / hints) |
|---|---|---|---|---|---|---|---|
| C0 | DDL only | 24.0 (18–31) | 50.7 (43–59) | 824 | 2.9 | 90.0% | 49.8 / — |
| C1 | + BIRD SME descriptions | 32.7 (26–41) | 51.3 (43–59) | 1,910 | 3.1 | 94.0% | 59.6 / 72.0 |
| C2 | LLM profiling summaries | 34.0 (27–42) | 51.3 (43–59) | 7,027 | 5.1 | 84.7% | 61.2 / 72.6 |
| C3 | fused (BIRD + profiling) | 34.7 (28–43) | 53.3 (45–61) | 8,112 | 5.4 | 88.7% | 63.2 / 73.0 |

*Parentheses: Wilson 95% CI. Paper numbers are for context only. Its Table 1 ran with its full linking and voting pipeline on GPT-4o; ours is one call to a 9B local model.*

### Findings

1. **Some metadata matters; which metadata matters much less.** Adding either BIRD descriptions (**+8.7 pp**, p = 0.015) or profiling summaries (**+10.0 pp**, p = 0.017) to bare DDL is a significant gain. The paper's ordering (profile > BIRD, fused best) reproduces in direction: 32.7 → 34.0 → 34.7. But none of the steps between metadata types is significant (BIRD → profile p = 0.87; BIRD → fused p = 0.74).

2. **Automatic metadata can replace SME metadata.** Profiling summaries were generated without ever seeing the BIRD descriptions (D11), and they match them (34.0 vs 32.7, n.s.). That is the paper's central claim, reproduced on a 9B local model. It matters in practice because SME documentation is usually missing or stale.

3. **But BIRD and profiling help on *different* questions.** Between C1 and C2, 36 of 150 questions flip (19 fixed, 17 broken). That much churn under a near-zero net change means the two sources carry different information: profiles carry formats and literals, SME text carries meanings (consistent with the audit in D14). Fusing them (C3) should capture both, but the model only partly does (C1 → C3: 20 fixed, 17 broken). That points at prompt length, below.

4. **Profiling metadata is expensive, and long prompts cost validity.** C2 and C3 use **3.7–4.3× the prompt tokens** of C1 and are ~1.6× slower, for a non-significant +1–2 pp. Valid-SQL rate falls from 94.0% (C1) to 84.7% (C2). The dev-slice read-through shows why: in long prompts the model attaches columns to the wrong table (e.g. `Examination.GPT`, where `GPT` lives in `Laboratory`). This is the paper's "lost in the middle" motivation for schema linking, and experiment 02 tests it directly.

5. **Hints dominate everything.** BIRD's per-question evidence adds **+17 to +27 pp** at every metadata level (all p < 0.001). With hints on, metadata adds nothing significant (C0+h → C3+h: +2.7 pp, p = 0.60). Hints spell out the exact literal, formula or join a question needs, which is most of what metadata supplies. As the paper notes, such hints don't exist in practice, so the **no-hints column is the realistic one**.

6. **Where profiling helps: moderate questions.** No-hints EX on moderate questions goes 16.2 (C0) → 27.0 (C1) → 33.8 (C2) → 36.5 (C3). On simple questions, profiles add nothing over DDL (37.2 → 37.2). Simple questions rarely hinge on value formats, while moderate ones often filter on a specific literal or date format.

### Answer to "can we trim the prompt?" (first pass)

For a 9B model with a full schema, **BIRD SME metadata gives statistically the same accuracy as fused metadata at 24% of the prompt tokens** (1,910 vs 8,112), with higher SQL validity. Profiling metadata only pays for itself once the schema is narrowed: schema linking (experiment 02) is what makes long, rich descriptions affordable. The dedicated trimming experiments (T1–T4) will measure which *parts* of the metadata carry the gain.

### Caveats
- At n = 150 the paired 95% CIs for a difference are about ±6–8 pp wide. "Not significant" means "smaller than that, if real", not "zero".
- One model, temperature 0, one seed. Run-to-run LLM instability (paper §4.1.1) isn't measured yet.
- Profiling summaries come from the same 9B model, with a 20% error rate in the audit (D14). A stronger summarizer could widen the profiling gain.

---

## Experiment 02 — Schema linking (paper Table 2)

C4 runs the paper's §3 linking: five draft SQLs under different schema views, literal revision via the value index, then a final call on only the linked columns (D15). C4-oracle gives the final call exactly the gold SQL's columns, an upper bound that is labelled as such.

| Config | Schema in final call | EX no hints | EX with hints | Prompt tok/q | LLM calls/q | sec/q | Valid SQL (no hints) | Link recall (no hints) |
|---|---|---|---|---|---|---|---|---|
| C3 | full schema, fused metadata | 34.7 (28–43) | 53.3 (45–61) | 8,112 | 1 | 5.4 | 88.7% | — |
| C4 | LLM-linked columns (~6.5) | 39.3 (32–47) | 56.7 (49–64) | 18,387 | 6.3 | 40.8 | 94.7% | 0.85 |
| C4-oracle | gold SQL's columns (~5.1) | 53.3 (45–61) | 61.3 (53–69) | 748 | 1 | 4.0 | 94.7% | 1.00 |

*Paper Table 2 (GPT-4o, fused metadata): full schema 61.2 → its linking 63.2 → perfect linking 69.0 without hints; 71.2 → 73.0 → 77.4 with hints. The shape reproduces: a small gain from linking, a much larger one from perfect linking.*

### Findings

1. **Linking helps a little, and not significantly.** C3 → C4 is **+4.7 pp** (15 fixed, 8 broke, p = 0.21) without hints and +3.3 pp (p = 0.44) with hints. The paper's gain is similar in size (+2.0 pp, +1.8 with hints).
2. **It fixes what the long prompt broke.** Valid SQL rises from 88.7% to 94.7%, back above C1's 94.0%. The "column attached to the wrong table" errors of experiment 01 mostly disappear once the prompt holds ~6 columns instead of the whole schema. Simple questions gain most (37.2 → 55.8); moderate ones don't move (36.5 → 36.5).
3. **Recall is the bottleneck, not the narrow prompt.** The oracle beats C4 by **+14.0 pp** (23 fixed, 2 broke, p < 0.001), so a perfectly narrowed prompt is worth a lot. C4 drops at least one needed column on **67 of 150** questions. Those score **19%** (13/67), against **55%** (46/83) when every needed column survives. Improving linking recall is the clearest lever left. The gap is larger than the paper's (+5.8 pp from its linking to perfect), as expected from a 9B linker.
4. **Linking is the most expensive step so far.** It costs 2.3× C3's prompt tokens and **7.6× its time** (40.8 vs 5.4 s/question), for a non-significant +4.7 pp. The oracle shows the other side: the right 5 columns in a 748-token prompt (9% of C3) give the best accuracy at the lowest cost.
5. **Hints and linking overlap.** Hints add +17 to +19 pp to C3 and C4 (p < 0.001), but only +8.0 pp to the oracle (p = 0.017). Much of what hints supply is "which column", and the oracle already has it.

---

## Experiment 03 — Few-shot examples (paper §4)

Eight retrieved examples go into C4's final call (D16). Two pools: **train** (other databases, the paper's setup) and **querylog** (BIRD dev questions on the same database). The framing was fixed on the dev slice before this run (D17): `-sep` ends the examples with a hand-off line, and the original inline framing is kept as a pre-registered ablation.

| Config | EX no hints | EX with hints | Valid SQL (no hints / hints) | Prompt tok/q |
|---|---|---|---|---|
| C4 (no examples) | 39.3 (32–47) | 56.7 (49–64) | 94.7% / 94.7% | 18,387 |
| C5-train-sep | 38.0 (31–46) | 48.7 (41–57) | 86.0% / 84.0% | 19,037 |
| C5-querylog-sep | 39.3 (32–47) | 56.0 (48–64) | 88.0% / 92.0% | 19,356 |
| C5-querylog (inline framing) | 34.0 (27–42) | 39.3 (32–47) | 88.7% / 90.0% | 19,314 |

### Findings

1. **Few-shot doesn't help a 9B model here.** With the frozen framing, query-log examples give exactly C4's accuracy: 39.3 → 39.3 (15 fixed, 15 broke) and 56.7 → 56.0 with hints. Train examples are neutral without hints (−1.3 pp, p = 0.84) and **hurt with hints (−8.0 pp, p = 0.036)**. Few-shot also lowers valid SQL (94.7% → 84–92%).
2. **Framing decides whether few-shot helps or hurts.** The same eight query-log examples written inline, so the real question reads like a ninth example, cost **−16.7 pp with hints** against the separated framing (6 fixed, 31 broke, p < 0.001), and −17.3 pp against no examples at all (p < 0.001). The model copies literals, filters and aliases from the examples (D17). This replicates the dev finding on 150 unseen questions.
3. **The dev slice picked a winner that didn't replicate.** On dev (n = 30), separated framing looked like a gain over C4 (+13 pp without hints, +3 with hints). On eval it is 0. The *framing* effect (inline vs separated) replicated, but "few-shot helps" was noise plus selection on 30 questions. That is the reason for a frozen eval split.
4. **Same-database examples beat other-database ones,** but only with hints: querylog vs train is +7.3 pp (p = 0.10) with hints and +1.3 pp without. That fits the paper's argument for query logs: examples from the same schema transfer, examples from other schemas mostly add noise.

### Answer to "can we trim the prompt?" (after 02/03)

- **Drop few-shot** for this model: it adds ~1,000 tokens/question for no gain. Inline framing makes it actively harmful.
- **Keep linking only if recall improves.** Today it costs 7.6× the time for a non-significant +4.7 pp. The oracle's 53.3% at 748 tokens shows the payoff available from a better linker, for example the higher recall the paper gets from GPT-4o.
- **Cheapest strong config so far:** C1 (BIRD metadata, full schema, 1,910 tokens, 3.1 s/question) is statistically tied with C4 (18,387 tokens, 40.8 s): C1 → C4 is +6.7 pp (21 fixed, 11 broke, p = 0.11), or +5.3 pp with hints (p = 0.24). C4 is ~10× the tokens and ~13× the time for a gain this test can't confirm.
