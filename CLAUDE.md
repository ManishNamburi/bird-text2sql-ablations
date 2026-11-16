# CLAUDE.md — BIRD text-to-SQL ablation study with promptfoo

## Project context

- **Goal:** Reproduce, at small scale and on a local LLM, the ablations from AT&T CDO's paper
  *"Automatic Metadata Extraction for Text-to-SQL"* (Shkapenyuk, Srivastava, Ghane, Johnson, 2025),
  and use **promptfoo** to measure how much each technique contributes, what it costs in prompt tokens and latency,
  and which prompt sections can be trimmed.
- **Purpose:** A learning project about evals that goes on a résumé and GitHub. Every step is documented and
  every tradeoff is written down (`docs/decisions.md`).
- **Hardware:** MacBook Pro M3 Pro, 18 GB unified memory, 11 cores. Models run locally through Ollama.
- **Dataset:** BIRD MiniDev (SQLite) — 500 questions over 11 databases. Metric is execution accuracy (EX).
- **The paper PDF is not committed** (copyright). The README links to the published paper instead.

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately
- Don't keep pushing.
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep the main context window clean.
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- Capture Lessons: Update this file (CLAUDE.md) with any change in approach the user has asked you to make.
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until the mistake rate drops.
- Review lessons (`tasks/lessons.md`) at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself, "Would a staff engineer approve this?"
- Run tests, check logs, and demonstrate correctness.

### 5. Demand Elegance (Balanced)
- For non-trivial changes, pause and ask, "Is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes
- Don't over-engineer.
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report, just fix it. Don't ask for hand-holding
- Point at logs, errors, and failing tests.
- Then resolve them.
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write a plan to `tasks/todo.md` with checkable items.
2. **Verify Plan**: Check in before starting implementation.
3. **Track Progress**: Mark items complete as you go.
4. **Explain Changes**: High-level summary at each step.
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

## Project rules (eval hygiene)

- **Change one variable at a time.** Each ablation config differs from its parent by exactly one technique.
- **Freeze the eval set.** The question subset is chosen once with a fixed seed and committed (`data/subset_ids.json`).
  Never tune prompts while looking at the eval set; use the separate dev slice for iteration.
- **Determinism:** temperature 0 and a fixed seed for single-candidate runs. Record the model tag and digest,
  the Ollama version, and the promptfoo version in every results file.
- **Report uncertainty.** Every accuracy gets a 95% CI. Every A-vs-B claim uses a paired test (McNemar) on the same questions.
- **Track cost alongside accuracy.** Report prompt tokens, completion tokens, and wall-clock time for each config.
- **Never let gold SQL leak** into a prompt, except in the explicitly labelled "oracle / perfect linking" upper-bound config.
- Large files (databases, model outputs, promptfoo DB) stay out of git; see `.gitignore`.
