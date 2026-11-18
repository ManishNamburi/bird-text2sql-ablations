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

---

## Experiment 04 — Three candidates + majority vote (paper §4)

C6 = C4 + voting (D19). Candidate 0 is C4's own answer. Candidates 1–2 see the linked columns in a shuffled order, and in **C6-vote** they also sample (seeds 43/44, T = 0.7). In **C6-shuffle** all three stay at T = 0, so the shuffle is the only source of diversity. Each candidate is executed, and the largest group of identical result sets wins. With no majority, C4's answer stands. The paper reports its voting only as part of the full pipeline, never isolated.

| Config | EX no hints | EX with hints | Valid SQL (no hints / hints) | pass@3 (no hints / hints) | Unanimous | Prompt tok/q | sec/q |
|---|---|---|---|---|---|---|---|
| C4 (parent) | 39.3 (32–47) | 56.7 (49–64) | 94.7% / 94.7% | — | — | 18,387 | 40.8 |
| C6-vote | 40.0 (33–48) | 58.7 (51–66) | 99.3% / 96.7% | 46.7 / 62.7 | 54% / 63% | 20,252 | 49.7 |
| C6-shuffle | 39.3 (32–47) | 60.7 (53–68) | 97.3% / 97.3% | 42.0 / 62.0 | 65% / 77% | 20,252 | 49.6 |

*pass@3 = at least one candidate is correct: the ceiling for a perfect selector. Unanimous = all three executed and returned the same rows.*

### Findings

1. **Voting barely moves accuracy.** C4 → C6-vote is +0.7 pp without hints (2 fixed, 1 broke, p = 1.0) and +2.0 pp with hints (4 / 1, p = 0.38). The dev slice had shown +6.7 pp on 4 flips; on 150 questions it shrinks to noise, the same pattern as few-shot in experiment 03.
2. **What voting reliably does is remove invalid SQL.** Valid SQL goes from 94.7% to 99.3% without hints (7 questions gained, 0 lost, p = 0.016). A query that errors can't win a vote, so a broken candidate 0 gets replaced. But most of the replacements still return the wrong rows, so EX barely moves.
3. **Shuffle-only with hints is the one significant gain, and it needs a caveat.** C4+h → C6-shuffle+h is +4.0 pp (6 fixed, 0 broke, p = 0.031). In all six, candidate 1 (the first shuffled order) won. The fixes look real: an escaped `Women''s` that C4 got wrong, `strength > 70` where the hint asks for `overall_rating > 70`, a spurious `OR` condition. But this is one of four C4 → C6 comparisons, and after a Holm correction it is not significant (adjusted p = 0.125). Treat it as a lead, not a result.
4. **Sampling makes candidates worse, not just more varied.** At T = 0.7, candidate 1 alone scores 35.3% (no hints) and 52.0% (with hints), below C4's 39.3 / 56.7. At T = 0, the shuffled candidates stay at C4's level (36.0–38.0 / 58.7–60.0). Sampling triples the distinct SQL (2.4 per question vs 1.7–2.0 for shuffle) but adds mostly wrong alternatives. A 9B model at T = 0.7 is a weaker generator, not a more diverse correct one.
5. **The selector is the bottleneck, not the candidates.** pass@3 is 46.7% (no hints) against 40.0% for the vote, so a perfect selector would gain another 6.7 pp from the same three candidates. Majority voting with three noisy candidates rarely overturns the parent: the winner differs from candidate 0 on only 7–11% of questions. That is the gap C7's SQL sanity checks are meant to close.
6. **Cost is moderate:** +2 short calls per question, +1,865 prompt tokens (+10%) and +9 s/question (+22%) over C4. Linking is still most of the cost. Executing candidates is cheap (76–474 ms per question on average), but a few candidates hit the 30 s vote timeout.

### Answer to "can we trim the prompt?" (after 04)
Voting adds no prompt sections, only calls, so it doesn't change the trimming picture. It isn't worth its 22% time cost for accuracy (n.s.), but it is a cheap way to eliminate execution errors. If one configuration were deployed today, C1 (1,910 tokens, 3.1 s) is still the value pick: C1 → C4 wasn't significant (p = 0.11), and voting adds at most 2 pp on top of C4.

---

## Experiment 05 — SQL sanity checks + correction (paper §4)

