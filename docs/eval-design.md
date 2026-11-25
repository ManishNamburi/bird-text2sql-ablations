# Eval design

How the measurements in this project are made, and why. Decision numbers (Dn) refer to [decisions.md](decisions.md).

## Question → number

Each eval question runs through the same flow:
1. The **promptfoo provider** (`promptfoo/providers/pipeline.py`) turns the question and the config's flags into a `PipelineConfig` and runs the pipeline (`src/birdeval/pipeline.py`). That means 1 to 17 LLM calls through Ollama (the maximum, on one C7 question).
2. The provider returns the SQL, the final prompt, token counts and timings, plus diagnostics (linking recall, vote groups, checks fired) in `metadata`.
3. The **assertion** (`promptfoo/asserts/ex_match.py`) executes the SQL read-only and compares the result rows with the cached gold rows using BIRD's EX rule. It emits the named scores `ex` and `valid_sql`.
4. promptfoo writes one JSON per experiment. `analysis/` turns those into paired tests, the summary and figures.

promptfoo's own prompt template is a placeholder (`{{question}}`). Multi-step configs need many prompts per question, so the pipeline builds them itself from the test vars. A config's YAML `config:` block maps one-to-one onto `PipelineConfig` fields, and an unknown key fails loudly (D7).

## Data and splits (D2, D6)

- **BIRD MiniDev, SQLite:** 500 entries, which are 498 unique questions over 11 databases (two ids are duplicated, D3).
- **Splits:** built once by `scripts/make_subset.py` with seed 42, stratified by database × difficulty, and committed as `data/subset_ids.json`:
  - **dev**, 30 questions: the only split prompts were ever iterated on;
  - **eval**, 150 questions: frozen, and used for every reported number;
  - **test**, all 468 non-dev questions: reserved for headline runs (the T1 check in 06, the replication in 09).
- **Confirmatory questions on test (D24).** Test contains the 150 eval questions. Where a hypothesis was found on eval, the verdict uses the 318 test questions outside eval, and all 468 are reported beside them. 09's hint × model lead shows why: −5.8 pp on the eval questions, +0.6 on the fresh ones, on the same machine.
- **The eval split stays frozen.** Twice, a dev "winner" vanished on eval (few-shot framing, voting). That's the reason the split is never tuned on.

## Metric (D9)

- **Execution accuracy (EX), exactly as BIRD's `calculate_ex`:** `set(pred_rows) == set(gold_rows)`. Row order and duplicates are ignored; column order counts.
- **Validated before any model run:** gold vs gold scores 100%, known-wrong SQL scores 0%, and the code was compared line by line with the official evaluator.
- **Gold rows are cached** (`scripts/cache_gold.py`), because two gold queries take 37 s and 184 s. A prediction gets a timeout of max(30 s, 2 × the gold runtime) (D4).
- **DuckDB was tested as an executor and rejected for scoring:** 27% of gold queries break or change their answer under it (D5).
- **`valid_sql`** records whether the prediction executes at all.

## Statistics

- **Accuracy CIs:** Wilson 95% intervals. They're well-behaved at n = 150 and near 0 or 1.
- **Comparisons are paired,** because every config answers the same questions:
  - an **exact McNemar test** on the discordant questions (fixed vs broke);
  - a **paired bootstrap CI** on the difference (10,000 resamples of questions).

  Pairing detects differences of roughly 5 pp, where two independent CIs (about ±8 pp each) couldn't.
