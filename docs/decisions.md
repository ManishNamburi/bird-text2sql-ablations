# Decision log

Each entry records a choice, the alternatives considered, the evidence, and the tradeoff.
Newest at the bottom.

---

## D1 — Local model: Qwen3.5-9B (main) + Qwen2.5-Coder-7B (check)
- **Context:** MacBook Pro M3 Pro, 18 GB unified memory. About 12 GB is usable by the GPU, and that must also hold the KV cache for 8–16K-token prompts.
- **Options:** qwen2.5-coder 7B (4.7 GB), qwen3.5 9B (6.6 GB Q4), 14B models (~9 GB), nemotron-3-nano 4B, nemotron-3.5-bolt e4b (7.9 GB, multimodal).
- **Choice:** `qwen3.5:9b` with thinking disabled as the main model, and `qwen2.5-coder:7b` reruns the headline configs.
- **Tradeoff:** The 9B model is newer and likely stronger but slower. Running two models lets us ask whether the paper's gains depend on model strength. 14B would squeeze the context budget. Thinking mode is off because it multiplies latency, and the paper's pipeline uses a non-reasoning model (GPT-4o).
- **As actually pulled (corrected 2026-11-17):** the "6.6 GB Q4" above was the pre-pull estimate. Ollama 0.40.16 serves `qwen3.5:9b` as 9.7B parameters, **nvfp4** quantization, on the **MLX** runner (7.6 GB), digest `d63f830f28d5`, pulled 2026-11-16 08:56. All 7,530 cached LLM calls behind experiments 01–05 were made after that pull with that tag, so every result comes from this one build. The runner didn't record this per run until Phase 5; it now writes a provenance footer (Ollama, promptfoo and Node versions, model digest) into each `results/*.md`.

## D2 — Eval set: stratified 150 per config + all unique questions for headline configs
- **Tradeoff:** A 95% CI on one accuracy at n=150 is about ±8 pp. Comparisons use paired McNemar tests on the same questions, which detect smaller differences. The full set costs about 3× more compute per config.

## D3 — Dedupe MiniDev to 498 unique questions
- **Evidence:** `mini_dev_sqlite.json` has 500 entries, but qid 137 and qid 138 each appear twice, identical. Found by the gold-cache completeness test.
- **Choice:** Key everything by `question_id` and evaluate 498 unique questions.
- **Tradeoff:** Our "full set" numbers are over 498, not 500, so they differ trivially from the paper's denominator. Keeping the duplicates would double-weight two questions.

