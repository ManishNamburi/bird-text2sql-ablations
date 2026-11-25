# Automatic metadata for text-to-SQL, ablated on a local 9B model

AT&T's paper [*Automatic Metadata Extraction for Text-to-SQL*](https://arxiv.org/abs/2505.19988) (Shkapenyuk, Srivastava, Johnson, Ghane, 2025) reached #1 on the BIRD leaderboard with GPT-4o. Its pipeline:
- describes every column automatically, from database profiling;
- narrows the schema with a schema-linking step that writes SQL to find the relevant columns;
- adds few-shot examples, several candidate queries, SQL sanity checks and a vote.

The paper reports the profiling and linking steps together. It doesn't isolate the few-shot examples, the voting or the checks.

This project rebuilds that pipeline and runs it on **`qwen3.5:9b` locally (MacBook Pro M3 Pro, 18 GB)**. It uses [promptfoo](https://www.promptfoo.dev/) to measure, one change at a time:
- what each step adds;
- what it costs in tokens and seconds;
- whether the gain is real or noise.

The headline configs are then repeated on **`qwen2.5-coder:7b`** to see whether the gains depend on the model. Another experiment uses promptfoo's own features (native provider, built-in assertions, an LLM judge, a pass-rate gate) and measures each one against execution. The last one re-runs the headline configs on both models on **all 468 test questions, on a second machine** (Windows, RTX 5070), to test the leads left open on eval, with the hypotheses pre-registered.

Every number is execution accuracy on 150 BIRD MiniDev questions, with 95% CIs and paired tests, except where a section says it uses the 468-question test split.

![Each step of the pipeline](docs/figures/ladder.png)

## Results

| Step | What changes | EX, no hints | EX, with hints | Prompt tokens/q | s/q | Paper (GPT-4o), no hints / hints |
|---|---|---|---|---|---|---|
| C0 | DDL only | 24.0 (18–31) | 50.7 (43–59) | 824 | 2.9 | 49.8 / — |
| C1 | + BIRD column descriptions | 32.7 (26–41) | 51.3 (43–59) | 1,910 | 3.1 | 59.6 / 72.0 |
| C3 | + LLM profiling summaries | 34.7 (28–43) | 53.3 (45–61) | 8,112 | 5.4 | 63.2 / 73.0 |
| C4 | + schema linking | 39.3 (32–47) | 56.7 (49–64) | 18,387 | 40.8 | 63.2 / 73.0 |
| C6 | + 3 candidates, majority vote | 40.0 (33–48) | 58.7 (51–66) | 20,252 | 49.7 | not isolated |
| C7 | + SQL sanity checks | **41.3** (34–49) | **59.3** (51–67) | 20,523 | 50.9 | not isolated |
| *Oracle* | *gold SQL's columns only (upper bound)* | *53.3* (45–61) | *61.3* (53–69) | *748* | *4.0* | *69.0 / 77.4* |

*EX = BIRD execution accuracy (%), with Wilson 95% CIs. "With hints" adds BIRD's per-question evidence, which real users don't write, so the no-hints column is the realistic one. Deltas, paired CIs, a Holm-adjusted McNemar matrix, the trimming table, all 34 qwen3.5 configs, the qwen2.5-coder rerun, the promptfoo-native experiment and the test-split replication are in [results/summary.md](results/summary.md). The full write-up of each experiment is in [docs/results.md](docs/results.md).*

### What I found

1. **The paper's shape reproduces on a 9B model; its level doesn't.** In both, metadata helps, profiling matches or beats the expert descriptions, linking adds a little, and perfect linking adds a lot. The 9B model sits 16–29 points below GPT-4o at every step.
2. **Automatic metadata can stand in for expert metadata.** LLM profiling summaries, written without seeing BIRD's descriptions, score the same as those descriptions (34.0 vs 32.7, n.s.). That's the paper's central claim, and it holds here.
3. **Without hints, the full pipeline beats bare DDL by 17 points (p = 0.001 after Holm).** But no single step is significant after the Holm correction; C0 → C1 comes closest (+8.7 pp, raw p = 0.015). C7 vs C1 is +8.7 pp (Holm-adjusted p = 0.35). **On the 468-question test split (experiment 09) that lead holds:** C7 beats C1 by +14.8 pp without hints and +11.0 with them on the 318 questions outside eval (both Holm p < 0.001). The full pipeline is better than a single call with good descriptions, at **11–16× the time**.
4. **The real lever is linking recall.** Feeding the model only the gold SQL's columns gives 53.3% at 748 tokens, beating every deployable config at 4% of C7's tokens. C4's linker drops a needed column on 67 of 150 questions. C7 scores 21% on those, against 58% when every needed column survives.
5. **Few-shot, voting and SQL checks add almost nothing for this model.**
   - **Few-shot:** zero net gain, and −17 pp when the examples are framed so that the model copies them.
   - **Voting:** +0.7 pp, though it removes nearly all invalid SQL.
   - **SQL checks:** +1.3 pp, all from one check (string concatenation).
6. **Hints dominate everything.** They add +17 to +27 pp at every step of the ladder, more than all the techniques combined. The oracle gains only +8, because much of what a hint supplies is which columns to use. The [error analysis](docs/error_analysis.md) shows why: about 8 of 20 sampled failures are questions that only mean what the gold SQL says once you've read the hint, or where the gold SQL itself is wrong.
7. **What profiling contributes is its example values, and trimming them costs accuracy.** I trimmed one section at a time from C3 (T1–T4, [results §06](docs/results.md#experiment-06--prompt-trimming-t1t4-research-question-4)).
   - **Masking the quoted values in the profile summaries** costs −10.7 pp with hints (Holm p = 0.012). The model then guesses literal formats (`'north Bohemia'` for `'North Bohemia'`).
   - **Short summaries instead of long ones** save 44% of the prompt and looked free on eval (+0.7 / −2.0). On the 468-question test split they cost −4.5 pp without hints (Holm p = 0.025) and −1.3 with hints. About half the short summaries drop the values that long ones quote, so it's the same mechanism.
8. **A 7B code model gives the same picture** ([results §07](docs/results.md#experiment-07--the-same-pipeline-on-qwen25-coder7b-d1-d22)). On `qwen2.5-coder:7b`, no config differs significantly from qwen3.5:9b (14 tests, all Holm p ≥ 0.57).
   - **The ladder's shape replicates:** descriptions add +8.7 pp without hints (raw p = 0.015), perfect linking adds +12.7 pp over C4 (p < 0.001), and voting and checks add ~0. Linking recall is again the lever.
   - **Hints seemed to help the coder less, but that didn't replicate.** On eval it is ahead by up to +4.7 pp without hints and behind by up to −8.7 pp with them; pooled, hints gained it 7.9 pp less (95% CI −14.1 to −2.0), a post-hoc lead. Pre-registered on the 318 fresh test questions (09), the difference is +0.6 pp (−3.4 to +4.5). The same machine gives −5.8 on the 150 eval questions, so the lead was a property of those questions.
9. **promptfoo's built-in checks are guards, and its LLM judge is a screen, not a metric** ([results §08](docs/results.md#experiment-08--promptfoos-own-features-measured-against-execution-d23)). C1 ± hints × both models, run on promptfoo's native `ollama:chat` provider and scored next to EX:
   - **The native provider reproduces the custom one exactly where the runtime is deterministic:** 300 of 300 coder replies were identical.
   - **qwen3.5:9b at temperature 0 and seed 42 is not deterministic on Ollama's MLX runner:** 43 of 300 replies differed from the ones cached two days earlier, and 17 differed even from a fresh call. This project's numbers are reproducible because every call is cached, not because of the seed.
   - **`is-sql` defaults to MySQL** and rejected 6.4% of SQLite queries that execute, mostly BIRD's own `CAST(… AS REAL)` idiom. With `databaseType: Sqlite` it rejects none, and it also accepts 91% of the queries that fail to execute.
   - **A reference-free `llm-rubric` judge (qwen3.5, never shown gold) agrees with EX at κ = 0.43.** It also overstated the coder's hint gain about twofold: +18.0 pp against +9.3 by EX (difference +8.7, CI +0.7 to +17.3). 5.5% of its verdicts were unreadable, mostly because it kept looking for the mistake the strict rubric told it to expect. No self-preference was detected. On the 318 fresh test questions (09) the overstatement is +6.6 pp (+0.6 to +12.6): the same direction, but Holm p = 0.106 over the six pre-registered tests, so it isn't established.
10. **On the 468-question test split, on a second machine, two of the four eval leads hold** ([results §09](docs/results.md#experiment-09--the-headline-configs-on-the-468-question-test-split-on-a-second-machine-d24)). The setup: Windows, RTX 5070, Ollama on llama.cpp, a different qwen3.5 build, and hypotheses pre-registered with the 318 questions outside eval as the confirmatory set.
    - **Supported:** the full pipeline beats C1 (+14.8 / +11.0 pp), and schema linking helps with hints (+6.0 pp, Holm p = 0.017).
    - **Unknown:** linking without hints (+1.9), the coder's smaller hint gain (+0.6), and the judge's overstatement (+6.6).
    - **Descriptive, 468 questions:** profiling now adds +6.8 pp over C1 without hints on qwen3.5 (+4.5 on the coder). On eval it was +2.0, not significant.
    - **Same 150 questions on both machines:** the coder's EX stays within ±2.0 pp of the Mac's, and the new qwen3.5 build is 0.7–4.7 pp lower in 13 of 14 cells, untested.
    - **Determinism:** on this runner even the coder's native and custom replies differ on 83 of 936, so these numbers are reproducible through the disk cache, not from the request.

### Cost against accuracy

![Cost vs accuracy, Pareto frontier](docs/figures/pareto.png)

Without hints, the cheap end of the frontier is C0 → C1 → T1 → T4 (3–6 s per question). T1 and T4 are C3 with one section trimmed, and on eval they sit above C3 by differences well inside the noise. T1's place there doesn't survive the test split, where it is 4.5 pp below C3. Linking is the step change in cost: 7.6× C3's time, for +4.7 pp (p = 0.21). **For a deployment on this model I'd pick C1 when cost matters most:** BIRD descriptions on the full schema, 1,910 tokens, 3.1 s, 32.7%. The test split (09) settles what the full pipeline buys over it: +12.0 pp without hints on all 468 questions, for 11× the time per question on the RTX 5070 (16× on the Mac). Rather than more calls, I'd spend effort on linking recall. Shortening the profile summaries (T1) looked like a cheap middle option on eval, but it costs 4.5 pp on the larger test split, so if profiles are used they stay long.

### promptfoo's own features, checked against execution (experiment 08)

C1 (BIRD descriptions, one call) as a promptfoo prompts × providers matrix on the native `ollama:chat` provider: 2 prompts × 2 models × 150 eval questions = 600 outputs. Every built-in check is scored against EX and against whether the SQL executes.

| Cell | EX | Executes | LLM judge passes | Judge − EX |
|---|---|---|---|---|
| C1 · qwen3.5:9b | 30.7 | 93.3 | 30.0 | −0.7 |
| C1 + hints · qwen3.5:9b | 50.0 | 92.0 | 54.7 | +4.7 |
| C1 · qwen2.5-coder:7b | 37.3 | 92.0 | 37.3 | 0.0 |
| C1 + hints · qwen2.5-coder:7b | 46.7 | 86.0 | 55.3 | +8.7 |

*% of 150 questions per cell. The judge is `llm-rubric` on local qwen3.5:9b. It sees the question, the hint, the schema and the SQL, never gold.*

| Feature | Measured against execution | Verdict |
|---|---|---|
| Native `ollama:chat` provider, Python prompt functions | Same SQL as the custom provider: coder 300/300; qwen3.5 257/300, a property of its MLX runner, not of the provider | A drop-in for single-call configs |
| promptfoo's response cache | Generation runs one model at a time; the full pass replays it 100% from cache, so only the judge calls Ollama | What made 2 models + a judge fit in 18 GB |
| `is-sql`, default dialect (MySQL) | Rejects 35 of 545 queries that execute (6.4%); 32 of them use `CAST(… AS REAL)` | Always set `databaseType` |
| `is-sql`, `databaseType: Sqlite` | 0 false rejects, but passes 50 of the 55 queries that fail to execute and 98.6% of wrong answers | A syntax guard, not a quality signal |
| `javascript`: one SELECT/WITH statement | Passed 600/600 | Free insurance; never fired |
| `llm-rubric` judge (reference-free) | κ = 0.43 (0.33–0.53); passes 70.0% of correct answers, fails 73.7% of wrong ones; 33 unreadable verdicts | A screen, not a metric: it doubled the coder's hint gain (+18.0 pp vs +9.3 by EX; difference +8.7, CI +0.7 to +17.3) |
| `PROMPTFOO_PASS_RATE_THRESHOLD` | `make gate`: exits 0 at 20%, non-zero at 30% (C1 on the coder, dev baseline 26.7%) | A working regression gate, on the deterministic runner |

The judge cost more than what it graded: about 2,300 prompt and 420 completion tokens per verdict, against about 1,900 and 62 per generated query, and 3.3 h of judging against 41 min of generation. No self-preference was detected (−2.3 pp, CI −9.0 to +4.7). Full analysis in [results §08](docs/results.md#experiment-08--promptfoos-own-features-measured-against-execution-d23); tradeoffs in D23.

## How the evaluation is built

The full design is in [docs/eval-design.md](docs/eval-design.md), and every tradeoff is logged in [docs/decisions.md](docs/decisions.md).

- **Data.** BIRD MiniDev (SQLite), 498 unique questions over 11 databases, split once with seed 42, stratified by database and difficulty. The splits are 30 questions for development and 150 frozen for evaluation. The test split is all 468 non-dev questions (a superset of eval), reserved for headline runs: the T1 check (06) and the replication (09), whose verdicts use the 318 questions outside eval. Prompts were only ever iterated on the dev 30.
- **Metric.** BIRD's official execution accuracy: set equality of result rows. It was validated line by line against `calculate_ex`, and gold vs gold scores 100%.
- **Statistics.** Every config answers the same questions, so every comparison is **paired**: an exact McNemar test plus a paired bootstrap CI. When several tests are reported together they are Holm-corrected.
- **One change at a time.** Each config differs from its parent by one flag of a single `PipelineConfig`, which promptfoo passes to one custom Python provider. A custom Python assertion scores EX.
- **promptfoo-native (08).** The single-call C1 config also runs on promptfoo's `ollama:chat` provider as a prompts × providers matrix, with built-in assertions, a local `llm-rubric` judge and an exit-code gate (`PROMPTFOO_PASS_RATE_THRESHOLD`). Each feature is scored against EX rather than trusted (D23).
- **CI.** GitHub Actions runs the tests that need no data, `promptfoo validate` on every config, and a check that `results/summary.md` rebuilds byte-identical from the committed CSVs. Model runs stay local.
- **Determinism.** Temperature 0, seed 42, thinking off. Voting candidates sample with fixed seeds. Every LLM call is cached on disk, keyed by its exact request, so reruns are free and identical, and timings are the original call's. The cache matters: on Ollama's MLX runner, a fresh qwen3.5 call doesn't reproduce about 1 in 7 old replies despite the fixed seed (D23). On the 5070's llama.cpp runner (Ollama 0.40.17), replies also depend on server state, for both models (D24). A hash-seed nondeterminism bug was found by that cache and fixed (D17).
- **No leakage.** Gold SQL never reaches a prompt except in the labelled oracle config. SQL-check detectors were calibrated on query-log gold SQL, never on eval.
- **Provenance.** `qwen3.5:9b`, digest `d63f830f28d5` (9.7B, nvfp4, MLX runner). Ollama 0.40.16, promptfoo 0.125.1, Node 22.23. All 10,234 qwen3.5 calls came from that one model build. The rerun's 4,209 calls came from `qwen2.5-coder:7b`, digest `dae161e27b0e` (7.6B, Q4_K_M, llama.cpp runner). Experiment 08's 600 generations and 600 judge verdicts used the same two builds, through promptfoo's cache. Experiment 09 ran on Windows (RTX 5070, Ollama 0.40.17, promptfoo 0.125.1, Node 22.23): 22,000 new calls from `qwen3.5:9b` digest `56671c2ab938` (9.0B, Q4_K_M, llama.cpp; Modelfile defaults `presence_penalty 1.5`, `top_k 20`, `top_p 0.95` kept) and the same coder digest, plus 1,872 generations and 1,872 judge verdicts.

## Reproduce

Requirements: macOS or Linux (Windows for 09, see D24), [uv](https://docs.astral.sh/uv/), Node ≥ 22.22, [Ollama](https://ollama.com) ≥ 0.40, about 16 GB free (13 GB of models, 2.5 GB of data).

Install dependencies and pull the models:

```bash
make setup
```

Download MiniDev (801 MB) and cache the gold results:

```bash
make data
```

Profile the databases, write the LLM column summaries and build the indexes (about 70 min):

```bash
make metadata
```

Build the few-shot pools (about 1.5 h of LLM time):

```bash
make fewshot
```

Run each experiment on the eval split (about 11 h in total on an M3 Pro), then rebuild the summary and figures:

```bash
make run-01 run-02 run-03 run-04 run-05 run-06 SPLIT=eval
```

The T1 check on the 468-question test split (about 80 min):

```bash
uv run python scripts/run_ablation.py promptfoo/configs/06_trimming.yaml --split test --providers '^(C3-fused|T1-short-profile)(\+hints)?$'
```

The qwen2.5-coder:7b rerun of the headline configs (about 5 h of model time):

```bash
make run-07 SPLIT=eval
```

Experiment 08, promptfoo's native provider, built-in assertions and LLM judge (about 4 h, most of it the judge):

```bash
make run-08 SPLIT=eval
```

Experiment 09, the 28 headline configs on the 468-question test split, then the judge cells. It took about 6.4 h of warm-ups plus about 5.5 h for the judge on an RTX 5070. On Windows, run without `make`, and pin the Ollama version the run started on:

```bash
BIRDEVAL_OLLAMA_VERSION=0.40.17 uv run python scripts/run_ablation.py promptfoo/configs/09_replication.yaml --split test
BIRDEVAL_OLLAMA_VERSION=0.40.17 uv run python scripts/run_native.py --split test --experiment 09_judge
uv run python analysis/export_csv.py --only 09_replication
uv run python analysis/export_native.py --experiment 09_judge --split test
```

If the combined pass has to be redone after the warm-ups, `--replay` (optionally `--jobs 1`) replays it from the cache without calling the model.

The regression gate: exits non-zero if C1's dev EX on the coder drops below `GATE` % (default 20; baseline 26.7):

```bash
make gate
```

```bash
make summary
```

`make summary` only needs the committed [results/per_question.csv](results/per_question.csv) (one row per config and question), [results/per_question_test.csv](results/per_question_test.csv) (the T1 test-split run), [results/per_question_native.csv](results/per_question_native.csv) (experiment 08), and [results/per_question_5070.csv](results/per_question_5070.csv) and [results/per_question_native_5070.csv](results/per_question_native_5070.csv) (experiment 09). Every table, figure and test in this README can be recomputed from it without models or data.

`make view` opens promptfoo's web viewer on the local runs, showing each test's actual prompt, SQL, score and latency.

## Repository layout

```
src/birdeval/      the pipeline: schema rendering, profiling, linking, few-shot, voting, SQL checks, EX scoring
promptfoo/         provider (one PipelineConfig per config), EX assertion, prompt functions, one YAML per experiment, test sets
scripts/           data prep and the two-pass runner (warm-up at -j 1, then a cache-only combined pass)
analysis/          paired tests, per-question export, summary + figures, error analysis
results/           per-run tables, per_question.csv, summary.md (raw promptfoo JSON stays local)
docs/              results, eval design, decisions log (D1–D24), error analysis, paper summary, figures
tests/             104 pytest tests: evaluator, schema renderer, linking, few-shot leakage, voting, checks, trims, judge leakage, repeat-limit abort
.github/workflows/ CI: data-free tests, promptfoo validate, summary rebuild check
tasks/             the plan and the lessons log kept during the project
```

## Limitations

- **Sample size.** At n = 150, a single accuracy has a ±8 pp CI. Paired tests detect differences of roughly 5 pp and up. "Not significant" here means "smaller than that, if real".
- **Two local models, one seed.** Run-to-run variance across seeds isn't measured, and a fresh qwen3.5 rerun isn't bit-identical even with the same seed (D23): the reported numbers are one recorded run. The `qwen2.5-coder:7b` rerun reuses qwen3.5's profile summaries. The 468-question test split has been run for C3 vs T1, where it reversed the eval reading, and for the headline configs on both models (09). That run was on a second machine with a different qwen3.5 build, so its numbers stand on their own and aren't pooled with the Mac's.
- **The 09 machine was unstable under heavy CPU load.** Its GPU dropped off the bus and its CPU logged a fatal machine-check error, both during cache-only passes after all model calls had finished. No recorded reply was affected (D24), but the hardware cause wasn't diagnosed.
- **The summarizer is the same 9B model.** An audit found 20% of its profile summaries wrong (D14). A stronger summarizer, as in the paper, could widen the profiling gain.
- **Few-shot pools differ from the paper.** The "query log" pool is BIRD dev questions on the same databases. BIRD has no real query logs.
- **BIRD gold SQL has errors.** 3 of 20 sampled failures are gold-side. All configs share the same gold, so comparisons stay fair, but absolute numbers are bounded by it.

## What I learned about evals

From [tasks/lessons.md](tasks/lessons.md), which I kept as the project ran:

- **A frozen eval split earns its keep.** Twice, a change that looked like +7 to +13 pp on the 30 dev questions came out at 0 on the 150 eval questions. A winner picked on a small slice is a hypothesis, not a result.
- **Framing matters more than content.** The same eight few-shot examples were worth 0 or −17 pp depending on one hand-off sentence.
- **Cache misses on an unchanged pipeline mean nondeterminism.** A set iteration order that depended on `PYTHONHASHSEED` was changing prompts between processes.
- **Execute both queries before blaming the evaluator, and before blaming the gold SQL.** A "logically identical" pair I suspected of an evaluator bug turned out to be an alias bug in the model's SQL. Two suspected gold bugs were confirmed only by running queries.
- **Correct for multiple tests.** A lone p = 0.03 out of four comparisons isn't a finding.
- **Size a non-inferiority margin against the CI you'll actually get.** I pre-registered "safe to trim = loss under 5 pp", but at n = 150 the paired CIs are ±5–7 pp wide, so a trim with no true effect fails about half the time or more. I reported the verdicts as registered: one trim hurts, and the other three are "inconclusive" rather than "safe".
- **A point estimate of ~0 is not "no loss".** Short summaries scored +0.7 pp on the 150 eval questions, and I called them the next candidate. On 468 questions they cost −4.5 pp (Holm p = 0.025). An inconclusive result is a reason to run more questions, not a lean toward "safe".
- **Compare models in more than one condition.** The coder was ahead of qwen3.5 without hints and behind it with hints in 6 of 7 configs. A comparison run in only one setting would have pointed to either model as the better one.
- **A fixed seed isn't determinism; check the runtime.** I assumed temperature 0 and seed 42 made reruns identical. On Ollama's MLX runner they didn't, about 1 reply in 7. My numbers are reproducible only because every call was cached, and I found out only by comparing two providers.
- **Measure a built-in check before trusting it.** `is-sql` silently defaults to MySQL and flagged 6.4% of valid SQLite. An LLM judge with κ = 0.43 looked fine per cell, but it doubled one A/B effect, the kind of decision an eval exists to make.
- **Confirm a lead on questions it wasn't found on.** "Hints help the coder less" was −7.9 pp on eval. Pre-registered on 318 fresh questions, it was +0.6, while the same machine still gave −5.8 on the eval questions. The leads that held (the full pipeline, linking with hints) got larger on fresh questions.
- **A replay is only as cached as its least-cached input.** The combined pass replays every LLM call from disk but recomputes the linking embeddings. When the GPU fell back to the CPU, slightly different embeddings changed 30 prompts. A cache-only pass should cache everything a prompt depends on.
- **Quote numbers from the source, never from memory.** I misquoted the paper's Table 2 once and caught it only by re-reading the PDF.

## License and data

The code is MIT ([LICENSE](LICENSE)); the MIT license covers this project's own code and docs only. BIRD MiniDev is © its authors under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The files here that carry BIRD questions and hints (`promptfoo/tests/*.yaml`) stay under that license. The databases, the paper PDF and model outputs aren't redistributed. `make data` downloads MiniDev from BIRD's official mirror.

## Citations

```bibtex
@article{shkapenyuk2025automatic,
  title   = {Automatic Metadata Extraction for Text-to-SQL},
  author  = {Shkapenyuk, Vladislav and Srivastava, Divesh and Johnson, Theodore and Ghane, Parisa},
  journal = {arXiv preprint arXiv:2505.19988},
  year    = {2025}
}

@article{li2024can,
  title   = {Can LLM Already Serve as a Database Interface? A Big Bench for Large-Scale Database Grounded Text-to-SQLs},
  author  = {Li, Jinyang and Hui, Binyuan and Qu, Ge and Yang, Jiaxi and Li, Binhua and Li, Bowen and Wang, Bailin and Qin, Bowen and Geng, Ruiying and Huo, Nan and others},
  journal = {Advances in Neural Information Processing Systems},
  volume  = {36},
  year    = {2024}
}
```
