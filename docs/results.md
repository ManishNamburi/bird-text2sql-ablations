# Results

All numbers are BIRD execution accuracy (EX) on the frozen **eval split: 150 MiniDev questions**, stratified by database and difficulty, with `qwen3.5:9b` (thinking off, temperature 0) via Ollama on an M3 Pro with 18 GB. The exceptions are labelled: the T1 check in §06 uses the 468-question test split, and §09 reruns the headline configs on that split on a second machine (RTX 5070, another qwen3.5 build).
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

---

## Experiment 07 — The same pipeline on qwen2.5-coder:7b (D1, D22)

Do the ladder's gains depend on the model? The seven headline configs (C0, C1, C3, C4, C6, C7, oracle), ± hints, were re-run with one change: `model: qwen2.5-coder:7b`. The profile summaries and their embeddings stay qwen3.5's (D11), so the comparison isolates linking and SQL generation. Prompts, seeds, temperatures and the vote and check rules are frozen; nothing was tuned for the coder. The spec and analysis were written in `tasks/todo.md` before any coder run. The 30 dev questions were used only as a harness check.

Run: 3,513 new LLM calls (291 min of model time), 0 errors, combined pass fully cached, largest prompt 19,505 tokens against the coder's enforced `num_ctx` of 24,576. Wall clock was 8.2 h because the Mac idle-slept for part of the night; the recorded timings are unaffected (`time.perf_counter` stops during sleep, and every call's time matches Ollama's own prompt + decode time).

### Model gap per config (primary)

| Config | qwen3.5 → coder, no hints | Δ (95% CI), fixed / broke | qwen3.5 → coder, with hints | Δ (95% CI), fixed / broke | Coder s/q (no hints) |
|---|---|---|---|---|---|
| C0 | 24.0 → 28.7 | +4.7 (−2.0 to +12.0), 18 / 11 | 50.7 → 46.0 | −4.7 (−12.7 to +3.3), 15 / 22 | 2.4 |
| C1 | 32.7 → 37.3 | +4.7 (−2.7 to +12.0), 20 / 13 | 51.3 → 46.7 | −4.7 (−12.0 to +2.7), 14 / 21 | 2.7 |
| C3 | 34.7 → 39.3 | +4.7 (−4.0 to +13.3), 26 / 19 | 53.3 → 50.7 | −2.7 (−12.0 to +6.0), 22 / 26 | 4.7 |
| C4 | 39.3 → 40.0 | +0.7 (−6.0 to +7.3), 13 / 12 | 56.7 → 49.3 | −7.3 (−16.0 to +1.3), 16 / 27 | 37.0 |
| C6 | 40.0 → 42.0 | +2.0 (−4.7 to +8.7), 15 / 12 | 58.7 → 50.7 | −8.0 (−16.0 to +0.0), 12 / 24 | 46.2 |
| C7 | 41.3 → 42.0 | +0.7 (−6.0 to +7.3), 14 / 13 | 59.3 → 50.7 | −8.7 (−16.0 to −1.3), 11 / 24 | 47.1 |
| Oracle | 53.3 → 52.7 | −0.7 (−7.3 to +6.0), 12 / 13 | 61.3 → 58.7 | −2.7 (−10.0 to +4.7), 15 / 19 | 3.8 |

*Δ = coder − qwen3.5 on the same 150 questions, paired bootstrap CI. Exact McNemar, Holm over the 14 tests: every adjusted p is ≥ 0.57 (smallest raw p = 0.041, C7 with hints). The coder ladder, its Holm-adjusted pairwise matrices and the step × model table are in `results/summary.md`.*

### Findings

1. **No config shows a significant model gap.** The point estimates lean one way per hint setting: the coder is ahead by +0.7 to +4.7 pp without hints (oracle −0.7) and behind by −2.7 to −8.7 pp with hints. The CIs are up to 17 pp wide, so "no detectable gap" is also consistent with a real loss of up to ~16 pp with hints.
2. **The ladder's shape mostly replicates.** Judged by sign and significance of each step, as for qwen3.5:
   - **BIRD descriptions** (C0 → C1, no hints): +8.7 pp, raw p = 0.015, the same as on qwen3.5. With hints: +0.7 on both.
   - **Profiling** (C1 → C3): +2.0 / +4.0, not significant (qwen3.5: +2.0 / +2.0).
   - **Linking** (C3 → C4): +0.7 / −1.3, not significant (qwen3.5: +4.7 / +3.3, also not significant). This is the one step whose sign flips with hints. The step × model difference is −4.0 (−12.0 to +4.0) without hints and −4.7 (−13.3 to +4.0) with them: unknown, not "linking is worse on the coder".
   - **Voting** +2.0 / +1.3 and **checks** +0.0 / +0.0, not significant (qwen3.5: +0.7 / +2.0 and +1.3 / +0.7).
   - **Perfect linking** (oracle vs C4): +12.7 / +9.3, both p < 0.001 (qwen3.5: +14.0, p < 0.001 / +4.7, p = 0.143).
   - **Full pipeline vs DDL** (C0 → C7, no hints): +13.3 pp, Holm p = 0.003 (qwen3.5: +17.3, Holm p = 0.001). Against C1 it's +4.7 (Holm p = 1.000; qwen3.5: +8.7, Holm p = 0.35).