- **Multiple comparisons:** when several tests are read together (the pairwise matrix in `results/summary.md`, or the four C4 → C6/C7 tests), p-values are Holm-adjusted. A lone raw p < 0.05 among several tests is reported as a lead, not a finding.
- **Interactions** (a step's gain on one model minus the other, or judge minus EX) have no McNemar test. They get a per-question contrast with a paired bootstrap CI and a two-sided bootstrap p (09, D24).
- **Pre-registration:** the test-split runs (06's T1 check, 09) fix the hypotheses, the family, the reading rule and the expected CI half-widths in `tasks/todo.md` before any model call. "Unknown" is a verdict, distinct from "no effect".

## One change at a time

- Every config is one `PipelineConfig`. Each config in a ladder differs from its parent by one field, and defaults keep earlier prompts byte-identical. That's checked by cache hits: a parent re-run inside a later experiment must produce no new LLM calls.
- `analysis/export_csv.py` re-checks this across experiments. A config appearing in several experiment files must give identical SQL, scores and tokens on every question, or the export fails.

## Determinism and caching (D8, D17)

- **Decoding:** temperature 0, seed 42, thinking off. Voting candidates 1–2 sample at T = 0.7 with fixed seeds 43/44 (D19).
- **Disk cache** (`src/birdeval/llm.py`): every Ollama call is stored under the sha256 of its exact request payload.
  - Reruns are free and bit-identical.
  - Each entry stores the original call's timings, so latency always describes a real call (promptfoo's own latency is ~0 ms on a replay).
- **Two-pass runner** (`scripts/run_ablation.py`):
  1. A warm-up per config at concurrency 1, so timings aren't distorted by parallel requests.
  2. A combined pass at concurrency 4 with `BIRDEVAL_CACHE_ONLY=1`. A cache miss there raises an error instead of calling the model, and the runner fails on any provider error. `--replay` reruns only this pass, and `--jobs` sets its concurrency.
  - *Limit (D24):* schema linking's query embeddings aren't disk-cached, so the combined pass recomputes them. In 09 the GPU fell back to the CPU, whose slightly different embeddings changed 30 prompts. Those rows failed as cache misses rather than being silently re-answered, and they were replayed after a reboot.
- **The seed doesn't make qwen3.5 deterministic; the cache does (D23).** On Ollama's MLX runner, qwen3.5:9b didn't reproduce 43 of 300 C1 replies cached two days earlier, at temperature 0 and seed 42, with the same digest and Ollama version. 17 of those also differed from a fresh call. The coder (llama.cpp runner) reproduced 300 of 300. Every reported number is therefore a replay of one recorded run: reruns are identical, but a fresh rerun of qwen3.5 would move by a point or two.
- **On the 5070 (Ollama 0.40.17, llama.cpp), replies depend on server state, for both models (D24).** Repeated in the same order after a model reload, 10 of 10 calls matched on both models. But one request aborted when sent alone and got a normal reply inside the pipeline, and the native provider matched the custom provider's cached replies on 1,628 of 1,872 (coder 853 of 936). 09's numbers are reproducible through the disk cache, not from the request.
- **Ollama's repeat-limit abort** (HTTP 500 "token repeat limit reached") is cached as a reply that fails to execute, so a cache-only pass can replay it. Every other HTTP error still raises (D24).
- **Version pin:** a run can set `BIRDEVAL_OLLAMA_VERSION`. The runner then stops before each promptfoo pass if Ollama's version has changed. Ollama's updater replaced the server a minute into 09's first start.
- **Nondeterminism shows up as cache misses.** A cache miss on an unchanged pipeline led to a real bug: value-index ties depended on `PYTHONHASHSEED`, so prompts differed between processes. It was fixed with a regression test that runs the lookup under three hash seeds.

## Leakage rules

- **Gold SQL never enters a prompt.** The exception is the `C4-oracle` config, which is labelled as an upper bound everywhere.
- **Diagnostics are computed but never shown to the model.** Linking recall against the gold columns, and pass@k scored against gold, are diagnostics only.
- **Few-shot pools never contain eval questions** (tested). The "query log" pool is BIRD dev minus MiniDev (D16).
- **Profiling summaries are written without seeing BIRD's descriptions** (D11). So "profiling ≈ expert metadata" isn't circular.
- **SQL-check detectors were calibrated on query-log gold SQL,** with the threshold fixed in advance, never on eval (D20). Voting uses a fixed 30 s execution timeout, not one derived from gold.

## Cost accounting

Every row records:
- prompt and completion tokens summed over all LLM calls;
- the number of calls;
- the original wall-clock latency, including candidate execution for voting configs.

Timings come from one machine (MacBook Pro M3 Pro, 18 GB, Ollama MLX runner), where prefill dominates at about 500 tok/s. Configs are compared on this hardware only. Absolute seconds won't transfer elsewhere. Experiment 09's timings come from an RTX 5070 (llama.cpp runner) and are compared only with each other. On the same 150 questions it is 3.5–7.4× faster per question than the Mac, more for C7 than for C1.

## Provenance

- **Model:** `qwen3.5:9b`, digest `d63f830f28d5` (9.7B, nvfp4, MLX).
- **Versions:** Ollama 0.40.16, promptfoo 0.125.1, Node 22.23, Python 3.12.
- **One build behind every result:** all 10,234 cached qwen3.5 calls were made after that model was pulled, under that tag.
- **The model rerun (D22):** `qwen2.5-coder:7b`, digest `dae161e27b0e` (7.6B, Q4_K_M, llama.cpp runner, `num_ctx` enforced), 4,209 cached calls.
- **Experiment 08 (D23):** 600 generations and 600 judge verdicts on eval, through promptfoo's native provider and its own cache, with the same two digests.
- **Experiment 09 (D24):** a second machine, Windows 11, RTX 5070 12 GB, Ollama 0.40.17, promptfoo 0.125.1, Node 22.23, Python 3.12.
  - **Models:** `qwen3.5:9b` digest `56671c2ab938` (9.0B, Q4_K_M, llama.cpp; Modelfile `temperature 1`, `top_k 20`, `top_p 0.95`, `presence_penalty 1.5`, of which the requests override only temperature). The same coder digest, and `nomic-embed-text` `0a109f422b47`.
  - **Calls:** 22,000 new cached calls, plus 1,872 native generations and 1,872 judge verdicts.
  - **Where it's recorded:** `results/09_replication__test.md` and `results/09_judge__test.md`.
- **Going forward,** the runner writes these facts into every `results/*.md` (D1 correction).

## promptfoo features used (D18, D23)

Experiments 01–07, through the custom provider:
- Custom Python provider and assertion.
- Named scores with `derivedMetrics` (EX %, valid-SQL %).
- `--tag split=… experiment=…` on every run.
- A provider-returned `prompt` and `latencyMs`, so the web viewer shows the real prompt and true latency.
- `REQUEST_TIMEOUT_MS` raised to 30 min, because one test is a whole pipeline.

Experiment 08 (D23), on the single-call C1 config, each one measured against execution:
- the native `ollama:chat` provider, in a prompts × providers matrix (2 prompts × 2 models);
- Python prompt functions that call the pipeline's own `build_messages`;
- `options.transform` (SQL extraction) and `transformVars` (the judge's schema var);
- promptfoo's response cache, so generation runs one model at a time and the full pass replays it;
- `is-sql` in both dialects, a `javascript` assertion, and a local `llm-rubric` judge;
- `--filter-providers` and `--grader echo` for the generation passes;
- `PROMPTFOO_PASS_RATE_THRESHOLD` as a regression gate (`make gate`);
- `promptfoo validate` on every config in CI.

Experiment 09 reuses both setups unchanged on the test split. promptfoo 0.125 defers model-graded assertions to the end of the full pass, grouped by grader, so its first ~65 min replay the generations with the judge idle.

Still skipped, with reasons in D18: `--resume`, `--repeat`, test generators, and promptfoo's cache or native provider for the multi-call configs.
