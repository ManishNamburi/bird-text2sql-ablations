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

## Corrections from the user
_(none yet)_
