"""The text-to-SQL pipeline. Every ablation is a PipelineConfig; configs differ only in flags.

  C0-C3  single call; metadata none | bird | profile | fused; hints on/off
  C4     + schema linking (paper §3): linking="llm"; the final SQL is generated on the
         linked columns only. linking="oracle" uses the gold SQL's columns (upper bound).
  C5     + few-shot examples in the final call: fewshot="train" (paper) | "querylog" (same DB).
Later phases add voting and SQL checks here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from birdeval.fewshot import examples_for
from birdeval.linking import VARIANTS, link, oracle_fields
from birdeval.llm import DEFAULT_MODEL, DEFAULT_NUM_CTX, LLMResult, chat, extract_sql
from birdeval.promptbuild import messages, schema_text


@dataclass(frozen=True)
class PipelineConfig:
    model: str = DEFAULT_MODEL
    metadata: Literal["none", "bird", "profile", "fused"] = "none"
    bird_values: bool = True  # include BIRD value descriptions (prompt-trimming knob)
    profile_detail: Literal["long", "short"] = "long"  # paper: long for SQL generation
    hints: bool = False  # BIRD "evidence" (the paper's oracle hint)
    linking: Literal["none", "llm", "oracle"] = "none"
    link_variants: tuple[str, ...] = tuple(VARIANTS)  # paper uses all five
    link_k: int = 15  # semantic neighbours in the focused schema
    link_max_retry: int = 1  # literal-revision rounds per variant
    fewshot: Literal["none", "train", "querylog"] = "none"
    fewshot_k: int = 8  # paper uses 8
    fewshot_framing: Literal["inline", "separated"] = "inline"  # separated: hand-off line after examples
    fewshot_example_hints: bool = True  # show examples' BIRD hints (only when hints=True)
    num_ctx: int = DEFAULT_NUM_CTX
    seed: int = 42

    def __post_init__(self):
        if self.metadata not in ("none", "bird", "profile", "fused"):
            raise ValueError(f"unknown metadata variant: {self.metadata!r}")
        if self.profile_detail not in ("long", "short"):
            raise ValueError(f"unknown profile_detail: {self.profile_detail!r}")
        if self.linking not in ("none", "llm", "oracle"):
            raise ValueError(f"unknown linking: {self.linking!r}")
        if self.fewshot not in ("none", "train", "querylog"):
            raise ValueError(f"unknown fewshot: {self.fewshot!r}")
        if self.fewshot_framing not in ("inline", "separated"):
            raise ValueError(f"unknown fewshot_framing: {self.fewshot_framing!r}")
        object.__setattr__(self, "link_variants", tuple(self.link_variants))  # YAML gives lists
        unknown = set(self.link_variants) - set(VARIANTS)
        if unknown:
            raise ValueError(f"unknown link_variants: {sorted(unknown)}")


@dataclass
class PipelineResult:
    sql: str
    messages: list[dict]
    calls: list[LLMResult] = field(default_factory=list)
    extra: dict = field(default_factory=dict)  # diagnostics for promptfoo metadata


def build_messages(q: dict, cfg: PipelineConfig, columns=None, examples=None) -> list[dict]:
    schema = schema_text(q["db_id"], cfg.metadata, cfg.profile_detail, columns, cfg.bird_values)
    return messages(schema, q, cfg.hints, examples, cross_db=cfg.fewshot == "train",
                    example_hints=cfg.fewshot_example_hints, separated=cfg.fewshot_framing == "separated")


def run(q: dict, cfg: PipelineConfig) -> PipelineResult:
    """q needs: question_id, db_id, question, evidence (only used when cfg.hints)."""
    calls: list[LLMResult] = []
    extra: dict = {}
    columns = None
    if cfg.linking == "llm":
        lr = link(q, model=cfg.model, hints=cfg.hints, variants=cfg.link_variants, k=cfg.link_k,
                  max_retry=cfg.link_max_retry, num_ctx=cfg.num_ctx, seed=cfg.seed)
        calls += lr.calls
        columns = lr.fields or None  # nothing parsable -> fall back to the full schema
        extra.update(link_fallback=not lr.fields, link_revisions=sum(t.revised_sql is not None for t in lr.traces),
                     link_traces=[t.__dict__ for t in lr.traces])
    elif cfg.linking == "oracle":
        columns = oracle_fields(q)

    if cfg.linking != "none":
        # Diagnostic only (never in a prompt): how much of the gold SQL's schema did we keep?
        gold = oracle_fields(q)
        kept = columns or set()
        extra.update(link_size=len(kept), link_recall=round(len(gold & kept) / len(gold), 3) if gold else 1.0)

    examples = examples_for(q, cfg.fewshot, cfg.fewshot_k) if cfg.fewshot != "none" else None
    if examples:
        extra.update(fewshot_ids=[e["id"] for e in examples], fewshot_top_sim=examples[0]["similarity"])
    msgs = build_messages(q, cfg, columns, examples)
    r = chat(msgs, model=cfg.model, num_ctx=cfg.num_ctx, seed=cfg.seed)
    calls.append(r)
    return PipelineResult(sql=extract_sql(r.text), messages=msgs, calls=calls, extra=extra)
