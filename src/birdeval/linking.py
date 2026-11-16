"""Schema linking (paper §3) and oracle ("perfect") linking.

The paper's insight: LLMs are poor at *directly* choosing relevant columns but good at
writing SQL - so link by generating SQL under several schema views and collecting the
fields those queries use. Recall beats precision: the union of all variants is kept.

For each schema variant:
  1. generate SQL for the question with that schema
  2. collect its fields and string literals
  3. for each literal, look up which fields actually contain it (value LSH index); if none of
     those fields is used by the query, add them to the schema and ask for one revision
  4. add the (revised) query's fields to the linked set

Variants (paper names; "full profile" = SME + long summary = our fused metadata):
  focused_minimal  focused schema, short summaries      full_minimal  full schema, short
  focused_maximal  focused schema, long summaries       full_maximal  full schema, long
  focused_full     focused schema, fused metadata
The focused schema = columns semantically close to the question (embeddings) + columns
whose values match literals in the question (value index) (+ keys, added by the renderer).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from birdeval import prompts
from birdeval.embed import similar_columns
from birdeval.llm import LLMResult, chat, extract_sql
from birdeval.promptbuild import messages, schema_text
from birdeval.sqlexec import DATA_ROOT
from birdeval.sqlfields import Field, extract_fields, extract_literals
from birdeval.valueindex import lookup

VARIANTS: dict[str, tuple[bool, str, str]] = {  # name -> (focused?, metadata, profile_detail)
    "focused_minimal": (True, "profile", "short"),
    "focused_maximal": (True, "profile", "long"),
    "full_minimal": (False, "profile", "short"),
    "full_maximal": (False, "profile", "long"),
    "focused_full": (True, "fused", "long"),
}

LITERAL_MATCH = 0.85  # shingle-Jaccard needed to say "this field contains this literal"
_STOP = set("""a an the of in on at to for from by with and or not no is are was were be been
what which who whom whose how many much list give show find name names number count
please among all each per than that this these those their its it as do does did have has
had there between more most less least average total amount percentage ratio""".split())


@dataclass
class LinkTrace:
    variant: str
    sql: str
    fields: list[str]
    missing_literals: dict[str, list[str]] = field(default_factory=dict)
    revised_sql: str | None = None


@dataclass
class LinkResult:
    fields: set[Field]
    calls: list[LLMResult] = field(default_factory=list)
    traces: list[LinkTrace] = field(default_factory=list)
    focused: set[Field] = field(default_factory=set)


def _ngrams(text: str, max_n: int = 6) -> list[str]:  # BIRD literals run long ("Fresno County Office of Education")
    words = re.findall(r"[\w'.-]+", text)
    out = []
    for n in range(max_n, 0, -1):
        for i in range(len(words) - n + 1):
            gram = words[i : i + n]
            if all(w.lower() in _STOP for w in gram) or len(" ".join(gram)) < 3:
                continue
            out.append(" ".join(gram).strip("'\".,"))
    return out


def question_literal_fields(db_id: str, text: str) -> set[Field]:
    """Fields containing (near-)exact matches for n-grams / quoted strings of the question."""
    candidates = re.findall(r"'([^']+)'|\"([^\"]+)\"", text)
    grams = [a or b for a, b in candidates] + _ngrams(text)
    out: set[Field] = set()
    for g in dict.fromkeys(grams):
        for m in lookup(db_id, g, min_similarity=LITERAL_MATCH, top_k=5):
            out.add((m.table.lower(), m.column.lower()))
    return out


def focused_fields(q: dict, hints: bool, k: int) -> set[Field]:
    text = q["question"] + (f" {q['evidence']}" if hints and q.get("evidence") else "")
    sem = {(t.lower(), c.lower()) for t, c, _ in similar_columns(q["db_id"], text, k)}
    return sem | question_literal_fields(q["db_id"], text)


def _missing_literals(db_id: str, sql: str, used: set[Field]) -> tuple[dict[str, list[str]], set[Field]]:
    """Literals whose containing fields are all absent from the query (paper step 2.d)."""
    missing, lit_fields = {}, set()
    for lit in extract_literals(sql):
        matches = lookup(db_id, lit, min_similarity=LITERAL_MATCH, top_k=5)
        holders = {(m.table.lower(), m.column.lower()) for m in matches}
        if holders and not holders & used:
            missing[lit] = [f"{m.table}.{m.column} (e.g. '{m.value}')" for m in matches]
            lit_fields |= holders
    return missing, lit_fields


def link(q: dict, *, model: str, hints: bool, variants: tuple[str, ...], k: int, max_retry: int,
         num_ctx: int, seed: int) -> LinkResult:
    db = q["db_id"]
    res = LinkResult(fields=set(), focused=focused_fields(q, hints, k))
    for name in variants:
        is_focused, metadata, detail = VARIANTS[name]
        cols = res.focused if is_focused else None
        msgs = messages(schema_text(db, metadata, detail, cols), q, hints)
        r = chat(msgs, model=model, num_ctx=num_ctx, seed=seed)
        res.calls.append(r)
        sql = extract_sql(r.text)
        used = extract_fields(sql, db)
        trace = LinkTrace(name, sql, sorted(f"{t}.{c}" for t, c in used))
        for _ in range(max_retry):
            missing, lit_fields = _missing_literals(db, sql, used)
            if not missing:
                break
            aug_cols = None if cols is None else cols | lit_fields
            aug = messages(schema_text(db, metadata, detail, aug_cols), q, hints)
            r = chat(aug + [{"role": "assistant", "content": f"```sql\n{sql}\n```"},
                            {"role": "user", "content": prompts.literal_revision(missing)}],
                     model=model, num_ctx=num_ctx, seed=seed)
            res.calls.append(r)
            sql = extract_sql(r.text)
            used = extract_fields(sql, db)
            trace.missing_literals, trace.revised_sql = missing, sql
            trace.fields = sorted(f"{t}.{c}" for t, c in used)
        res.fields |= used
        res.traces.append(trace)
    return res


@lru_cache(maxsize=1)
def _gold_sql() -> dict[int, str]:
    return {q["question_id"]: q["SQL"] for q in json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text())}


def oracle_fields(q: dict) -> set[Field]:
    """ORACLE: the fields the gold SQL uses (paper's 'perfect schema linking'). Upper bound only."""
    return extract_fields(_gold_sql()[int(q["question_id"])], q["db_id"])
