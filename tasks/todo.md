# Plan — BIRD text-to-SQL ablations with promptfoo on a local LLM

Status: **APPROVED 2026-11-16 — Phase 0 in progress.**

### Check-in decisions (2026-11-16)
- **Model:** `qwen3.5:9b` (thinking off) is the main model. `qwen2.5-coder:7b` reruns the headline configs as a model-size check.
- **Eval size:** stratified 150 for every config, plus all 500 for 2–3 headline configs.
- **Ollama:** the user upgrades the app themselves (0.5.7 → current).
- **Installs and downloads:** approved (Node 22, promptfoo, uv Python env, minidev.zip, Ollama models).

## 1. What we are reproducing

The paper (AT&T CDO, 2025) reached #1 on the BIRD leaderboard by stacking several techniques on GPT-4o.
It reports these ablations on MiniDev (500 questions):

| Paper Table 1: metadata × hints        | EX    |
|----------------------------------------|-------|
| No metadata, no hints                  | 49.8% |
| BIRD (SME) metadata, no hints          | 59.6  |
| Profiling metadata, no hints           | 61.2  |
| Fused metadata, no hints               | 63.2  |
| BIRD metadata, hints                   | 72.0  |
| Profiling metadata, hints              | 72.6  |
| Fused metadata, hints                  | 73.0  |

| Paper Table 2: schema linking (fused)  | no hints | hints |
|----------------------------------------|----------|-------|
| Full schema                            | 61.2     | 71.2  |
| Their LLM schema linking               | 63.2     | 73.0  |
| Perfect (oracle) schema linking        | 69.0     | 77.4  |

The paper does **not** isolate few-shot examples, multi-candidate voting, or the SQL sanity checks.
Those are the gaps this project fills, along with the token cost of each step.

**Research questions**
1. Do the paper's gains (metadata, profiling, schema linking) carry over to a ~7–9B local model?
2. What does each step add, as Δ execution accuracy with a 95% CI and a paired test?
3. What does each step cost, in prompt tokens and seconds per question?
4. Which prompt sections can we trim (long → short profiles, drop sample values, drop instructions) without a significant accuracy loss?

## 2. Key design decisions (proposed — see docs/decisions.md once written)

| Decision | Proposal | Tradeoff |
|---|---|---|
| Model | **Decided:** `qwen3.5:9b` (6.6 GB, Q4_K_M, thinking off) as the main model, with `qwen2.5-coder:7b` (4.7 GB) rerunning the headline configs. | Qwen3.5-9B is newer and likely stronger, but about 40% slower and needs the Ollama upgrade. The coder 7B is code-specialized and fast. Running both shows whether the gains depend on model size. 14B models (9 GB) leave little room for an 8–16K context on 18 GB. Nemotron-3-nano-4B is small; nemotron-3.5-bolt is multimodal and 7.9 GB, so it is not a good fit. |
| Eval set | Stratified sample of **150** MiniDev questions (by database × difficulty, seed 42), plus a separate **30-question dev slice** for prompt iteration. Optionally all 500 for the 2–3 headline configs overnight. | 150 questions gives a ±8 pp 95% CI on a single accuracy. Paired McNemar tests catch smaller differences because both configs answer the same questions. The full 500 would take about 3× longer per config. |
| Harness | promptfoo drives everything. One **custom Python provider** runs the pipeline, with flags per technique. One **custom Python assertion** executes predicted and gold SQL on SQLite and compares result sets (BIRD EX). | Built-in `ollama:` providers can't do multi-step pipelines (linking, voting). A single provider with flags guarantees that ablations differ only in their flags. |
| Profiling LLM | The same local model writes the profile summaries, offline, once, cached to disk. | The paper used GPT-4o. A weaker summarizer may shrink the profiling gain. That is itself a finding to report. |
| Vector search | `nomic-embed-text` via Ollama plus numpy cosine similarity. Values index via `datasketch` MinHash-LSH on shingles, as in the paper. | The paper used FAISS. At about 1K columns, brute-force numpy is exact and simpler. |
| Few-shot pool | BIRD **dev questions not in MiniDev**, on the same 11 databases, treated as the "query log" from paper §5–6. Questions masked before embedding, top-k=4 (paper: 8). | The paper used the BIRD train set (different DBs, a ~9 GB download). Same-DB examples are closer to the industrial query-log case the paper argues for, but they are easier. We document this and never include any eval question in the pool. k=4 instead of 8 keeps the prompt small for a 7B model. |
| Prompt caching | Put the schema block **first** and the question **last**, and run tests grouped by database with concurrency 1. Ollama then reuses the KV cache for the shared prefix. | Big speedup on Apple Silicon, where prefill dominates. Concurrency 1 makes wall-clock times comparable between configs. |