The paper's four checks (D20) run on every candidate:
- an ascending sort on a column that holds NULLs, with no filter excluding them;
- `MIN()` on such a column;
- min/max via a nested subquery instead of `ORDER BY … LIMIT 1`;
- string concatenation of fields in the output.

A flagged candidate gets up to three correction calls at T = 0. **C7** = C6-vote + checks (the paper's order: check, then vote). **C4-checked** = C4 + checks, which isolates the checks from voting. The detectors were calibrated on query-log gold SQL, never on eval. Each fires on ≤ 2.6% of gold queries.

| Config | EX no hints | EX with hints | Questions where a check fired (no hints / hints) | fixed / broke vs parent | Prompt tok/q | sec/q |
|---|---|---|---|---|---|---|
| C4 | 39.3 (32–47) | 56.7 (49–64) | — | — | 18,387 | 40.8 |
| C4-checked | 40.7 (33–49) | 57.3 (49–65) | 9 / 14 | 2 / 0 and 1 / 0 | 18,477 | 41.2 |
| C6-vote | 40.0 (33–48) | 58.7 (51–66) | — | — | 20,252 | 49.7 |
| C7 | **41.3** (34–49) | **59.3** (51–67) | 12 / 16 | 2 / 0 and 1 / 0 | 20,523 | 50.9 |

### Findings

1. **The checks rarely fire, and almost never matter.** A check fired on 6–11% of questions. A correction changed the SQL on nearly all of them, but changed the *answer* on only 2 (no hints) or 1 (with hints). C6-vote → C7 is +1.3 / +0.7 pp (2 fixed / 0 broke, p = 0.50; 1 / 0, p = 1.0). The same holds for C4 → C4-checked.
2. **Concatenation is the only check that pays.** All three fixes came from `concat`: the model wrote `first_name || ' ' || last_name AS full_name`, and BIRD's gold returns the two columns separately. That is the paper's "apparent preferences of the authors" check, and it works exactly as described.
3. **The other checks change SQL but not results.**
   - `null_order` added `IS NOT NULL` on 3–4 questions. None of those changes flipped a question.
   - `minmax_subquery` fired on 4–9 questions. The model often rewrote the query but kept the subquery, so the flag remained after three retries: 14 candidates for C7+hints, costing 29 calls. Where it did switch to `ORDER BY … LIMIT 1`, no question flipped.
   - `null_min` never fired. SQLite's `MIN` already skips NULLs, so this check is close to vacuous here (D20).
4. **No check broke anything.** That's 0 regressions across 51 flagged questions × configs. Rejecting revisions that fail to execute meant a correction never introduced an error, and the checks are narrow by construction.
5. **Cheap:** C7 costs +271 prompt tokens and +1.2 s/question over C6-vote (+2.4%). The corrections ride on short linked-schema prompts.

### The full pipeline (C7) against the single-call configs

| Comparison | Δ EX no hints | p | Δ EX with hints | p | Cost ratio (time) |
|---|---|---|---|---|---|
| C3 (fused, full schema) → C7 | +6.7 pp (18 fixed / 8 broke) | 0.076 | +6.0 pp | 0.14 | 9.4× |
| C1 (BIRD metadata, full schema) → C7 | +8.7 pp (23 / 10) | 0.035 | +8.0 pp | 0.073 | 16× |

Stacking every technique (profiling metadata, linking, voting, checks) gives +6 to +9 pp over a single call, and the paired CIs barely exclude zero. These four comparisons were chosen *after* seeing the per-step results. C1 → C7 is the only one under 0.05, and it doesn't survive a Holm correction over the four (adjusted p = 0.14). The honest summary: the full pipeline is probably better, by single digits, at 9–16× the time.

### Answer to "can we trim the prompt?" (after 05)
- **Keep the concatenation check:** it's a cheap AST check that fixes for a real BIRD convention, with zero regressions.
- **Drop `null_min`:** it can't fire usefully in SQLite.
- **`null_order` and `minmax_subquery` can go** for this model. They cost calls and fixed nothing on 150 questions.
- **Overall:** for a 9B local model, BIRD metadata on a full schema (C1, 1,910 tokens, 3.1 s) gets about 80% of the full pipeline's accuracy (32.7 vs 41.3) at 6% of its time. The linking oracle (53.3 at 748 tokens) shows where the next real gain is: recall of the right columns, not more calls on top of the wrong ones.

---

## Experiment 06 — Prompt trimming T1–T4 (research question 4)

Each trim removes one prompt section from **C3** (fused metadata, full schema, one call), the config whose cost *is* its metadata block. C7 was the planned base, but linking is ~90% of its tokens and no trim touches linking (D21). Star design: every trim is one flag away from C3. C3 was re-run inside 06 and matched experiment 01 row for row (0 new LLM calls).

| Trim | What is removed | Δ EX no hints (95% CI) | Δ EX with hints (95% CI) | Prompt tok/q | sec/q | Verdict |
|---|---|---|---|---|---|---|
| C3 | — | 34.7 | 53.3 | 8,112 | 5.4 | base |
| T1 | long → short profile summaries | +0.7 (−6.0 to +7.3) | −2.0 (−8.0 to +4.7) | 4,546 (−44%) | 4.5 | inconclusive |
| T2 | example values in the profile summaries, masked as `'…'` | −6.7 (−13.3 to +0.0) | **−10.7** (−16.7 to −4.7), Holm p = 0.012 | 7,258 (−11%) | 5.0 | **hurts** |
| T3 | BIRD value descriptions | −1.3 (−6.7 to +4.0) | −3.3 (−8.0 to +1.3) | 7,483 (−8%) | 5.1 | inconclusive |
| T4 | system prompt → one line (format instruction kept) | +4.0 (−1.3 to +9.3) | −1.3 (−6.0 to +3.3) | 8,061 (−1%) | 5.7 | inconclusive |

*Δ = trim − C3, paired bootstrap CI. Holm adjustment over all 8 tests; only T2 with hints survives it (raw p = 0.002; without hints raw p = 0.064). Verdict rule, fixed before the eval run: **safe** = CI lower bound above −5 pp in both hint settings; **hurts** = Holm p < 0.05 with Δ < 0; else **inconclusive**.*

### Findings

1. **The example values are what profiling contributes.** Masking the quoted literals in the profile summaries, while keeping their counts, lengths and formats, costs −6.7 / −10.7 pp. With hints that's 20 questions broken against 4 fixed. Of the first 8 broken questions read, 4 are wrong literal formats that the masked values would have shown:
   - qid 93: `'north Bohemia'` for `'North Bohemia'`;
   - qid 346: `'legal'` for `'Legal'`;
   - qid 47: a district-type label where the column holds the code `'52'`;
   - qid 487: the set name `'Coldsnap'` compared against a set-code column.

   No SQL contained the placeholder itself. This is the paper's core argument for profiling (§2: literal formats are what SME documentation lacks), here measured directly.
2. **Masked profiles score *below* no profiles.** T2 is under C1, which has BIRD descriptions and no profiles at all: −4.7 pp without hints, −8.7 pp with hints (raw p = 0.041). This comparison wasn't pre-registered, so it's a lead. A plausible reading: the masked summaries keep saying "this column holds specific literals" without saying which, and the model guesses, at 3.8× C1's tokens.
3. **Short profiles cost nothing measurable on eval and save 44% of the prompt** *(overturned on the 468-question test split, see below)*. T1 drops 3,566 tokens and 0.9 s per question, and its point estimates are +0.7 / −2.0. Valid SQL rises from 88.7% to 92.7%, consistent with experiment 01's finding that long prompts lead the model to the wrong table. Half the short summaries (403 of 798) still quote at least one value (e.g. "either 'D' or 'S'"), so T1 keeps much of what finding 1 says matters. But the CI lower bounds (−6.0 / −8.0) don't clear the −5 pp margin, so by the pre-registered rule T1 is **inconclusive**, not safe.
4. **BIRD value descriptions and the system rules: no measurable effect either way.** T3 (−8% tokens) is −1.3 / −3.3, and T4 is +4.0 / −1.3. T4 saves only 51 tokens, so "inconclusive" here mostly says the two rules (existing columns only; exactly the columns asked) don't move this model.
5. **The margin was too tight for n = 150, and that's the main methodological lesson.** The paired CIs are ±4.7 to ±6.7 pp wide, so a trim with a true Δ of exactly 0 fails a −5 pp non-inferiority test about half the time or more. Only the 468-question test split (CIs about ±3.5 pp) could certify T1 or T3 as safe. I chose the margin by comparing it to the detectable effect size, when it needed to exceed the expected CI half-width (see `tasks/lessons.md`).

### T1 on the 468-question test split

T1 was the one trim worth confirming, so C3 and T1 (± hints) were re-run on the test split: all 468 non-dev questions, which include the 150 eval questions. Spec, verdict rule and expected power were written in `tasks/todo.md` before the run. The rule is D21's, unchanged, with Holm over these 2 tests. With the paired SDs from eval, the expected CI half-width was ~3.6–3.9 pp, and a T1 with no true effect would have been called safe about 60% of the time. Run: 83 min, 1,272 new LLM calls, 0 errors. On the 150 eval questions every row (EX, SQL, tokens) is identical to the eval run.

| Questions | n | C3 no hints / hints | T1 no hints / hints | Δ no hints (95% CI), fixed / broke | Δ with hints (95% CI), fixed / broke | Verdict |
|---|---|---|---|---|---|---|
| all test | 468 | 41.5 / 51.7 | 37.0 / 50.4 | **−4.5** (−7.7 to −1.1), 22 / 43, Holm p = 0.025 | −1.3 (−4.1 to +1.5), 20 / 26, Holm p = 0.46 | **hurts** |
| not in eval (secondary) | 318 | 44.7 / 50.9 | 37.7 / 50.0 | −6.9 (−10.7 to −3.5), 8 / 30 | −0.9 (−3.8 to +1.9), 10 / 13 | — |

Cost on test: T1 saves 3,549 prompt tokens (−44%) and 0.65 s per question. Valid SQL is the same (90.4% vs 90.6%).

1. **Short profiles cost accuracy without hints.** −4.5 pp, significant after correction, so by the pre-registered rule T1 **hurts**. The loss is in moderate (38.8 → 30.6) and challenging (28.9 → 23.7) questions; simple ones are flat (54.7 → 56.8).
2. **With hints, T1 is within the margin.** The CI lower bound (−4.1) clears −5 pp, but "safe" needed both settings, so this is not a verdict. Hints cover most of the gap: T1 with hints answers 30 of the 43 questions T1 broke without them.
3. **The eval estimate of +0.7 was a lucky draw.** On the 318 questions outside eval the no-hints Δ is −6.9. The eval-vs-rest difference is z = −1.9 (p = 0.056), large but within what sampling explains at n = 150. A ~0 point estimate inside a ±6.7 pp CI was never evidence of "no loss", and the README's "next candidate" wording leaned on it more than it deserved.
4. **Why: the short summaries drop values, as in T2.** In a seeded sample of 12 of the 43 broken questions (no hints), 4 fail on a value the long summary quotes and the short one doesn't:
   - qid 136: long summary lists `'POPLATEK MESICNE' (monthly)`, short only says "values representing monthly…"; T1 wrote `= 'monthly'`;
   - qid 468: long lists `'Chinese Simplified'`, short says "ten distinct localized names"; T1 guessed `'zh-Hans'`;
   - qid 1344: long lists `income.source = 'Fundraising'`, short doesn't; T1 searched `budget.category` instead;
   - qid 93: long shows `'west Bohemia'` (casing pattern), short shows only `'Prague'` and `'south Moravia'`; T1 wrote `'north bohemia'`.

   The other 8 are formula, join and extra-column changes with no clear link to the trimmed text (e.g. a percentage of amounts becoming a percentage of rows), the kind of flip any prompt change causes. This is the same mechanism as T2, at a smaller dose: 403 of 798 short summaries still quote a value, against 795 of 798 long ones.

### Answer to "can we trim the prompt?" (final)
- **Don't trim the values out of profiles.** They are the part of profiling that carries the gain. Masking them (T2) and shortening the summaries so that about half lose them (T1) both cost accuracy without hints.
- **Short profiles are not a free 44%.** They cost −4.5 pp without hints on the 468-question test split. With hints they stay within 5 pp, so a hints-only deployment could consider them, but that reading wasn't pre-registered as a verdict.
- **BIRD value descriptions and the system rules** can probably go, but the evidence is "no detectable effect", not "no effect".
- **The cost picture doesn't change:** the biggest cost lever is still the C1-vs-C3 choice (24% of the tokens) and, above that, linking (experiment 02), not trimming sections inside one prompt.