3. **Linking recall is the lever on both models.** The coder's linker drops a needed column on 55 of 150 questions (recall 0.878; qwen3.5: 67, 0.85). When it does, C4 scores 21.8% (qwen3.5: 19.4%); when every needed column survives, 50.5% (qwen3.5: 55.4%).
4. **The SQL checks fire but change nothing on the coder.** They fired on 13 / 12 questions, every correction made the requested rewrite, and the final SQL differs from C6's on 8 questions in each setting, with 0 EX flips. The coder never writes string concatenation, the check behind all of qwen3.5's C7 gains (§05).
5. **Hints help the coder less (post hoc).** Hint gains per config, qwen3.5 / coder:

   | | C0 | C1 | C3 | C4 | C6 | C7 | Oracle |
   |---|---|---|---|---|---|---|---|
   | qwen3.5 | +26.7 | +18.7 | +18.7 | +17.3 | +18.7 | +18.0 | +8.0 |
   | coder | +17.3 | +9.3 | +11.3 | +9.3 | +8.7 | +8.7 | +6.0 |
   | difference (95% CI) | −9.3 (−18.7 to −0.7) | −9.3 (−17.3 to −1.3) | −7.3 (−18.0 to +3.3) | −8.0 (−17.3 to +1.3) | −10.0 (−18.7 to −1.3) | −9.3 (−18.0 to −0.7) | −2.0 (−10.0 to +5.3) |

   Pooled over the 7 configs: −7.9 pp (−14.1 to −2.0). This test wasn't pre-registered, and the 7 configs share questions, so it's a lead, not a result. Its pattern explains finding 1: the coder starts higher without hints and gains less from them. Its valid-SQL rate also drops with hints in C0, C1 and C3 (89.3 → 86.7, 92.0 → 86.0, 88.7 → 82.0), while qwen3.5's stays within 1.4 pp. In a seeded sample of 8 of the 22 C0 + hints questions qwen3.5 gets right and the coder misses (15 go the other way):
   - 2 add output columns nobody asked for (qid 366 adds `status`; qid 50 adds `AvgScrMath`);
   - 2 depart from the hint's literal mapping (qid 772 joins to colour names where the hint says `eye_colour_id`; qid 377 writes `NOT LIKE '%Angel%'` where the hint says "is not 'Angel'");
   - 3 use a wrong or non-existent column (qids 633, 1189, 954);
   - 1 is a value-case error (qid 1484: `'discount'` for `'Discount'`).

   At n = 8 that's a description, not a mechanism.
