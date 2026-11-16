"""LLM-summarize every column profile into a SHORT and a LONG description (paper §2.1).

  short: what the column means + value format     (paper: used for schema linking)
  long:  meaning + exact literal formats + gotchas (paper: used for SQL generation)

Inputs per column: table name, the other column names in the table, column name, declared
type, and the English profile. Deliberately NOT the BIRD SME descriptions, so that C2
("profiling metadata") measures purely automatic metadata (see docs/decisions.md D11).

Output: data/derived/summaries/<db>.json  {"table.column": {"short", "long"}}
Resumable: every LLM call is disk-cached, so a rerun only pays for missing columns.

Run:  uv run python scripts/summarize_profiles.py [--limit N] [db_id ...]
"""

import argparse
import json
import time

from birdeval.llm import DEFAULT_MODEL, chat
from birdeval.profiling import DERIVED, load_profiles
from birdeval.sqlexec import DB_ROOT

SYSTEM = "You document database columns for analysts who write SQL queries. Be precise and factual; never invent values."

INSTRUCTIONS = """Using the profile, describe this column.
- "short": one sentence: what the column means and the format of its values.
- "long": at most 60 words: what the column means; the exact format of stored values, quoting real example literals from the profile; and anything a SQL writer must know (NULLs, sentinel or placeholder values, numbers stored as text, mixed formats, codes and what they likely stand for).
State only facts supported by the profile. No generic advice.
Reply with JSON only: {"short": "...", "long": "..."}"""

SCHEMA = {
    "type": "object",
    "properties": {"short": {"type": "string"}, "long": {"type": "string"}},
    "required": ["short", "long"],
}


def summarize(profile: dict, sibling_columns: list[str], model: str) -> tuple[dict, object]:
    others = ", ".join(c for c in sibling_columns if c != profile["column"])
    user = (f"Table: {profile['table']}\nOther columns in this table: {others}\n"
            f"Column: {profile['column']} (declared type: {profile['declared_type'] or 'none'})\n"
            f"Profile: {profile['english']}\n\n{INSTRUCTIONS}")
    r = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
             model=model, format=SCHEMA, num_predict=400)
    out = json.loads(r.text)
    return {"short": out["short"].strip(), "long": out["long"].strip()}, r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dbs", nargs="*")
    ap.add_argument("--limit", type=int, help="only the first N columns per DB (for trials)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    dbs = a.dbs or sorted(p.name for p in DB_ROOT.iterdir() if p.is_dir())

    t_all, n_all = time.time(), 0
    for db in dbs:
        profiles = load_profiles(db)[: a.limit]
        by_table: dict[str, list[str]] = {}
        for p in load_profiles(db):
            by_table.setdefault(p["table"], []).append(p["column"])
        summaries, t0, new = {}, time.time(), 0
        for p in profiles:
            s, r = summarize(p, by_table[p["table"]], a.model)
            summaries[f"{p['table']}.{p['column']}"] = s
            new += not r.cached
        n_all += len(profiles)
        if a.limit is None:
            path = DERIVED / "summaries" / f"{db}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(summaries, indent=1, ensure_ascii=False))
        rate = (time.time() - t0) / max(new, 1)
        print(f"{db:26s} {len(profiles):4d} columns ({new} new, {rate:.1f}s/new call)", flush=True)
        if a.limit is not None:
            for k, v in summaries.items():
                print(f"  [{k}]\n    SHORT: {v['short']}\n    LONG:  {v['long']}")
    print(f"total {n_all} columns in {(time.time() - t_all) / 60:.1f} min")


if __name__ == "__main__":
    main()
