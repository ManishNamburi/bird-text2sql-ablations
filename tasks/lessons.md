# Lessons

Rules learned while working on this project. Review at session start.

## Environment
- Check tool version constraints before planning around them: the latest promptfoo requires Node ≥ 22.22, but this machine has Node 20.20. Ollama 0.5.7 predates the Qwen3/3.5 model families.

## Data and evaluator
- Validate the evaluator before any model run: gold vs gold must score 100%. This caught two slow gold queries (timeouts) and two duplicate question_ids in MiniDev.
- Never swap the execution engine for speed without diffing results against ground truth: DuckDB changed or broke 27% of gold answers.
- Key everything by `question_id` and assert uniqueness.

## Local LLM ops
- Cache misses on a supposedly unchanged pipeline are a determinism alarm. Re-run under two `PYTHONHASHSEED`s: if the miss moves with the seed, something iterates a set into a prompt. Sort before rendering.
- Don't run CPU-heavy jobs beside an LLM batch: JSON-constrained decoding tripled from 5 to 17 s/call while indexes were building.
- Ollama's MLX runner ignores `num_ctx`, while llama.cpp enforces it (silent truncation). Set one large `num_ctx` everywhere and assert `prompt_tokens < num_ctx`.
- Generated artifacts (LLM summaries) feed every later config. Audit a seeded sample before running ablations on them.
- When a summarizer hallucinates, fix the input before the prompt: the "stored as text" error came from the profile not stating the storage class.

## Reporting
- Before blaming the evaluator (ties, row order), execute both queries. A "logically identical" pair on qid 1102 was actually an alias bug in one of them.
- When a technique *hurts*, rebuild the exact prompt from the cache and read it before theorizing. That separates harness bugs from model behavior in minutes.
- Recompute every number quoted in prose from the data before publishing. Two ratios in the first results draft were rounded wrong (3.68–4.25× written as "3.7–4.2×").
- Quote paper numbers from the PDF text, never from memory. A linking figure in the 02 write-up was wrong ("63.2 → 66.2"; Table 2 says 61.2 → 63.2 → 69.0).
- A choice made on the 30-question dev slice is a hypothesis, not a result. Separated framing looked like +13 pp over C4 on dev and was +0 on eval. Only the larger inline-vs-separated effect replicated.
- Report paired tests, not overlapping CIs. With n=150, the CIs of C1 and C3 overlap heavily, but the paired view also shows 37 discordant questions, which is the real story.

## promptfoo
- promptfoo injects `basePath` into a Python provider's `config`. Strip its known keys, then validate strictly.
- promptfoo iterates `for test: for provider:`. Never run several local-LLM configs interleaved; warm up one config at a time.
- promptfoo's `latencyMs` is ~0 on cache hits. Report timings stored with the original call.
- Never trust result order in promptfoo's JSON export. Order by the config's label list.
- **Several tests at once need a correction before one of them is called significant.** In experiment 04, one of four C4 → C6 comparisons hit p = 0.031 (Holm-adjusted 0.125). Report the raw p, the number of tests, and the adjusted p together, and call a lone hit a lead, not a result. (2026-11-17)
- **Compute every number in a write-up; never type one from a rough recollection of an earlier table.** In the error analysis I wrote 13/66 vs 49/84 where the data says 14/67 vs 48/83. Generate the sentence's numbers with a query, then paste. (2026-11-17)
- **Size a non-inferiority margin against the CI you will get, before pre-registering it.** I set "safe = CI lower bound > −5 pp" for T1–T4, but at n = 150 the paired CIs are ±4.7 to ±6.7 pp, so a trim with a true Δ of 0 fails about half the time or more. Compute the expected half-width from a previous paired comparison first, then pick the margin or the n. (2026-11-17)
- **An inconclusive result with a ~0 point estimate is not a lean toward "safe".** T1 was +0.7 pp on eval (CI ±6.7) and I called it the next candidate; on 468 questions it was −4.5 pp (Holm p = 0.025). Write "unknown, run more questions", and keep recommendations off inconclusive results. (2026-11-17)
- **Claims of the form "X still contains some Y" need a count.** I wrote that short summaries quote values "now and then"; the count was 403 of 798. (2026-11-17)
- **Start a multi-hour run under `caffeinate -i -s -w <pid>`.** The Mac idle-slept overnight during the coder eval run and only progressed during maintenance wakes: about 18 minutes of LLM time in 3 hours. Results and recorded timings were unaffected (`time.perf_counter` stops during sleep on macOS, and every call's time matched Ollama's own prompt+decode time); only wall-clock was lost. (2026-11-18)
- **A closed lid on battery overrides `caffeinate`.** The 08 dev run spent 9 h in clamshell sleep even under `caffeinate -i -s`. For long runs: AC power and the lid open, then check `pmset -g log` for sleep events before trusting wall-clock numbers. promptfoo's latencies are wall clock, so they include sleep. (2026-11-18)
- **Check that the runtime is deterministic before treating a rerun as a replication.** Temperature 0 and a fixed seed did not make qwen3.5:9b on Ollama's MLX runner reproduce its replies (43 of 300 differed after two days, 17 even from a fresh call); llama.cpp did. Compare a handful of fresh calls with cached ones before any reproduction claim, and say which runner. (2026-11-19)
- **When a run's estimate is off by 3×, find which stage overran before waiting.** The 08 judge, told to be strict, deliberated at ~20 s a verdict and 5% of verdicts ran into the token cap. Time 10 calls of every stage on dev, not just generation. (2026-11-19)
- **A rendered template shows you what the grader really sees; read it against the spec.** The rubric rendered `{{evidence}}` in every cell, although the spec said "when the prompt has one". The dev check covered gold leakage, not this. (2026-11-19)
- **Confirm a lead on questions it wasn't chosen on.** H3 (hints help the coder less) was −7.9 pp on eval. On the 318 fresh test questions it was +0.6, while the same machine still gave −5.8 on the 150 eval questions. Test splits that contain eval get a confirmatory "outside eval" set fixed before the run. (2026-11-24)
- **A cache-only pass must cache every input its prompts depend on.** 09's combined pass recomputed the linking embeddings live. After the GPU fell back to the CPU, the CPU embeddings flipped near-tied columns and gave 30 cache misses. The misses failed loudly, which is the point of `BIRDEVAL_CACHE_ONLY`. Next experiment: disk-cache query embeddings too. (2026-11-23)
- **Pin the runtime version for a multi-hour run, and turn off auto-update.** Ollama's updater replaced the server a minute into 09's first start, and 33 calls failed. The runner now stops if `/api/version` changes (`BIRDEVAL_OLLAMA_VERSION`). (2026-11-23)
- **On Windows, read and write text as UTF-8 explicitly, and use 127.0.0.1, not localhost.** The cp1252 default broke a few-shot test, and localhost's IPv6-first lookup added ~2 s per Ollama call. (2026-11-22)
- **A run that looks hung may just be deferred work: read the tool's own log before killing it.** promptfoo 0.125 replays all generations before running any grader call ("Grouping model-graded assertions by provider"), so the GPU sat idle for an hour with nothing written to the eval DB. (2026-11-24)
- **When the machine itself fails, check the system logs before rerunning.** The 09 desktop's GPU dropped off the bus (`nvlddmkm` 153), then its CPU logged a fatal machine check (WHEA 18). Both happened under the heaviest CPU load. Check that the data parses, then rerun gently (`--jobs 1`) or fix the hardware. Don't just retry. (2026-11-23)

## Corrections from the user
_(none yet)_
