# Handoff: test-split replication on the RTX 5070 desktop (written 2026-11-22)

You are picking this project up on a new machine with no memory of the earlier sessions. Read `CLAUDE.md`, `tasks/lessons.md`, `docs/decisions.md` (D1–D23) and `docs/results.md` first. The project rules in `CLAUDE.md` apply in full. In particular: **write a spec in `tasks/todo.md` and check in with the user before running anything that costs model time.**

## Where the project stands
- Repo: https://github.com/ManishNamburi/bird-text2sql-ablations (public). It was handed off at commit `8ddd66b`; CI is green.
- Experiments 01–08 are done on a MacBook Pro M3 Pro (18 GB):
  - `qwen3.5:9b`, digest `d63f830f28d5`, nvfp4 on Ollama's **MLX** runner;
  - `qwen2.5-coder:7b`, digest `dae161e27b0e`, Q4_K_M on **llama.cpp**;
  - Ollama 0.40.16, promptfoo 0.125.1, Node 22.23, Python 3.12.7.
- Every number is on the frozen eval split (150 questions). The 468-question test split (`promptfoo/tests/test.yaml`) has only been used for C3 vs T1 (D21).

## The goal: one pre-registered replication on the test split
Run the 7 headline configs (C0, C1, C3, C4, C6, C7, oracle), ± hints, on **both models**, over the **468 test questions**, entirely on this machine. Optionally add the 08 judge cells. At n = 468, paired tests detect ~3 pp instead of ~5 pp, which settles the leads left open on eval:

1. **C7 vs C1** (full pipeline vs one call): +8.7 pp on eval, Holm p = 0.35.
2. **C3 → C4** (schema linking): +4.7 / +3.3 pp on eval, not significant.
3. **Hints help the coder less:** −7.9 pp pooled (−14.1 to −2.0), post hoc on eval (D22, results §07).
4. **The LLM judge overstates the hint effect** on the coder: +18.0 vs +9.3 pp by EX, difference +8.7 (+0.7 to +17.3), not pre-registered (D23, results §08).

Write these as hypotheses with their tests (paired bootstrap CI, exact McNemar, Holm over the family) and expected CI widths **before** any run, as in the 07 spec in `tasks/todo.md`. The test split contains the 150 eval questions. Report the 318 outside eval separately, as D21 did.

## The model build will be different: treat this as its own run
- On NVIDIA, Ollama won't serve the Mac's nvfp4/MLX build of `qwen3.5:9b`. Check what `ollama pull qwen3.5:9b` gives here (digest, quantization, runner via `ollama show`) and record it.
- **Never mix 5070 numbers with Mac numbers.** Every comparison is within this machine's run, including its own C1 and C3 baselines. The Mac results are context, not a parent config.
- Same for `qwen2.5-coder:7b`: record its digest here, even if it matches.
- Determinism: on the Mac, MLX didn't reproduce ~1 in 7 replies at temperature 0 and seed 42; llama.cpp did (D23). Before the main run, check it here: run 10 dev C1 calls twice with the cache off and compare. Report the result either way.

## Copy the derived metadata; don't regenerate it
`data/derived/` (profiles, LLM column summaries, embeddings, few-shot pools, value index) is gitignored and was generated on the Mac with qwen3.5. Regenerating it here would change the summaries and the replication would vary two things at once (the D22 rule: summaries stay qwen3.5's).
- Archive: `bird_derived_2026-11-22.tar.gz` (123 MB), handed over separately by the user, **not** in git. It may arrive as 5 parts (`….part_a` to `….part_e`). Join them in order:
  - Linux, WSL or Git Bash: `cat bird_derived_2026-11-22.tar.gz.part_* > bird_derived_2026-11-22.tar.gz`
  - Windows cmd: `copy /b bird_derived_2026-11-22.tar.gz.part_a+bird_derived_2026-11-22.tar.gz.part_b+bird_derived_2026-11-22.tar.gz.part_c+bird_derived_2026-11-22.tar.gz.part_d+bird_derived_2026-11-22.tar.gz.part_e bird_derived_2026-11-22.tar.gz`
- SHA-256: `90c0a82e4e3660625615d8fe0ee11d81e5c58ec6a497c7a032ee6e267556106f`. Verify it before extracting.
- Extract from the repo root: `tar -xzf bird_derived_2026-11-22.tar.gz` gives `data/derived/…`.
- Don't run `make metadata` or `make fewshot`. Run `make data` (downloads MiniDev and caches gold results) and `uv run pytest -q` (expect 103 passed once the data is in place).
- `nomic-embed-text` is still needed for query-time embeddings: `ollama pull nomic-embed-text`.

## Mac-specific bits to adapt (small, separate commit)
- `Makefile` line 3 and `scripts/run_ablation.py` line 32 hard-code Homebrew's Node 22 path (`/opt/homebrew/opt/node@22/bin`). promptfoo needs Node ≥ 22.22. Make the path optional (use it only if it exists) rather than replacing it, so the Mac keeps working.
- Long runs on the Mac started under `caffeinate`. On this machine, prevent sleep the local way (Windows: power plan "never sleep" while running; Linux: `systemd-inhibit`). Then check the OS's sleep log before trusting any wall-clock time (lesson from 08).
- Check the GPU first: `nvidia-smi`. A desktop 5070 has 12 GB of VRAM. The two models can't be resident together, and the runners already run one model at a time. Watch that `num_ctx` 24,576 fits; the runner refuses truncated prompts (D13).

## Cost and expectations
- On the Mac, the 7 configs ± hints cost ~314 s per question for qwen3.5 (~41 h at 468). The 5070 should be several times faster; time 10 dev questions per config first and put a real estimate in the spec.
- Seconds aren't comparable to the Mac's; tokens are. Report both, labelled by machine.
- Raw outputs stay out of git (`results/raw/`, `.cache/`, `.promptfoo/`). Commit the `results/*.md` tables and a new per-question CSV, as for 07.

## Done means
- Spec approved by the user, then runs with 0 provider errors and a fully cached combined pass.
- New results section and decision entry (D24), README and `eval-design.md` provenance updated, every number generated from the CSV, the summary rebuilding byte-identically, and CI green.
- Commit and push only when the user asks.
