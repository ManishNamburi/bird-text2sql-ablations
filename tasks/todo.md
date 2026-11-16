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
- [ ] **C4 C3 + schema linking** _(implemented + unit-tested 2026-11-16, D15; config `02_linking.yaml`; dev verification pending)_ — — simplified paper §3 algorithm: generate SQL under 3 schema variants (focused/minimal, full/minimal, focused/maximal), collect fields, and fix literals via the LSH value index with ≤1 retry.
- [ ] **C4-oracle Perfect linking** _(implemented, D15)_ — — fields taken from the gold SQL. This is an upper bound, labelled as oracle.

Paper §4 extras (not ablated in the paper):
- [ ] **C5 C4 + few-shot** _(implemented 2026-11-16, D16)_: two pools: `train` (8 examples from 69 other DBs, the paper's setup) and `querylog` (8 examples from same-DB BIRD dev minus MiniDev). Config `03_fewshot.yaml`.
- [ ] **C6 C5 + 3 candidates + majority vote** — vary seed and schema field order; parse with sqlglot; vote on execution results.
- [ ] **C7 C6 + SQL sanity checks and correction** — NULL ordering for ASC/MIN, subquery-vs-ORDER BY, string concatenation, with ≤2 retries.

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

### Phase 4 — Runs
- [ ] Metadata ladder C0–C3 (± hints).
- [ ] Linking C4 and C4-oracle.
- [ ] C5–C7.
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
