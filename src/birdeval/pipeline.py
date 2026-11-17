"""The text-to-SQL pipeline. Every ablation is a PipelineConfig; configs differ only in flags.

  C0-C3  single call; metadata none | bird | profile | fused; hints on/off
  C4     + schema linking (paper §3): linking="llm"; the final SQL is generated on the
         linked columns only. linking="oracle" uses the gold SQL's columns (upper bound).
  C5     + few-shot examples in the final call: fewshot="train" (paper) | "querylog" (same DB).
  C6     + `votes` candidates for the final call and a majority vote on execution results
         (paper §4). Candidate 0 is the single-candidate call; candidates i >= 1 shuffle the
         column order (shuffle_seed=i) and sample with seed+i at vote_temperature (D19).
  C7     + SQL sanity checks (paper §4) on every candidate before the vote: checks=True. A
         flagged candidate gets up to check_retries correction calls (D20).
  T1-T4  prompt trims of the final call, one flag each (D21): profile_detail="short",
         profile_values=False (mask example values), bird_values=False, system="minimal".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from birdeval import prompts
from birdeval.fewshot import examples_for
from birdeval.linking import VARIANTS, link, oracle_fields
from birdeval.llm import DEFAULT_MODEL, DEFAULT_NUM_CTX, LLMResult, chat, extract_sql
from birdeval.promptbuild import messages, schema_text
from birdeval.sqlchecks import check_sql, correction_messages
from birdeval.sqlexec import execute
from birdeval.voting import VOTE_TIMEOUT_S, vote


@dataclass(frozen=True)
class PipelineConfig:
    model: str = DEFAULT_MODEL
    metadata: Literal["none", "bird", "profile", "fused"] = "none"
    bird_values: bool = True  # include BIRD value descriptions (prompt-trimming knob)
    profile_detail: Literal["long", "short"] = "long"  # paper: long for SQL generation
    profile_values: bool = True  # False masks quoted example values in profile summaries (T2)
    hints: bool = False  # BIRD "evidence" (the paper's oracle hint)
    linking: Literal["none", "llm", "oracle"] = "none"
    link_variants: tuple[str, ...] = tuple(VARIANTS)  # paper uses all five
    link_k: int = 15  # semantic neighbours in the focused schema
    link_max_retry: int = 1  # literal-revision rounds per variant
    fewshot: Literal["none", "train", "querylog"] = "none"
    fewshot_k: int = 8  # paper uses 8
    fewshot_framing: Literal["inline", "separated"] = "inline"  # separated: hand-off line after examples
    fewshot_example_hints: bool = True  # show examples' BIRD hints (only when hints=True)
    votes: int = 1  # candidates for the final call; 1 = no voting (paper uses 3)
    vote_temperature: float = 0.7  # for candidates 1.. (seed changes are inert at T=0)
    system: Literal["full", "minimal"] = "full"  # final-call system prompt; linking keeps "full" (T4)
    checks: bool = False  # paper §4 SQL sanity checks + correction, per candidate (C7)
    check_retries: int = 3  # paper: "up to three retries"
    num_ctx: int = DEFAULT_NUM_CTX
    seed: int = 42

    def __post_init__(self):
        if self.metadata not in ("none", "bird", "profile", "fused"):
            raise ValueError(f"unknown metadata variant: {self.metadata!r}")
        if self.profile_detail not in ("long", "short"):
            raise ValueError(f"unknown profile_detail: {self.profile_detail!r}")
        if self.system not in ("full", "minimal"):
            raise ValueError(f"unknown system: {self.system!r}")
        if self.linking not in ("none", "llm", "oracle"):
            raise ValueError(f"unknown linking: {self.linking!r}")
        if self.fewshot not in ("none", "train", "querylog"):
            raise ValueError(f"unknown fewshot: {self.fewshot!r}")
        if self.fewshot_framing not in ("inline", "separated"):
            raise ValueError(f"unknown fewshot_framing: {self.fewshot_framing!r}")
        if self.votes < 1:
            raise ValueError(f"votes must be >= 1, got {self.votes}")
        if self.check_retries < 0:
            raise ValueError(f"check_retries must be >= 0, got {self.check_retries}")
        object.__setattr__(self, "vote_temperature", float(self.vote_temperature))  # 0 vs 0.0 in the cache key
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


def build_messages(q: dict, cfg: PipelineConfig, columns=None, examples=None,
                   shuffle_seed: int | None = None) -> list[dict]:
    schema = schema_text(q["db_id"], cfg.metadata, cfg.profile_detail, columns, cfg.bird_values, shuffle_seed,
                         cfg.profile_values)
    system = prompts.SYSTEM if cfg.system == "full" else prompts.SYSTEM_MINIMAL
    return messages(schema, q, cfg.hints, examples, cross_db=cfg.fewshot == "train",
                    example_hints=cfg.fewshot_example_hints, separated=cfg.fewshot_framing == "separated",
                    system=system)


def _runs(db_id: str, sql: str) -> bool:
    return bool(sql.strip()) and execute(db_id, sql, VOTE_TIMEOUT_S).ok


def correct(q: dict, cfg: PipelineConfig, msgs: list[dict], sql: str, seed: int,
            calls: list[LLMResult]) -> tuple[str, dict]:
    """Check one candidate and ask for corrections while a check fires (paper §4).
    Each retry shows the candidate's own conversation, the current SQL and its problems; T = 0.
    A revision that fails to execute is not adopted (a correction must not create an error), and
    the loop stops when a revision is rejected or unchanged, since a T = 0 retry would repeat it."""
    issues = check_sql(sql, q["db_id"])
    fired = [i.check for i in issues]
    cur, retries = sql, 0
    while issues and retries < cfg.check_retries:
        retries += 1
        r = chat(correction_messages(msgs, cur, issues), model=cfg.model, num_ctx=cfg.num_ctx, seed=seed)
        calls.append(r)
        new = extract_sql(r.text)
        if new == cur or (not _runs(q["db_id"], new) and _runs(q["db_id"], cur)):
            break
        cur = new
        issues = check_sql(cur, q["db_id"])
    return cur, {"fired": fired, "retries": retries, "remaining": [i.check for i in issues],
                 "original": sql, "changed": cur != sql}


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
    cand_msgs, cand_sqls = [msgs], [extract_sql(r.text)]
    for i in range(1, cfg.votes):
        m = build_messages(q, cfg, columns, examples, shuffle_seed=i)
        ri = chat(m, model=cfg.model, num_ctx=cfg.num_ctx, seed=cfg.seed + i, temperature=cfg.vote_temperature)
        calls.append(ri)
        cand_msgs.append(m)
        cand_sqls.append(extract_sql(ri.text))

    if cfg.checks:
        checked = [correct(q, cfg, m, sql, cfg.seed + i, calls)
                   for i, (m, sql) in enumerate(zip(cand_msgs, cand_sqls))]
        cand_sqls = [sql for sql, _ in checked]
        extra.update(check_traces=[t for _, t in checked],
                     check_fired=sorted({c for _, t in checked for c in t["fired"]}),
                     check_calls=sum(t["retries"] for _, t in checked),
                     check_changed=any(t["changed"] for _, t in checked))
    if cfg.votes == 1:
        return PipelineResult(sql=cand_sqls[0], messages=msgs, calls=calls, extra=extra)

    v = vote(q["db_id"], cand_sqls)
    extra.update(vote_sqls=cand_sqls, vote_groups=v.groups, vote_winner=v.winner,
                 vote_unanimous=min(v.groups) == cfg.votes,  # all executed and returned the same rows
                 vote_distinct_sql=len(set(cand_sqls)),
                 vote_exec_ms=round(v.exec_ms))
    return PipelineResult(sql=cand_sqls[v.winner], messages=cand_msgs[v.winner], calls=calls, extra=extra)