6. **Cost is about the same.** The coder is 5–17% faster per question across the 7 configs (C1 2.7 vs 3.1 s; C7 47.1 vs 50.9 s) and uses 1–13% fewer prompt tokens (13% only on C0's bare DDL), a tokenizer difference: the prompts are the same text.

### Answer to "do the gains depend on the model?"
- **Not detectably, at n = 150.** A 7B code model and a 9B general model give the same ladder shape: descriptions help without hints, linking adds little, perfect linking adds a lot, and voting and checks add almost nothing.
- **The conclusions from 01–06 hold on both models:** C1 is the cheap deployable pick, and linking recall is where the remaining accuracy is.
- **The open question is the hint × model interaction.** The coder uses hints less well. Testing it properly needs a pre-registered comparison on the 468-question test split.

---

## Experiment 08 — promptfoo's own features, measured against execution (D23)

Experiments 01–07 used promptfoo as a harness: one custom Python provider and one custom EX assertion. 08 uses the parts most promptfoo users rely on and checks each against the execution ground truth this project already has:
- the native `ollama:chat` provider;
- Python prompt functions, in a prompts × providers matrix (C1 ± hints × qwen3.5:9b / qwen2.5-coder:7b);
- an output `transform`, `transformVars`, and promptfoo's response cache;
- the built-in `is-sql` and `javascript` assertions;
- a reference-free `llm-rubric` judge;
- `PROMPTFOO_PASS_RATE_THRESHOLD` as a regression gate.

The spec and analysis were written in `tasks/todo.md` before any 08 run. The rubric wording was iterated on the 30 dev questions only, and then frozen.

Run (eval): 600 generations (two passes of 300, one model loaded at a time, judge off), then the full config with every generation served from promptfoo's cache and 600 live judge calls. 0 errors. Wall clock 4.1 h, of which the judge took 3.3 h, with no sleep events during the run.

### 1. Does the native provider reproduce the custom one?

| Cell | Same SQL as the custom provider's cached row | Of the rest: same as a fresh custom call | EX native / custom |
|---|---|---|---|
| C1 · coder | 150 / 150 | — | 37.3 / 37.3 |
| C1+hints · coder | 150 / 150 | — | 46.7 / 46.7 |
| C1 · qwen3.5 | 130 / 150 | 14 of 20 | 30.7 / 32.7 |
| C1+hints · qwen3.5 | 127 / 150 | 12 of 23 | 50.0 / 51.3 |

- **The coder cells are the clean test, and they match 300 of 300.** promptfoo's provider sends the same request as ours: same messages, same options, same reply.
- **qwen3.5 differs on 43 of 300.** 26 of those match a fresh call through our own client, so the cached reply from two days earlier is what changed. The other 17 differ from both.
- **Why:** qwen3.5 runs on Ollama's MLX runner, which doesn't reproduce every reply even between two identical requests a few minutes apart. Ollama version and model digest were unchanged. Streaming and the previous request's KV prefix were tested and ruled out (dev, `tasks/todo.md`). The coder's llama.cpp runner reproduced every reply.
- **What this means for 01–07:** every qwen3.5 number there comes from one cached run, and every rerun replays that cache, so "rerunning gives identical results" holds. A fresh rerun would not reproduce it exactly: here it moved C1's EX by −2.0 and −1.3 pp.

### 2. Cheap built-in checks against execution

Pooled over the 600 outputs. "Executes" = `valid_sql`.

| Check | Pass rate | Rejects SQL that executes | Accepts SQL that doesn't execute | Pass rate when EX is wrong |
|---|---|---|---|---|
| `is-sql` with `databaseType: Sqlite` | 99.2% | 0 / 545 | 50 / 55 | 98.6% |
| `is-sql`, default dialect (MySQL) | 92.3% | 35 / 545 (6.4%) | 44 / 55 | 92.1% |
| `javascript`: one SELECT/WITH statement | 100% | 0 / 545 | 55 / 55 | 100% |

- **`is-sql` defaults to MySQL, and that costs a SQLite user real false alarms.** It rejected 35 queries that execute, and the SQLite dialect rejected none of those (exact McNemar p < 0.001). 32 of the 35 use `CAST(… AS REAL)`, the idiom BIRD's own gold SQL uses for percentages. The coder writes it more often, so its false-reject rate is 10.5% against qwen3.5's 2.5%.
- **With the right dialect, `is-sql` is a syntax check and nothing more.** It accepted 50 of the 55 queries that fail to execute (a parser can't know which tables and columns exist) and 98.6% of the wrong answers.
- **The single-statement check never fired.** Both models always wrote one SELECT. It costs nothing, and it would catch a model that starts appending a second statement.
- None of the three is a proxy for accuracy. They are guards against malformed output, and BIRD's errors are semantic.

### 3. A reference-free LLM judge against EX

The grader is `qwen3.5:9b` (temperature 0, seed 42, thinking off, JSON output), pinned to local Ollama. Without a provider, `llm-rubric` grades remotely. It sees the question, BIRD's hint, the schema text C1 shows and the SQL. It never sees gold SQL or gold rows (tested). The frozen rubric is a strict 5-point checklist (columns and literals exist, joins, conditions, aggregations, output columns) that tells the grader that queries like these usually contain a mistake.

| Cell | EX | Judge pass rate | Judge − EX |
|---|---|---|---|
| C1 · qwen3.5 | 30.7 | 30.0 | −0.7 |
| C1+hints · qwen3.5 | 50.0 | 54.7 | +4.7 |
| C1 · coder | 37.3 | 37.3 | 0.0 |
| C1+hints · coder | 46.7 | 55.3 | +8.7 |

- **Per question, the judge is a moderate proxy.** It agrees with EX on 72.2% of outputs, κ = 0.43 (bootstrap 0.33–0.53). It passes 70.0% of correct answers (173/247) and fails 73.7% of wrong ones (260/353). That's better than the spec's expectation of "well below 0.6", and still far from a replacement for execution.
- **Per cell, the pass rates track EX, but the judge overstates the effect of hints.** On the coder, hints add +9.3 pp by EX and +18.0 by the judge: a difference of +8.7 pp (paired bootstrap CI +0.7 to +17.3). On qwen3.5 it's +19.3 vs +24.7, a difference of +5.3 (−2.7 to +14.0). The judge also swaps the top two cells: by EX, qwen3.5+hints (50.0) beats coder+hints (46.7); by the judge, the coder edges ahead (55.3 vs 54.7). This comparison was not a pre-registered test; it puts a number on the spec's "does the judge rank the cells the same way". The answer is no: an A/B decision made on the judge would have exaggerated the hint gain by up to twofold.
- **A plausible reason, not tested:** the grader sees the hint in every cell (the rubric template always renders it; the spec said "when the prompt has one", see D23). SQL written with the hint follows its formula, which a hint-reading grader checks easily. Whether the SQL is right in the database it can't check.
- **Grader errors: 33 of 600 (5.5%), counted as fails, as promptfoo does.** 29 of them hit the 4,096-token output cap: the grader, told to expect a mistake, keeps looking for one inside the JSON `reason` and never reaches a verdict. Those 29 replies are 47.5% of the judge's output tokens. A typical verdict is 119 tokens (median); the mean is 417.
- **Self-preference (exploratory): none detected.** (Judge − EX) on qwen3.5's SQL minus the same on the coder's is −2.3 pp (−9.0 to +4.7). The judge is qwen3.5.
- **Cost:** a verdict averages 2,289 prompt and 417 completion tokens, against ~1,900 and 62 for the SQL it grades. Judging took 3.3 h against 41 min for generation. A deliberative judge costs several times what it grades.

### 4. The regression gate

`make gate` runs C1 on the coder over the 30 dev questions with only the EX assertion, so promptfoo's pass rate is EX. With `PROMPTFOO_PASS_RATE_THRESHOLD=20` it exits 0 (baseline 26.7%, 8/30). At 30 it exits non-zero with promptfoo's "below the threshold" message. The coder was chosen because its runner reproduces every reply; a qwen3.5 gate could flip on an unchanged prompt. The gate needs a model, so it runs locally, not in CI.

### Answer to "what does promptfoo itself give this project?"
- **The native provider is a drop-in for single-call configs.** It reproduced the custom provider exactly where the runtime is deterministic. Python prompt functions kept the prompt text byte-identical to the pipeline's.
- **promptfoo's cache made a two-model-plus-judge matrix practical** on 18 GB: generate one model at a time, then replay everything with only the judge live.
- **Set `is-sql`'s `databaseType`.** The MySQL default rejected 6.4% of valid SQLite queries.
- **Treat an LLM judge as a screen, not a metric.** κ = 0.43 against execution, and it doubled one A/B effect. Where execution is available, it's the metric. Where it isn't, the judge's errors are correlated with the intervention being tested, which is the case that matters.
- **The reproducibility finding outranks the feature tour:** "temperature 0, seed 42" did not make qwen3.5:9b on MLX deterministic. The cache, not the seed, is what makes this project's numbers reproducible.

---

## Experiment 09 — The headline configs on the 468-question test split, on a second machine (D24)

**This section is not on the eval split, and not on the Mac.** Experiments 01–08 left four leads open on the 150 eval questions:
- the full pipeline beats C1;
- schema linking helps;
- hints help the coder less;
- the LLM judge overstates the coder's hint gain.

09 tests them on all 468 test questions, on a Windows desktop with an RTX 5070 (12 GB), Ollama 0.40.17 on the llama.cpp runner. The design:
- **Configs:** the seven headline configs (C0, C1, C3, C4, C6, C7, oracle), ± hints, on both models: 28 configs, plus the 08 judge cells (C1 ± hints × 2 models).
- **Models:** `qwen3.5:9b` here is a different build from the Mac's (Q4_K_M, digest `56671c2ab938`, on llama.cpp, against nvfp4 on MLX). `qwen2.5-coder:7b` is the same digest (`dae161e27b0e`).
- **Nothing reused:** the disk cache doesn't transfer, so every call is new on this machine. Labels carry `@5070`, so no row can join the Mac's tables.
- **Pre-registered:** the hypotheses, the question set that carries the verdict, the test family and the reading rule were written in `tasks/todo.md` before any model call on this machine.

The 150 eval questions are inside the test split, and every lead was *chosen* on them. So the verdicts use the **318 test questions outside eval**, with all 468 reported beside them. Source: `results/per_question_5070.csv` and `results/per_question_native_5070.csv`; all tables are in `results/summary.md`.

**Run:**
- **Generation:** 22,000 new LLM calls (11,055 qwen3.5, 10,945 coder), 5.2 h of model time, on 2026-11-23. Then the judge cells on 2026-11-24: 1,872 generations, then 1,872 live verdicts.
- **Clean:** 0 provider errors. The largest prompt was 19,757 tokens against the enforced `num_ctx` of 24,576 (D13). Ollama's repeat-limit abort (D24) stopped one request in an early start; in the final run that request got a normal reply, so 0 cached calls are aborts.
- **Version change:** Ollama auto-updated from 0.40.16 to 0.40.17 a minute into the first start. The job was stopped, the user chose to stay on 0.40.17, and every test-split call is from 0.40.17.
- **Hardware failures:** the GPU dropped off the bus during the cache-only combined pass, and the next replay was ended by a fatal CPU machine-check error. Neither touched a recorded reply (D24). The combined pass was finally replayed at concurrency 1 with 0 errors, and its pass counts equal the warm-ups' for all 28 configs.

### The pre-registered tests

Holm over the 6 tests in each question set. H1/H2 use an exact McNemar. H3 and H4 are interactions, so their p is a two-sided paired bootstrap. H4 uses the promptfoo-native C1 cells, with their EX and the judge on the same rows.

| # | Hypothesis | Mac, eval 150 | 5070, same 150 | **5070, fresh 318 (95% CI)** | Holm p | Verdict | 5070, all 468 |
|---|---|---|---|---|---|---|---|
| H1a | C7 > C1, no hints | +8.7 | +6.0 | **+14.8** (+9.7 to +20.1) | < 0.001 | **supported** | +12.0 |
| H1b | C7 > C1, with hints | +8.0 | +8.7 | **+11.0** (+6.3 to +16.0) | < 0.001 | **supported** | +10.3 |
| H2a | C4 > C3 (linking), no hints | +4.7 | +2.7 | +1.9 (−2.2 to +6.0) | 0.923 | unknown | +2.1 |
| H2b | C4 > C3, with hints | +3.3 | +0.0 | **+6.0** (+2.2 to +10.1) | 0.017 | **supported** | +4.1 |
| H3 | hints help the coder less (pooled over 7 configs) | −7.9 | −5.8 | +0.6 (−3.4 to +4.5) | 0.923 | unknown | −1.5 |
| H4 | the judge overstates the coder's hint gain | +8.7 | +8.0 | +6.6 (+0.6 to +12.6) | 0.106 | unknown | +7.1 |

*Δ in pp. "Supported" = Holm p < 0.05 with the predicted sign; "contradicted" = the CI excludes 0 on the other side; anything else is unknown, not "no effect". The "5070, same 150" column is descriptive: it's this machine's run on the questions the leads were chosen on.*

### Findings

1. **The full pipeline beats a single call with BIRD descriptions** (H1, supported both ways). C7 − C1 is +14.8 pp without hints (61 questions fixed, 14 broken) and +11.0 with them, both Holm p < 0.001. On eval this was +8.7 with Holm p = 0.35 (§05): a lead then, a result now. It costs 11.0× C1's time and 10.8× its prompt tokens on this machine (qwen3.5: 9.4 against 0.85 s/q).
2. **Schema linking helps with hints; without hints it's unknown** (H2). C4 − C3 is +6.0 pp with hints (30 fixed, 11 broken, Holm p = 0.017) and +1.9 (−2.2 to +6.0) without. Linking recall on all 468 is 0.864 without hints and 0.912 with them, so hints also help the linker keep the needed columns. That fits a larger gain with hints, but nothing here tests that mechanism.
3. **"Hints help the coder less" didn't replicate** (H3). On the 318 fresh questions the pooled difference is +0.6 pp (−3.4 to +4.5). On the 150 eval questions, the same machine gives −5.8, close to the Mac's −7.9. The lead belonged to the questions it was found on, not to the model or the machine, which is the selection effect the fresh-question rule was there to catch.
4. **The judge still points toward overstating the coder's hint gain, but it doesn't pass the bar** (H4). The difference is +6.6 pp on the fresh questions (CI +0.6 to +12.6, bootstrap p = 0.035), and +8.0 and +7.1 on the eval and all-468 sets. After Holm over 6 it's p = 0.106, so the pre-registered reading is "unknown". It's the same direction and size as 08's +8.7.
5. **The ladder's shape replicates on both models, at 468 questions.** All steps below are unadjusted, so they're descriptive (`results/summary.md` has both ladders):
   - **BIRD descriptions** (C0 → C1, no hints): +9.4 (qwen3.5) and +8.8 (coder), both p < 0.001.
   - **Profiling** (C1 → C3, no hints): +6.8 (p < 0.001) and +4.5 (p = 0.019). On eval it was +2.0 on both models, not significant, so at n = 468 the paper's profiling gain shows up on its own.
   - **Voting and checks** (C4 → C6 → C7): +0.0 to +1.7 per step on qwen3.5, none with p < 0.05. On the coder, voting with hints is +2.6 (p = 0.004); every other voting and check step is between −0.2 and +0.6.
   - **Perfect linking** (oracle vs C4): +11.3 / +6.6 (qwen3.5) and +9.4 / +10.5 (coder), all p < 0.001.
6. **Same questions, other machine: the coder reproduces the Mac; qwen3.5's new build is a little lower.** On the 150 eval questions, the coder's EX is within ±2.0 pp of the Mac's in every cell. With hints it's identical per question on C1, C3, C4 and the oracle: same digest, same answers. The 5070's qwen3.5 build is lower in 13 of 14 cells, by −0.7 to −4.7 pp (one cell +0.7). No CI excludes 0; the closest is the oracle without hints, −4.7 (−9.3 to 0.0). That's a build-and-runtime difference, not a model effect, and it isn't tested.
7. **The judge on the 5070 behaves as in 08.**
   - It agrees with EX on 70.8% of the 1,872 outputs, κ = 0.40 (08: 72.2%, κ = 0.43).
   - Sensitivity is 70.7% and specificity 70.8%.
   - 58 verdicts (3.1%) were unreadable and count as fails.
   - By the judge, hints add +18.8 pp on qwen3.5 and +19.0 on the coder; by EX, +13.7 and +12.0.
8. **The native provider matched the custom one less often here, for both models.** 1,628 of 1,872 native SQL strings equal the custom provider's cached reply:
   - coder: 417 and 436 of 468 (08 on the Mac: 300 of 300);
   - qwen3.5: 377 and 398.

   Of the 244 that differ, 127 equal a fresh call through `birdeval.llm.chat`: Ollama now gives a different reply than the one it gave a day earlier. The other 117 equal neither. EX moves by 0.7 pp or less in each cell (native vs custom: 31.6 / 31.8, 45.3 / 44.7, 34.6 / 35.3, 46.6 / 47.2).

   This fits what Step 1 found. 10 calls repeated in the same order after a model reload were 10/10 identical on both models. But one C4-oracle request aborted three times when sent alone, and got a normal reply inside the pipeline. So on 0.40.17's llama.cpp runner a reply depends on server state (which cached prompt prefix it reuses), not on the request alone. **Every 09 number is reproducible through the disk cache, not from the request.** A shuffled-order determinism check that would size this wasn't run.
9. **Cost on this machine:** C1 takes 0.85 s per question (coder 0.57), and C7 9.4 s (coder 6.4). On the same 150 eval questions the 5070 is 3.5–7.4× faster per question than the Mac, and C7's gain is the largest (5.4× for qwen3.5, against 3.5× for C1). So C7 vs C1 is 16× the time on the Mac and 11× here. Absolute seconds stay machine-specific.

### Answer to "do the eval leads hold?"
- **Two of the four do: the full pipeline beats C1 by 11–15 points, and linking helps when hints are given.** Both are larger on the fresh questions than on eval.
- **The hint × model lead was a property of the eval questions.** On the same machine it is −5.8 on eval and +0.6 on the 318 fresh questions.
- **The judge's bias toward the coder's hint gain is consistent in size (+6.6 to +8.7 pp across sets) but not established** after correcting for the six tests.
- **The deployment pick changes.** At the eval split's precision, C1 looked like the cheap pick, with the pipeline's gain uncertain. On 468 questions the pipeline's +12.0 pp without hints is real. Whether it's worth 11× the time per question is a product decision, and the numbers for it are now known.
