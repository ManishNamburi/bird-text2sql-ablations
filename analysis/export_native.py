"""Experiments 08 (D23) and 09's judge cells (D24) -> one row per (model, prompt, question).

Reads the full-config promptfoo export, the generation passes (token counts) and the
reproduction check written by scripts/run_native.py. Like the other committed CSVs it holds
no SQL and no judge reasons, only scores and flags.

Run:  uv run python analysis/export_native.py            (08, eval -> results/per_question_native.csv)
      uv run python analysis/export_native.py --split dev  (-> results/raw/, not committed)
      uv run python analysis/export_native.py --experiment 09_judge --split test
                                                          (-> results/per_question_native_5070.csv)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
METRICS = ["ex", "valid_sql", "is_sql_sqlite", "is_sql_mysql", "single_select", "judge"]
# llm-rubric's reasons when the grader's reply can't be read as a verdict (not a judgement).
GRADER_ERROR = re.compile(r"neither a pass verdict|could not extract json|failed to parse", re.IGNORECASE)


def load(split: str, experiment: str = "08_native") -> pd.DataFrame:
    rows = []
    for r in json.loads((RAW / f"{experiment}__{split}.json").read_text(encoding="utf-8"))["results"]["results"]:
        named = r.get("namedScores") or {}
        judge = next(c for c in r["gradingResult"]["componentResults"] if c["assertion"]["type"] == "llm-rubric")
        rows.append({
            "model": r["provider"]["label"],
            "prompt": r["prompt"]["label"],
            "question_id": int(r["vars"]["question_id"]),
            "db_id": r["vars"]["db_id"],
            "difficulty": r["vars"]["difficulty"],
            **{m: int(named.get(m, 0)) for m in METRICS if m != "judge"},
            # The judge's verdict. Its score can be fractional (e.g. 0.5 on a fail), so it is kept apart.
            "judge": int(judge["pass"]),
            "judge_score": judge.get("score"),
            "grader_error": int(not judge["pass"] and bool(GRADER_ERROR.search(judge.get("reason") or ""))),
            "provider_error": bool(r.get("error")) and not named,
        })
    df = pd.DataFrame(rows)
    # Token counts from the generation passes (the full pass replays them from promptfoo's cache).
    tok = []
    for model in df["model"].unique():
        for r in json.loads((RAW / f"{experiment}__{split}__gen_{model}.json").read_text(encoding="utf-8"))["results"]["results"]:
            u = (r.get("response") or {}).get("tokenUsage") or {}
            tok.append({"model": model, "prompt": r["prompt"]["label"], "question_id": int(r["vars"]["question_id"]),
                        "prompt_tokens": u.get("prompt", 0), "completion_tokens": u.get("completion", 0)})
    rep = pd.DataFrame(json.loads((RAW / f"{experiment}__{split}__repro.json").read_text(encoding="utf-8")))
    keys = ["model", "prompt", "question_id"]
    df = df.merge(pd.DataFrame(tok), on=keys, validate="1:1").merge(rep, on=keys, validate="1:1")
    if df["provider_error"].any():
        raise SystemExit(f"{int(df['provider_error'].sum())} provider errors")
    df["same_as_cached"] = df["same_as_cached"].astype(int)
    df["same_as_fresh"] = df["same_as_fresh"].map({True: 1, False: 0})  # NaN where it equals the cached row
    return df.drop(columns="provider_error").sort_values(keys, kind="stable").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "eval", "test"], default="eval")
    ap.add_argument("--experiment", choices=["08_native", "09_judge"], default="08_native")
    a = ap.parse_args()
    split = a.split
    df = load(split, a.experiment)
    committed = {("08_native", "eval"): "per_question_native.csv", ("09_judge", "test"): "per_question_native_5070.csv"}
    name = committed.get((a.experiment, split))
    stem = "per_question_native" if a.experiment == "08_native" else f"per_question_native__{a.experiment}"
    out = ROOT / "results" / name if name else RAW / f"{stem}__{split}.csv"  # 08 dev keeps its old name
    df.to_csv(out, index=False)
    print(f"-> {out.relative_to(ROOT)}: {len(df)} rows; grader errors {int(df['grader_error'].sum())}; "
          f"same SQL as cached custom row {int(df['same_as_cached'].sum())}/{len(df)}")
    print((100 * df.groupby(["prompt", "model"], sort=False)[METRICS].mean()).round(1).to_string())


if __name__ == "__main__":
    main()
