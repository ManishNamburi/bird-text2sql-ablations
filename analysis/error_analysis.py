"""Error analysis of the headline config (C7, no hints) on eval.

1. Automatic taxonomy of EVERY failure, from executing the prediction against the cached gold rows:
     invalid SQL | empty result | wrong row count | right row count, wrong values
   crossed with whether schema linking dropped a column the gold SQL needs (link_recall < 1).
2. A fixed random sample of 20 failures (seed 42), dumped with question, hint, both SQLs and the
   first rows of both results, for a manual read. The manual tags live in docs/error_analysis.md.

Needs results/raw/05_checks__eval.json (not committed) and the MiniDev data.
Run:  uv run python analysis/error_analysis.py [--dump path]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from birdeval.report import load_results
from birdeval.sqlexec import DATA_ROOT, execute, load_gold, timeout_for

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "05_checks__eval.json"
CONFIG = "C7"
N_SAMPLE, SEED = 20, 42


def classify(row) -> tuple[str, list | None]:
    gold = load_gold()[row.question_id]["rows"]
    r = execute(row.db_id, row.sql, timeout_for(row.question_id))
    if not r.ok:
        return "invalid SQL", None
    if not r.rows and gold:
        return "empty result", r.rows
    if len(set(r.rows)) != len(set(gold)):
        return "wrong row count", r.rows
    return "right row count, wrong values", r.rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, help="write the 20 sampled cases here for reading")
    a = ap.parse_args()

    df = load_results(RAW)
    fails = df[(df["config"] == CONFIG) & (df["ex"] == 0)].sort_values("question_id").copy()
    n_all = int((df["config"] == CONFIG).sum())
    results = [classify(r) for r in fails.itertuples()]
    fails["category"] = [c for c, _ in results]
    fails["pred_rows"] = [rows for _, rows in results]
    fails["linking dropped a needed column"] = fails["link_recall"] < 1

    table = pd.crosstab(fails["category"], fails["linking dropped a needed column"], margins=True,
                        margins_name="total")
    print(f"{CONFIG}: {len(fails)} failures of {n_all}\n")
    print(table.to_markdown(), "\n")
    print(pd.crosstab(fails["difficulty"], fails["category"]).to_markdown())

    if a.dump:
        qs = {q["question_id"]: q for q in json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text(encoding="utf-8"))}
        sample = fails.sample(N_SAMPLE, random_state=SEED).sort_values("question_id")
        out = []
        for r in sample.itertuples():
            q = qs[r.question_id]
            out.append(
                f"## qid {r.question_id} · {r.db_id} · {r.difficulty} · {r.category} · link_recall {r.link_recall}\n"
                f"Q: {q['question']}\nHint (not shown to C7): {q['evidence']}\n"
                f"PRED: {r.sql}\nGOLD: {q['SQL']}\n"
                f"PRED rows: {(r.pred_rows or [])[:5]!r}\nGOLD rows: {load_gold()[r.question_id]['rows'][:5]!r}\n")
        a.dump.write_text("\n".join(out), encoding="utf-8")
        print(f"\n-> {a.dump} ({len(out)} cases: qids {sorted(sample['question_id'])})")


if __name__ == "__main__":
    main()
