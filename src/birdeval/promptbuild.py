"""The single place where a schema view + question become chat messages.

Shared by the single-call pipeline and schema linking, so identical views produce
byte-identical prompts (and hit the LLM cache) - e.g. the linking variant
`full_maximal` is exactly the C2 prompt.
"""

from __future__ import annotations

from birdeval import prompts
from birdeval.profiling import load_summaries, mask_literals
from birdeval.schema import render


def schema_text(db_id: str, metadata: str, detail: str = "long", columns=None,
                bird_values: bool = True, shuffle_seed: int | None = None,
                profile_values: bool = True) -> str:
    """metadata: none | bird | profile | fused; detail: long | short profile summaries.
    profile_values=False masks the quoted example values in the summaries (T2)."""
    profile = None
    if metadata in ("profile", "fused"):
        profile = load_summaries(db_id, detail)
        if not profile_values:
            profile = {k: mask_literals(v) for k, v in profile.items()}
    return render(db_id, bird=metadata in ("bird", "fused"), bird_values=bird_values, profile=profile,
                  columns=columns, shuffle_seed=shuffle_seed)


def messages(schema: str, q: dict, hints: bool, examples: list[dict] | None = None,
             cross_db: bool = False, example_hints: bool = True, separated: bool = False,
             system: str = prompts.SYSTEM) -> list[dict]:
    evidence = q.get("evidence") if hints else None
    block = (prompts.few_shot_block(examples, hints and example_hints, cross_db, separated)
             if examples else None)
    return [{"role": "system", "content": system},
            {"role": "user", "content": prompts.user_message(schema, q["question"], evidence, block)}]
