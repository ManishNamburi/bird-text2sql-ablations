# Lessons

Rules learned while working on this project. Review at session start.

## Environment
- Check tool version constraints before planning around them: the latest promptfoo requires Node ≥ 22.22, but this machine has Node 20.20. Ollama 0.5.7 predates the Qwen3/3.5 model families.

## Data and evaluator
- Validate the evaluator before any model run: gold vs gold must score 100%. This caught two slow gold queries (timeouts) and two duplicate question_ids in MiniDev.
- Never swap the execution engine for speed without diffing results against ground truth: DuckDB changed or broke 27% of gold answers.
- Key everything by `question_id` and assert uniqueness.

## Local LLM ops
- Don't run CPU-heavy jobs beside an LLM batch: JSON-constrained decoding tripled from 5 to 17 s/call while indexes were building.
- Ollama's MLX runner ignores `num_ctx`, while llama.cpp enforces it (silent truncation). Set one large `num_ctx` everywhere and assert `prompt_tokens < num_ctx`.
- Generated artifacts (LLM summaries) feed every later config. Audit a seeded sample before running ablations on them.
- When a summarizer hallucinates, fix the input before the prompt: the "stored as text" error came from the profile not stating the storage class.

## promptfoo
- promptfoo injects `basePath` into a Python provider's `config`. Strip its known keys, then validate strictly.
- promptfoo iterates `for test: for provider:`. Never run several local-LLM configs interleaved; warm up one config at a time.
- promptfoo's `latencyMs` is ~0 on cache hits. Report timings stored with the original call.
- Never trust result order in promptfoo's JSON export. Order by the config's label list.

## Corrections from the user
_(none yet)_