## D4 — Cache gold results; per-question timeout = max(30 s, 2 × gold runtime)
- **Evidence:** Two gold queries are slow on SQLite: qid 701 (`codebase_community`) takes 183 s, and qid 518 (`card_games`) takes 37 s. The other 496 take 9 s combined.
- **Problem:** BIRD's official evaluator uses a fixed 30 s timeout. Here, the gold query itself would time out, so those questions would score wrong for every config, which is silent noise.
- **Choice:** Run all gold queries once (`scripts/cache_gold.py`, ~4 min) and store the rows in a pickle. Predictions get max(30 s, 2× that question's gold time).
- **Tradeoff:** A slight departure from the official harness, documented here. It also halves eval time, because gold never re-runs.

## D5 — Keep SQLite as the execution engine (DuckDB evaluated and rejected for scoring)
- **Question:** Would DuckDB be faster? (User question, 2026-11-16.)
- **Experiment:** All 500 gold queries run on DuckDB 1.x, attached to the same `.sqlite` files through the `sqlite` extension, then compared against SQLite results.

  | | SQLite | DuckDB |
  |---|---|---|
  | Total time, 500 gold queries | 230 s | 5 s |
  | qid 701 / qid 518 | 183 s / 37 s | 0.04 s / 0.06 s |
  | Median per query | 0.9 ms | 2.7 ms |
  | Same result as SQLite | — | **365 / 500 (73%)** |
  | Errors | — | 73 (`IIF` missing, VARCHAR vs INT comparisons, parser and conversion errors) |
  | Different result | — | 62 (float rounding, REAL as float32, division semantics, `inf` vs NULL) |

- **Choice:** Keep SQLite for executing and scoring SQL.
  1. **Correctness:** The benchmark's ground truth *is* SQLite semantics (dynamic typing, `IIF`, `strftime`, integer division). On DuckDB, 27% of the gold queries fail or change answer, so the metric itself would be wrong.
  2. **Comparability:** The paper and the leaderboard both use SQLite EX.
  3. **Speed is not the bottleneck:** After gold caching, a prediction executes in about 1 ms (median). An LLM call takes about 5–15 s. Execution is under 0.1% of runtime.
- **Where DuckDB *does* fit:** Phase 2 profiling (full-column scans for distinct counts, top-k, min/max over the 600 MB football DB) is pure statistics, not SQL semantics. DuckDB's columnar engine should speed it up a lot. We'll measure when building it, and watch for SQLite mixed-type columns (the `sqlite_all_varchar` option).
- **Lesson for evals:** A faster engine that changes the answers changes the metric. Validate the evaluator against ground truth before optimizing it.

## D6 — Three frozen splits: dev (30) / eval (150) / test (468)
- **Choice:** Stratify by (db_id × difficulty) with seed 42 and largest-remainder allocation (`scripts/make_subset.py`, committed as `data/subset_ids.json`).
  - `dev`: the only questions we look at while iterating on prompts.
  - `eval`: every ablation config runs here. Disjoint from `dev`.
  - `test`: all 468 non-dev questions, for the headline configs.
- **Why:** Any question used to tune prompts inflates its own score. Keeping `dev` out of `eval` and `test` makes every reported number held-out.
- **Tradeoff:** The headline set is 468, not the paper's 500. The difficulty mix stays proportional (eval: 43 simple / 74 moderate / 33 challenging).

## D7 — promptfoo harness: one Python provider whose config *is* the ablation
- **Choice:** One custom provider (`promptfoo/providers/pipeline.py`). Its YAML `config:` maps 1:1 onto a frozen `PipelineConfig` dataclass. Unknown keys raise, after stripping promptfoo's own injected keys such as `basePath`, so a typo can't silently run the wrong ablation.
- **Alternative:** promptfoo's built-in `ollama:chat` provider with prompt templates. That's simpler for single-call configs, but it can't express multi-step pipelines (schema linking, voting, correction). It would also give us two code paths to keep consistent.
- **Tradeoff:** Prompts are built in Python (`src/birdeval/prompts.py`) instead of in promptfoo's prompt files, so the promptfoo UI shows the question rather than the full prompt. Mitigation: the provider returns the raw model reply in its metadata, and the prompts live in one small module.
- **Scoring:** A Python assertion computes BIRD EX against cached gold rows looked up by `question_id`. Gold SQL is never a test variable, so it can't leak into a prompt. It emits `namedScores` for `ex` and `valid_sql`.

## D8 — Two-pass runner to keep Ollama's prefix cache warm
- **Evidence:** promptfoo's evaluator iterates `for test: for provider:`, as read from `dist/src/evaluator-*.js`. Ollama keeps one KV-cache slot, so several configs in one eval would alternate prompts and miss the cache on every call. The smoke test showed a cache hit cuts prefill from ~4–6 s to ~0.3 s.
- **Choice:** `scripts/run_ablation.py` warms up each config alone (`--filter-providers`, tests sorted by DB, concurrency 1), filling birdeval's disk cache. It then runs one combined eval where every call is a cache hit, giving promptfoo's side-by-side comparison view.
- **Tradeoff:** Each eval is executed twice, but the second pass costs only SQL execution time. Latency is reported from the original call timings stored in the cache, not promptfoo's `latencyMs`, which shows ~0 on cache hits.

## D9 — Evaluator verified against BIRD's official code
- **Check:** The official `evaluation/evaluation_ex.py` (`calculate_ex`) is `set(predicted_res) == set(ground_truth_res)` on raw `fetchall()` tuples. It has no rounding or normalization, and errors and timeouts score 0. Ours is identical, apart from the per-question timeout in D4.
- **Minor difference:** We decode invalid UTF-8 bytes with replacement characters instead of raising. Both gold and prediction go through the same path, so comparisons stay consistent.

## D10 — Canonical schema rendering for every metadata variant
- **Choice:** Schemas are rendered from SQLite PRAGMAs (columns, primary keys including composite ones, and foreign keys) into one canonical `CREATE TABLE` format. Metadata is attached as an end-of-line `-- comment` per column. A test asserts that C1 minus its comments is byte-identical to C0.
- **Details:**
  - BIRD descriptions that merely repeat the column name are dropped. For example, frpm's `CDSCode` is described as just "CDSCode". Dropping these saves tokens without losing information.
  - BIRD's "commonsense evidence:" label is stripped, but the text after it is kept.
  - SQL keywords used as identifiers are quoted, e.g. financial's table `order`.
- **Tests caught:** Composite primary keys rendered as invalid DDL, and the `order` table being unquoted. Both are fixed, and every rendered schema is now executed in an in-memory SQLite and compared with the real DB.
- **Size:** BIRD value descriptions roughly double some schemas (`california_schools`: 5.5K → 13K chars). That makes them a prime candidate for trimming experiment T3.

## D11 — Profiling: SQLite stats → English profile → LLM short/long summaries
- **Engine:** SQLite (resolves D5's open question). All 798 columns profile in 65 s, so speed is a non-issue. SQLite's `typeof()` also exposes *how values are stored*: numbers stored as TEXT, mixed storage classes. The paper's Q1260 (`RF < 20` on a TEXT column) is exactly this trap, and DuckDB's SQLite scanner would hide it by coercing types.
- **Profile contents:** The paper's §2.1 English format (NULLs, distinct count, min/max, top-10 values), plus:
  - the storage class,
  - value-length range,
  - "looks numeric" and "looks like JSON" flags,
  - dominant format patterns (`9999-99-99` vs `999999`). Patterns are only reported when one format covers ≥30% of the sample and the top-10 list doesn't already show every value.
- **Summarizer inputs:** table name, sibling column names, column name, declared type, and the English profile. **The BIRD SME descriptions are deliberately excluded.**
  - *Tradeoff:* The paper's summarizer also saw "the provided metadata for this field". Excluding it makes C2 a clean test of *fully automatic* metadata vs SME metadata (C1). It may understate profiling's gain relative to the paper's Table 1.
- **Same model** (`qwen3.5:9b`, thinking off) writes the summaries, using JSON-schema-constrained output. The summaries are an artifact generated once. The `qwen2.5-coder:7b` check reuses them, so the model-size comparison isolates SQL generation.
- **Prompt fixes from an 8-column trial** (before any eval questions were involved):
  1. The model claimed an INTEGER column was "stored as text". *Root cause:* the profile quotes every value (`'14872'`) and never stated the storage class. *Fix:* the profile now always states it.
  2. Long summaries were about 100 tokens and padded with generic advice ("preserve leading zeros" on columns with none). *Fix:* "at most 60 words; state only facts supported by the profile; no generic advice". Average length dropped about 45%, and the call time went from 7.5 s to 5.3 s.
- **Ops lesson:** CPU-heavy jobs running beside the LLM batch tripled per-call latency (JSON-constrained decoding uses CPU), from 5 s to ~17 s.

## D12 — Value index: MinHash-LSH on character 3-shingles (paper §3)
- **What's indexed:** Up to 10,000 distinct values per column (paper: N=10000), for non-numeric, non-JSON columns whose values are ≤100 chars. That's 302 columns and 531K values; it builds in 38 s and takes ~245 MB of pickles (gitignored, rebuildable).
- **Lookup:** Candidate keys come from LSH (64 perms, threshold 0.5) and are re-scored by exact shingle Jaccard (≥0.6). The best match per column is returned.
- **Validation:** Reproduces the paper's §3.1 example exactly: `'Fresno County Office of Education'` maps to `frpm.District Name`, `satscores.dname`, and `schools.District`. It also resolves three dev-slice failures (`Coldsnap` → `sets.name`, `banned` → `'Banned'`, `csgillespie` → `users.DisplayName`). Both are locked in as tests.
- **Alternative:** Exact `LIKE` lookups against the live DB, the CHESS-style approach. That's simpler at this scale, but the paper argues it doesn't scale to industrial DBs, and it misses near matches.

## D13 — One global context size (24,576) plus a truncation guard
- **Measured prompt sizes** (tokens, calibrated on 120 real prompts at 3.67 chars/token):

  | DB | C0 DDL | C1 BIRD | C2 profile (long) | C3 fused (long) | C3 fused (short) |
  |---|---|---|---|---|---|
  | european_football_2 | 1,951 | 3,942 | 17,003 | 18,995 | 12,112 |
  | card_games | 840 | 3,417 | 9,880 | 12,456 | 7,977 |
  | california_schools | 707 | 3,696 | 7,692 | 10,681 | 7,244 |
  | toxicology (smallest) | 304 | 551 | 1,215 | 1,462 | 1,000 |

  Profiling metadata multiplies prompt size **5–10×** over DDL. This quantifies the paper's motivation for schema linking.
- **Finding:** Ollama's **MLX runner** (used by `qwen3.5:9b`) ignores `num_ctx`. A 19,696-token prompt is processed in full even with `num_ctx=4096`, and `ollama ps` keeps showing 8192. The llama.cpp runner (likely used by `qwen2.5-coder:7b`) *does* enforce it and would silently truncate the schema.
- **Choice:** `DEFAULT_NUM_CTX = 24576` for every config and model, so configs stay identical. `chat()` raises if `prompt_tokens >= num_ctx`, so truncation can never silently masquerade as a "metadata doesn't help" result.
- **Cost:** A cold 19.7K-token prefill takes 77 s (257 tok/s). The next question on the same DB reuses the prefix and takes 14 s. Grouping tests by DB (D8) is what makes the C2/C3 configs affordable.
- **Memory:** Ollama reports 16 GB for the loaded model, and swap rose from 5.9 to 8.5 GB during the 19.7K test. It runs, but this is the ceiling. 14B models were the right call to skip (D1).

## D14 — Audit the generated metadata before using it
- **Choice:** Grade a seeded random sample of 20 long summaries against their source profiles (`scripts/audit_summaries.py` → `docs/summary_audit.md`).
- **Result:** 60% OK, 20% MINOR, 20% WRONG.
  - 1 of the WRONG cases is a copied-number error: 836 NULLs became 83,600.
  - 3 are wrong *meanings* of cryptic codes: the X/Y formation-coordinate columns were read as "player identifiers", and `UG` was expanded as "undergraduate" instead of "ungraded".
- **Interpretation:** Profiles are strong on formats and literals and weak on semantics. This predicts that C2 should help most where failures are literal or format errors, and that C3 (fused) should beat both C1 and C2. Those are testable hypotheses for the ladder.
- **Why it matters for evals:** Generated metadata is an *input* to every downstream config. If it isn't measured, a bad C2 result can't be told apart from bad metadata or a bad technique.

## D15 — Schema linking implementation (paper §3), and oracle linking
- **Algorithm:** Five schema variants (focused/full × short/long/fused metadata). Each generates draft SQL, and we collect its fields and string literals.
  - If a literal is found by the value index (Jaccard ≥ 0.85) only in fields the draft doesn't use, those fields are added and the model gets **one** revision prompt (`max_retry=1`).
  - The union of fields across variants is the linked schema.
  - The final SQL is generated on that schema with fused metadata.
  - If no draft parses, we fall back to the full schema (recall over precision).
- **Focused schema:** top-15 columns by embedding similarity to the question (plus the hint when hints are on), plus columns whose sampled values match 1–6-word n-grams or quoted strings of the question.
  - The renderer adds the PKs of kept tables and FKs (both ends) between them, so joins stay writable.
  - *Bug caught by a test:* with a 4-word n-gram cap, "Fresno County Office of Education" (5 words) only matched *county* columns. That's exactly the confusion in the paper's example, so the cap was raised to 6.
- **Shared prompt builder** (`promptbuild.py`): the `full_maximal` draft is byte-identical to the C2 prompt, so it's served from the LLM cache, and the two pipelines can't drift. Verified: all 240 dev prompts from experiment 01 still hit the cache after the refactor.
- **Field extraction:** sqlglot's `qualify` resolves aliases and unqualified columns to base tables. On all 498 gold queries, every query yields fields and none are fake columns. A regex cross-check's 61 "misses" were all false alarms: table names, `COUNT()`/`date()`, words inside multi-word column names.
- **Diagnostic `link_recall`:** the share of the gold SQL's fields that survive linking. It's computed from gold SQL *after* generation and only reported in metadata, never shown to the model. It separates "linking dropped a needed column" from "the model wrote bad SQL with the right columns".
- **Oracle (C4-oracle):** fields come from the gold SQL. This is the paper's "perfect schema linking" upper bound and is labelled as oracle everywhere.
- **Tests (LLM stubbed, no Ollama):**
  - The paper's §3.1 walkthrough, end to end: a draft using `frpm.County Name` triggers a revision listing `schools.District`, and the revised fields are linked.
  - No revision happens when the literal is in a used field.
  - Prompt identity with C2.
  - The oracle restricts the schema to gold tables.
- **Cost (expected):** 5 drafts (1 cached) + revisions + 1 final, about 6–8 LLM calls per question vs 1. Measured on dev after the eval run, because LLM calls during the run would thrash Ollama's prefix cache and distort its timings.

## D16 — Few-shot pools: train (paper) *and* a same-DB query log
- **User decision (2026-11-16):** run both. The first choice was train only, then the user changed it to train + query log.
- **C5-train** uses `birdsql/bird23-train-filtered`: 6,601 question/SQL pairs over 69 databases, **none** of them MiniDev DBs. This is the paper's setup.
- **C5-querylog** uses `birdsql/bird_sql_dev_20251106` (the revised BIRD dev): 1,534 questions on the same 11 DBs, minus all 498 MiniDev question IDs, minus 1 entry whose SQL is identical to an eval gold query (dev 863 ≡ eval 875). That leaves **1,035**. Retrieval is restricted to the question's own database, which is what a per-database query log means. This mirrors the paper's §5–6 argument that query logs are the realistic source of few-shot examples.
  - **Kept, on purpose:** 11 near-duplicate siblings (question similarity > 0.85, e.g. "tallest" vs "dumbest superhero"). A real query log contains exactly these. Each test records the IDs of the examples it retrieved, so the analysis can measure whether C5-querylog's gain comes from near-duplicates.
- **Retrieval** (paper §4 / [LPKP24]): the LLM masks names, values, numbers and dates in every question. Masked questions are embedded (nomic) and the top-k=8 retrieved (paper: 8). Eval questions are masked from their text only.
  - *Tradeoff:* LLM masking costs ~1.5 h of GPU time, batched 25 per call with a per-item fallback if the item count is wrong. Heuristic masking would be free but asymmetric: train questions could use their gold SQL literals, eval questions could not.
- **Placement:** examples go in the **final** call only, after the schema and before the question. C5's linking drafts stay byte-identical to C4's (cache hits), and the schema-first prefix caching still works. With no examples the prompt is unchanged byte for byte (verified: 240/240 cache hits).
- **Hints in examples** are shown only when the run itself uses hints, so a no-hints config never sees evidence-style text.
- **Download sizes:** 2.65 MB + 0.79 MB (train) + 0.95 MB (dev), instead of the 8.9 GB `train.zip`. Few-shot needs only question/SQL text, not databases.

## D17 — Few-shot framing iterated on dev; value-index ties made deterministic
- **Why (2026-11-16):** on the 30-question dev slice, C5 *hurt* with hints on (C4+h 53.3 → C5-querylog+h 30.0; 3 fixed, 10 broke). Rebuilding the prompts from the cache showed no harness bug. The model copied from the examples: a literal from a near-duplicate (`= 5` for "7"), dropped filters, example-shaped extra columns, T1/T2 alias mix-ups.
- **Two candidate fixes, each one change away from its parent** (`promptfoo/configs/03b_fewshot_framing.yaml`, dev only):
  - `fewshot_framing: separated` ends the example block with a hand-off line (`prompts.FEWSHOT_HANDOFF`), so the real question isn't read as a ninth example.
  - `fewshot_example_hints: false` hides the examples' own BIRD hints. They are noisy (one says `= 16` while its SQL says `= 10`) and can teach the model that SQL may ignore the hint.
- **Defaults keep the original prompt byte for byte**, so the original C5 stays a valid, cached config and is reported alongside the fix.
- *Tradeoff:* choosing a prompt after looking at results is tuning. This is allowed on dev and only on dev (project rule). The chosen framing is frozen *before* any eval-split run, and the dev numbers are labelled as iteration, not results. With n=30 this pick is noisy; the eval split is the real test.
- **Determinism bug found along the way:** `valueindex.lookup` iterated `lsh.query()` (a set), so among equal-similarity matches the example value and the order of the matched columns depended on `PYTHONHASHSEED`. That text goes into the literal-revision prompt, so one dev prompt changed between processes (found as a cache miss that recurred under every hash seed). Fix: iterate keys in index order. A regression test runs `lookup` under 3 hash seeds and fails on the old code. Experiment 01 is unaffected (no linking). The 02/03 dev runs were redone after the fix.

## D18 — Which promptfoo features we use, and which we skip
A review of promptfoo 0.125.1 against this setup (2026-11-16). Each claim below was checked in the installed code, not just the docs.
- **Adopted:**
  - The provider returns top-level `prompt` (the final call's messages) and `latencyMs` (the original summed latency). The viewer shows them as "Actual Prompt Sent" and real latency, instead of the YAML placeholder `{{question}}` and ~0 ms replay time. Verified in the viewer.
  - `derivedMetrics` `EX_pct` and `valid_sql_pct` (`100 * ex / __count`). On dev they match the pandas numbers exactly.
  - `--tag split=… --tag experiment=…` on every combined eval.
  - `REQUEST_TIMEOUT_MS` = 30 min in the runner's environment. The Python provider's default limit is 300 s *per test*, which is a whole pipeline here. The slowest dev question took 181 s, and voting (C6) triples the calls.
  - **Cache-only combined pass:** the runner sets `BIRDEVAL_CACHE_ONLY=1`, so `llm.chat` raises `CacheMiss` instead of calling Ollama at `-j 4`. The runner fails if any row has a provider error. Without a warm-up (`--no-warmup`), the combined pass runs at `-j 1` with live calls.
- **Skipped, with reasons:**
  - *promptfoo's cache:* its key hashes the provider script but not the modules it imports (`src/birdeval/*`), so a pipeline edit would replay stale answers. Our cache keys on the exact Ollama request instead.
  - *`--resume` / `retry`:* they refuse `--no-write`, which the warm-ups use. A restart is already cheap: finished calls come back from our disk cache.
  - *`--repeat`:* with temperature 0, a fixed seed and our cache, repeats are identical. Run-to-run instability needs different seeds, which is a `PipelineConfig` field.
  - *Native `ollama:chat` provider for the single-call configs:* it reports no prefill/decode timings. It would also bypass our cache and the shared prompt builder, which keeps linking's `full_maximal` draft byte-identical to C2. One code path for all configs matters more than less code for a few.
  - *Python test generators:* frozen, committed YAML fits "freeze the eval set" better.
  - *`extensions` hooks:* the `afterAll` return value isn't saved, so `analysis/analyze.py` stays separate.
  - *OTLP tracing:* per-call timelines for linking would be nice in the viewer, but they need OpenTelemetry packages. Possible for Phase 5.

## D19 — Voting (C6): parent config, diversity, and the vote rule
Paper §4: three candidates, diversified by "changing the LLM randomization seed" and by "randomizing the order of the (schema linking-reduced) schema fields". Each is executed, results become sets, two agreeing candidates win, else one is picked at random. Implementation: `src/birdeval/voting.py`, `PipelineConfig.votes` / `vote_temperature`, config `04_voting.yaml` (2026-11-17).
- **Parent is C4, not C5.** The original ladder stacked voting on few-shot. On eval, few-shot gave no gain (querylog-sep = C4 exactly; train-sep −8 pp with hints), so C6 = C4 + voting. That keeps C6 one change from the best non-oracle config.
- **Candidate 0 is exactly C4's final call** (same messages, seed, T = 0), so it is a cache hit and the parent's answer is always on the ballot. Candidates 1..k−1 shuffle column order within each table (`shuffle_seed = i`) and use seed 42 + i.
- **Temperature 0.7 for candidates 1..k−1, fixed a priori.** At T = 0 decoding is greedy and a seed change does nothing, so the paper's "seed" diversity needs sampling. 0.7 is Qwen's recommended non-thinking setting. Not tuned on dev or eval. The sub-ablation `C6-shuffle` (T = 0) measures how much diversity the order shuffle alone gives.
  - *Tradeoff:* this breaks "temperature 0 everywhere", which the project rule limits to single-candidate runs. Results stay reproducible because the seed is fixed and every reply is cached.
- **Vote rule:** execute read-only with a fixed 30 s timeout. A gold-derived timeout (as the EX scorer uses) would let the gold query's runtime influence selection. Failed candidates don't vote. Group by `frozenset(rows)`, BIRD's EX equality. The largest group wins; ties go to the group with the lowest index; if nothing executes, candidate 0.
  - *Deviation:* the paper breaks ties at random. Ours falls back to the C4 answer, so every C6-vs-C4 difference comes from an actual majority, and runs are deterministic.
- **Diagnostics** (metadata only, never in a prompt): candidate SQLs, group sizes, winner, unanimity, distinct-SQL count. Analysis adds **pass@k**: any candidate correct, scored against gold. It is the ceiling for a perfect selector, the selection analogue of oracle linking.
- **Cost:** k − 1 extra final calls, short because they run on the linked schema. Candidate execution time is added to `latencyMs`.

## D20 — SQL sanity checks (C7): detectors, calibration, correction loop
Paper §4: candidates are checked for "SQL constructions that are likely to indicate an incorrect response". On a hit, "the LLM is asked for a correction with up to three retries". Then the vote. Implementation: `src/birdeval/sqlchecks.py`, `pipeline.correct`, `PipelineConfig.checks` / `check_retries`, config `05_checks.yaml` (2026-11-17).
- **The paper's four checks, as sqlglot detectors.** Aliases and unqualified columns resolve to base tables through the linking qualifier. Each check is scoped to its own SELECT, so a subquery's filter doesn't cover the outer query (a test caught that bug).
  - `null_order`: `ORDER BY f` ascending.
  - `null_min`: `MIN(f)` in the select list.
  - Both fire only when no predicate in that SELECT's WHERE/ON/HAVING already rules out NULL for f (`IS NOT NULL`, or a comparison like `f > x`).
  - `minmax_subquery`: `= / IN (SELECT MAX|MIN(...))`.
  - `concat`: `||` or CONCAT over fields in the output.
- **NULL guard (deviation):** the two NULL checks fire only if f actually holds NULLs in the database. Otherwise a correction can't change the result and only costs a call.
  - Note: SQLite's `MIN()` already ignores NULLs, so `null_min` can change a result only in edge cases. It's kept because the paper names it, and its effect is reported separately.
- **Calibrated on the query-log pool, never on eval:** the detectors were run over the gold SQL of the 1,035 BIRD dev questions outside MiniDev (same 11 DBs). A check firing on more than 10% of gold queries would encode a style BIRD's authors don't share; that threshold was fixed before looking. Firing rates: `null_order` 0.7%, `null_min` 0.2%, `minmax_subquery` 2.6%, `concat` 1.1%, so all four are kept.
- **Correction loop**, per candidate and before the vote:
  - Each retry sends the candidate's own messages, the current SQL as an assistant turn, and a user turn listing every check that fired. T = 0, same seed as the candidate.
  - After a revision, the checks run again, up to 3 retries.
  - A revision that fails to execute is rejected while the current SQL runs, because a correction must not create an error.
  - The loop stops when a revision is rejected or unchanged, since a T = 0 retry would only repeat it.
  - The original SQL, the checks that fired, the retries and the final SQL go to metadata.
- **Configs**, both one change from their parent: C7 = C6-vote + checks (C6-vote was the pre-registered C6; picking C6-shuffle after its eval result would be selection on eval), and C4-checked = C4 + checks, which isolates the checks from voting.
- *Tradeoff:* checks only see what they're written for. On this model they may fire rarely, in which case C7 ≈ C6 by construction. The firing rate is reported first so that "no effect" can be told apart from "rarely triggered".