## 3. Ablation ladder (each config changes exactly one thing)

Metadata block (paper Table 1):
- [ ] **C0 Baseline** — `CREATE TABLE` DDL only + question.
- [ ] **C1 + BIRD SME metadata** — column descriptions and value descriptions from `database_description/*.csv`.
- [ ] **C2 Profiling metadata** — LLM-summarized profiles instead of BIRD metadata.
- [ ] **C3 Fused metadata** — BIRD + profiling.

Schema linking (paper Table 2):
- [ ] **C4 C3 + schema linking** _(implemented + unit-tested 2026-11-16, D15; config `02_linking.yaml`; dev-verified 2026-11-16: 0 errors, link recall 0.93)_ — — simplified paper §3 algorithm: generate SQL under 3 schema variants (focused/minimal, full/minimal, focused/maximal), collect fields, and fix literals via the LSH value index with ≤1 retry.
- [ ] **C4-oracle Perfect linking** _(implemented, D15)_ — — fields taken from the gold SQL. This is an upper bound, labelled as oracle.

Paper §4 extras (not ablated in the paper):
- [ ] **C5 C4 + few-shot** _(implemented 2026-11-16, D16)_: two pools: `train` (8 examples from 69 other DBs, the paper's setup) and `querylog` (8 examples from same-DB BIRD dev minus MiniDev). Config `03_fewshot.yaml`.
- [x] **C6 C4 + 3 candidates + majority vote** _(done 2026-11-17, D19; parent changed from C5 to C4 after few-shot gave no gain)_ — vary seed and schema field order; vote on execution results (execution replaces the sqlglot validity check).
- [x] **C7 C6 + SQL sanity checks and correction** _(done 2026-11-17, D20)_ — NULL ordering for ASC/MIN, subquery-vs-ORDER BY, string concatenation, with ≤3 retries (paper).

Cross factor:
- [ ] **Hints (evidence) on/off** for C0, C1, C3, C4, and C7 (the paper's main contrast).

Prompt trimming (on the best non-oracle config):
- [ ] **T1** long profile → short profile.
- [ ] **T2** drop the sample/common values from profiles.
- [ ] **T3** drop the BIRD value descriptions and keep only column descriptions.
- [ ] **T4** strip the system instructions down to one line.

## 4. Metrics captured per test (promptfoo named metrics)

- `ex` execution match (0/1). This is the primary metric.
- `valid_sql` (does it parse and execute without error).
- `prompt_tokens`, `completion_tokens`, `latency_ms`, and `llm_calls` (from provider metadata).
- Sliced by `difficulty` and `db_id` via test metadata.
- Analysis script: accuracy with Wilson 95% CI, Δ vs parent config, McNemar exact p-value, and an accuracy-vs-prompt-tokens Pareto chart.

## 5. Implementation steps

### Phase 0 — Environment (needs the user's OK on downloads and installs)
- [x] `git init`, `.gitignore` (data/, results raw, promptfoo DB, PDF). _(LICENSE + README skeleton moved to Phase 5.)_
- [x] Upgrade Ollama 0.5.7 → current 0.40.x (user approved 2026-11-16). The app was installed manually in `/Applications/Ollama.app`, so the options are the app's built-in updater or `brew install --cask ollama-app --force`. Re-verify `llama3.2` still loads afterwards.
- [x] Node 22 via `brew install node@22` (keg-only, doesn't replace Node 20). Pin `promptfoo` in `package.json`.
- [x] Python env via `uv` (`pyproject.toml`): sqlglot, datasketch, numpy, pandas, scipy/statsmodels, requests, matplotlib, pytest.
- [x] `ollama pull qwen3.5:9b` (6.6 GB), `qwen2.5-coder:7b` (4.7 GB), and `nomic-embed-text` (0.27 GB).
- [x] Download `minidev.zip` (801 MB) from the official BIRD mirror to `data/raw/`, unzip, and verify 500 questions and 11 SQLite DBs.
- [ ] Get BIRD dev questions for the few-shot pool (check whether minidev.zip already contains `dev.json`; otherwise download dev questions only).
- [x] Smoke test: one question end-to-end through Ollama, timing prefill vs generation.

### Phase 1 — Data and eval set
- [x] `scripts/make_subset.py`: stratified dev 30 / eval 150 / test 468 (all non-dev), seed 42 → `data/subset_ids.json` (D6).
- [x] `src/birdeval/sqlexec.py`: read-only SQLite execution with a 30 s timeout; BIRD EX comparison (set equality of result rows).
- [x] **Validate the evaluator:** gold vs gold is 100%, known-wrong SQL is 0%, and the logic matches the official `calculate_ex` line by line (D9).
- [x] pytest for the evaluator and the schema renderers.

### Phase 1 results (2026-11-16)
- Frozen splits: dev 30 / eval 150 / test 468 (D6). Test files are in `promptfoo/tests/`, sorted by DB.
- Harness verified on dev: 4 configs × 30 questions in 8.4 min wall clock. The combined pass took 4 s, confirming all cache hits. 0 provider errors.
- Dev numbers (n=30, CIs ±15 pp, a **sanity check only, not results**): C0 20.0%, C1 23.3%, C0+hints 36.7%, C1+hints 33.3%. Hints help most, as in the paper. C1 doubles prompt tokens (881 → 2,011 per question).
- Failure read-through found no harness bugs. Errors are the paper's targets: wrong literal case (`'banned'` vs `'Banned'`), literal in the wrong column (`setCode = 'Coldsnap'`), unknown date formats, and gold-SQL quirks.
- Tests: 36 passing (evaluator + schema renderer).

### Phase 2 — Metadata (offline)
- [x] `scripts/profile_db.py`: per-column nulls, distinct count, min/max, length, character classes, top-10 values → English profile (paper §2.1).
- [x] `scripts/summarize_profiles.py`: LLM short and long summaries per column, cached JSON. Spot-check 20 by hand and record in docs.
- [x] `scripts/build_indexes.py`: MinHash-LSH value index (N=10,000 distinct values per column) and embeddings of long summaries.

### Phase 2 results (2026-11-16)
- **Profiles:** 798 columns in 65 s (SQLite). They include storage class, format patterns, and top values (D11).
- **LLM summaries:** 798 × short/long in 70 min at ~5.3 s/column. Two prompt fixes came from an 8-column trial (D11).
- **Audit** of 20 random summaries: 60% OK / 20% MINOR / 20% WRONG. Formats are reliable; the meanings of cryptic codes are not (D14, `docs/summary_audit.md`).
- **Value LSH index:** 531K values, 38 s. Reproduces the paper's §3.1 Fresno example (D12).
- **Embeddings:** 798 column vectors (nomic-embed-text), 11 s.
- **Prompt size:** profiles multiply it 5–10× (EF2 fused: 19K tokens). The MLX runner ignores `num_ctx`, so there's now one global 24,576 plus a truncation guard (D13).
- **Dev slice (n=30, sanity only):** C0 20.0 / C1 23.3 / C2 33.3 / C3 30.0; with hints 36.7 / 33.3 / 46.7 / 43.3. The direction matches the paper (profiling ≥ SME metadata). Cost is 0.9K → 7.4K prompt tokens and 3.8 → 15.5 s/question. Invalid SQL is mostly columns attached to the wrong table in long prompts, which motivates schema linking.
- 42 tests passing.
- **Still open:** the few-shot pool source (needed for C5).

### Phase 3 — promptfoo harness _(single-call parts pulled into Phase 1 on 2026-11-16)_
- [x] `promptfoo/providers/pipeline.py`: config flags → pipeline; returns SQL plus token, latency, and call metadata.
- [x] `promptfoo/asserts/ex_match.py`: EX metric plus `valid_sql`.
- [ ] `promptfoo/configs/*.yaml`: one file per experiment group; tests generated from the subset JSON. _(01_metadata.yaml done; 02+ after Phase 2.)_
- [x] `scripts/run_ablation.py`: two-pass runner (per-config warm-up, then combined eval), with a summary table per run (D8).
- [x] `src/birdeval/schema.py`: canonical renderer, DDL ± BIRD metadata, 36 tests (D10).
- [ ] Iterate prompts **only on the 30-question dev slice**; freeze prompts before running on the 150.

### Phase 3b — promptfoo features (approved and done 2026-11-16, D18; verified on 02 dev: identical EX, 0 new LLM calls, prompt visible in viewer)
- [x] Provider returns top-level `prompt` (actual final messages) and `latencyMs` (original summed latency) so the viewer shows real prompts and true timings.
- [x] Explicit Python timeout: `REQUEST_TIMEOUT_MS` = 30 min in the runner (default 300 s per test; slowest dev question 181 s). `workers` left alone: warm-ups run at -j 1 and the combined pass is cache-only.
- [x] `derivedMetrics`: EX % and valid-SQL % per config.
- [x] `--tag split=… --tag experiment=…` on combined evals.
- [x] Combined pass is cache-only (`BIRDEVAL_CACHE_ONLY=1` → `CacheMiss`), and the runner fails on any provider error.
- [x] Record what was skipped and why (resume, repeat, native ollama provider, generators, hooks) in `docs/decisions.md`.

### Phase 4 — Runs
- [x] Metadata ladder C0–C3 (± hints) on eval (150): 1 h 33 min, 0 errors. See `docs/results.md` §01 and `results/01_metadata__eval_analysis.md`.
- [x] Linking C4 and C4-oracle on eval (150): 3 h 10 min, 0 errors. See `docs/results.md` §02.
- [x] C5 on eval (150): 2 h 5 min, 0 errors. See `docs/results.md` §03.
- [x] C6 on eval (150): 94 min, 0 errors. See `docs/results.md` §04.
- [x] C7 on eval (150): 15 min, 0 errors. See `docs/results.md` §05.

#### C7 spec — SQL sanity checks + correction (paper §4, written 2026-11-17)
Paper §4: each candidate is checked for constructions "likely to indicate an incorrect response". If one is found, "the LLM is asked for a correction with up to three retries"; then the vote. The four checks it names:
- (a) **NULL ordering:** "ensure a NOT NULL predicate on f" if the output is ordered ascending on f.
- (b) the same, if the select list contains `MIN(f)`.
- (c) **min/max via a nested subquery** instead of `ORDER BY … LIMIT`.
- (d) **string concatenation** of fields instead of returning them separately.

- **Parent is C6-vote, the pre-registered C6.** C6-shuffle+hints looked better on eval, but picking it now would be choosing on the eval split (its p = 0.031 doesn't survive Holm). Checks run on every candidate *before* the vote, as in the paper.
- **Second config, C4-checked = C4 + checks** (single candidate, no vote). It isolates what the checks do on their own. Paper and C6 order are unaffected, and it is one change from C4.
- **Detectors** (`src/birdeval/sqlchecks.py`, sqlglot AST, resolved through the existing qualifier so aliases map to real columns):
  - (a)/(b) fire when `f` is ordered ASC (explicit or default) or appears in `MIN(f)`, and no `f IS NOT NULL` (or a comparison that already excludes NULL, e.g. `f > x`) is in that SELECT's WHERE/JOIN.
  - **Guard (declared deviation):** fire only if `f` actually contains NULLs in the database (one cached `SELECT 1 … WHERE f IS NULL LIMIT 1`). Otherwise the check costs a call and can't change the result.
  - (c) fires on `col = (SELECT MAX/MIN(col) …)`.
  - (d) fires on `||` or `CONCAT` in the outer select list.
- **Correction:** the candidate's own messages + its SQL as the assistant turn + a user turn naming each fired check and asking for a revised query. T = 0, same seed as the candidate.
  - Re-check after each revision, up to 3 retries.
  - If a revision fails to execute, keep the last version that did (corrections must not create errors).
- **Calibrating without touching eval:** run the detectors over the **gold SQL of the query-log pool** (BIRD dev minus MiniDev, same 11 DBs). A check that fires often on gold encodes a preference BIRD's authors don't share, so it gets dropped *before* any model run. The correction-prompt wording may be iterated on dev only, then frozen.
- **Diagnostics:** fired checks per candidate (by type), retries used, whether the final SQL still trips a check, and whether a correction changed the result rows. Analysis reports, per check: firing rate, and EX before vs after on the questions where it fired (paired).
- **Config** `promptfoo/configs/05_checks.yaml`, ± hints: C4-linked, C4-checked, C6-vote, C7 (parents cached).
- **Cost.** Only flagged candidates pay, at ~1 short call per retry. Estimate: ~15–25 min on dev, ~45–75 min on eval.
- **Steps.**
  - [x] `sqlchecks.py` (detectors + NULL guard), 19 detector tests + 4 correction-loop tests (87 total pass). A test caught a scoping bug: a subquery's `IS NOT NULL` had been counted for the outer ORDER BY.
  - [x] Gold-SQL firing rates on the query-log pool (1,035): null_order 0.7%, null_min 0.2%, minmax_subquery 2.6%, concat 1.1%. All four are under 10%, so all are kept.
  - [x] Correction loop in `pipeline.py` (`checks`, `check_retries`), per candidate before the vote. Defaults are byte-identical (C4/C6-vote rows all cache hits).
  - [x] Dev run (3.2 min): checks fire on 1–2 of 30 questions per config; every correction did what was asked (adds `IS NOT NULL`, or switches to ORDER BY … LIMIT 1); 1 fixed / 0 broke overall. Wording frozen unchanged. Eval run started.
  - [x] Eval: C7 41.3 / 59.3 vs C6-vote 40.0 / 58.7 (2/0 and 1/0 flips, n.s.); all fixes from `concat`; 0 regressions. Full pipeline C1 → C7 +8.7 pp (p = 0.035, Holm 0.14). Written up in `docs/results.md` §05 and D20.

#### C6 spec — 3 candidates + majority vote (paper §4, written 2026-11-17)
Paper §4: three candidates, diversified by "changing the LLM randomization seed" and "randomizing the order of the (schema linking-reduced) schema fields"; each is executed, results become sets, and if two agree one of them is chosen, else one is picked at random.
- **Parent is C4, not C5.** Few-shot gave no gain on eval and is dropped (results §03), so C6 = C4 + voting. That keeps C6 one change from the best non-oracle config. (Deviation from the original ladder, recorded as D19.)
- **Candidates.** Linking runs once and is shared (cache hits from 02). Candidate 1 is exactly C4's final call (cache hit). Candidates 2 and 3 use the same linked columns with the column order shuffled within each table (`shuffle_seed` 1, 2) and LLM seeds 43, 44.
- **Temperature.** With temperature 0, a seed change does nothing (greedy decoding), so the paper's "seed" source needs sampling. Fixed a priori, not tuned: T = 0.7 for candidates 2–3 (Qwen's recommended non-thinking setting); candidate 1 stays at 0. The sub-ablation `C6-shuffle` keeps T = 0 for all three, isolating the order-shuffle source.
- **Vote.** Execute each candidate read-only with a fixed 30 s timeout (no gold-derived timeout, so nothing about the gold query reaches selection). Errors and timeouts don't vote. Group by `set(rows)` (BIRD's EX equality). Pick the largest group; on a tie, the group containing the lowest-numbered candidate. If none executes, return candidate 1. Deviation: the paper breaks ties at random; ours falls back to the C4 answer, so every C6-vs-C4 difference comes from an actual majority.
- **Diagnostics** (provider metadata, never in a prompt): all candidate SQLs, vote group sizes, which candidate won, `vote_unanimous`. Analysis adds **pass@3** (any candidate correct) as the ceiling for a perfect selector, the analogue of the linking oracle.
- **Config** `promptfoo/configs/04_voting.yaml`, ± hints: C4-linked (parent, cached), C6-vote (shuffle + T 0.7), C6-shuffle (shuffle, T 0).
- **Cost.** 2 extra short final calls per question per config (~1–2K prompt tokens each). Estimate: about 1 h on eval, 15 min on dev.
- **Steps.**
  - [x] Implement `voting.py` (`pick`, `vote`) and the candidate loop in `pipeline.py` (`votes`, `vote_temperature`; `shuffle_seed` through `build_messages`). Defaults keep C0–C5 prompts and cache keys byte-identical.
  - [x] Tests (`tests/test_voting.py`, 64 total pass): majority, tie → candidate 0, failures don't vote, row-order-insensitive grouping, candidate 0 = C4's exact call, seeds/temperatures, shuffled schema = same lines reordered.
  - [x] Dev run (sanity only, nothing tuned), 19 min: candidate 0 reproduces C4 exactly (40.0 / 53.3). C6-vote 46.7 / 60.0 (3 fixed, 1 broke each; n.s.); C6-shuffle 40.0 / 53.3. pass@3 66.7 / 63.3. Valid SQL 90 → 100%. Combined pass fully cached, 0 fallbacks, max candidate exec 4.4 s.
  - [x] Eval run: 94 min, 0 errors, combined pass fully cached, 0 linking fallbacks. C6-vote 40.0 / 58.7 vs C4 39.3 / 56.7 (n.s.); C6-shuffle 39.3 / 60.7 (+h: 6 fixed / 0 broke, p = 0.031, not significant after Holm over 4 tests). pass@3 46.7 / 62.7. Valid SQL 94.7 → 99.3% (p = 0.016).
  - [x] Analysis written up in `docs/results.md` §04 and D19.

#### Dev check of C4/C5 (n=30, 2026-11-16; sanity only, nothing here is significant)
- **02 linking:** C3 30.0 → C4 40.0 → oracle 56.7 (no hints); with hints 43.3 → 53.3 → 56.7. Link recall 0.93, ~6 linked columns. C4 costs 6.2 calls, 18.5K prompt tok, ~56 s per question (vs 1 call, 8.6K, ~18 s for C3). The oracle is a single 725-token call. 0 errors.
- **03 few-shot (on top of C4):** no hints: C4 40.0 / train 36.7 / querylog 43.3. With hints: C4 53.3 / train 33.3 / querylog 30.0 (C4+h → querylog+h: 3 fixed, 10 broke, p = 0.09).
- **Harness checked, no bug:** prompts rebuilt from cache; examples are same-DB (querylog) or other-DB (train), placed between schema and question, no gold leakage.
- **Failure pattern is copying:** wrong literal from a near-duplicate example (qid 486: `= 5` instead of 7; top sim 0.99), dropped filters (Fresno, Marvel, "Aaron"), example-shaped extra columns (COUNT, MIN/MAX), and T1/T2 alias mix-ups (1102: `T1.player_name` on Player_Attributes).
- **Likely causes:** (1) the target question is formatted as a ninth example with nothing separating it; (2) BIRD dev hints are noisy (one example's hint says `= 16`, its SQL `= 10`), so with hints on the examples teach "the SQL may ignore the hint". Without hints, query-log examples do fix percentage formulas and joins (moderate 31 → 56).
- **Framing fix (03b, dev only, D17):** a hand-off line after the examples ("Now write the SQL for the question below. The examples only illustrate style…") recovers few-shot: with hints, querylog 30.0 → 56.7 (8 fixed / 0 broke, p = 0.008) and train 33.3 → 60.0 (9 / 1, p = 0.02); without hints, querylog 43.3 → 53.3 and train 36.7 → 43.3. Hiding the examples' own hints is mixed (+6.7 querylog, −10 train; 2–3 flips), so it's dropped. **Frozen:** `fewshot_framing: separated`, example hints shown. The eval config keeps inline query-log as a framing ablation.
- **Determinism fix:** value-index ties depended on `PYTHONHASHSEED` (D17). Re-running 02/03 dev after the fix gave identical EX.
- [ ] Trimming T1–T4.
- [ ] Optional: repeat the headline configs on `qwen3.5:9b` and/or on all 500 questions.

### Phase 5 — Analysis and write-up
- [ ] `analysis/analyze.py` → `results/summary.md`, CI tables, McNemar matrix, waterfall chart of gains, and a Pareto chart.
- [ ] Error analysis: 20 failures categorized (wrong column, wrong literal, join, aggregation, gold-SQL bug).
- [ ] README: motivation, setup, how to reproduce, results vs paper, tradeoffs, limitations, and what I learned about evals.
- [ ] `docs/`: `paper-summary.md`, `setup.md`, `eval-design.md`, `decisions.md` (one entry per tradeoff).

### Phase 0 results (2026-11-16)
- Ollama 0.40.16, promptfoo 0.125.1 (Node 22.23 keg-only), Python 3.12 via uv, 11 evaluator tests passing.
- Data: 500 entries = **498 unique questions** (D3); 11 SQLite DBs open read-only.
- Gold cache built; two slow gold queries (701: 183 s, 518: 37 s) handled by a per-question timeout (D4).
- DuckDB evaluated for execution and rejected for scoring: 27% of gold queries break or change answer (D5). Candidate for profiling only.
- Smoke test (`qwen3.5:9b`, DDL only, no hints, 3 questions): pipeline works. Prefill ~200–280 tok/s cold, decode 21–35 tok/s. **The prefix KV cache works:** the 3rd same-DB call's prefill dropped to 331 ms from ~4–6 s, so grouping tests by DB is confirmed worthwhile. All 0/3 correct, as expected without hints or metadata (e.g. "exclusively virtual" means `Virtual = 'F'`).
- Still open: source for the few-shot pool (full BIRD `dev.json` is not in minidev.zip).

## 6. Compute budget (estimate, to verify in the Phase 0 smoke test)

7B Q4 on an M3 Pro: roughly 300 tok/s prefill and 30 tok/s generation. Single-call configs take about 5–15 s per question,
so 150 questions take 15–40 min. Linking, voting, and correction configs take 3–6× that.
The total for all configs on 150 questions is about **8–12 hours**, which can run overnight in chunks.
Profiling summaries are a one-time job of about 1 hour.

## 7. Risks

- A 7B model may make the metadata gains noisy. Mitigation: paired tests, and the optional 9B rerun.
- BIRD gold SQL has known errors (paper §4.1.1). Mitigation: the error analysis tags them, and we report but do not "fix" them.
- Memory pressure: keep `num_ctx` at 8192 by default and measure the largest prompt. Fall back to linking-only configs if the full fused schema overflows.

## Review

_(filled in after implementation)_
