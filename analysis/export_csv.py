"""Merge the eval runs into one committed table: results/per_question.csv

results/raw/ (promptfoo JSON exports, ~100 MB) stays out of git. This CSV holds everything
the summary, figures and paired tests need, so they can be recomputed without models or data.

Test-split runs go to results/per_question_test.csv. Their eval questions are the same cached
calls as in the eval runs, so those rows must match the eval table and the script checks it.

A config that appears in several experiments (C4-linked is in 02-05) must give the same answer
everywhere: its rows are compared column by column and the script fails on any difference.
Latency is the exception: for voting configs it includes executing the candidates, which is
re-measured on every run, so the first experiment's value is kept.

Experiment 09 (D24), the RTX 5070 replication on the test split, goes to its own file,
results/per_question_5070.csv: another machine and another qwen3.5 build, so none of its rows
may join the Mac's tables (its labels all carry "@5070").

Run:  uv run python analysis/export_csv.py
      uv run python analysis/export_csv.py --only 09_replication   (the 5070 table alone; the Mac's
                                                                  raw exports aren't on that machine)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from birdeval.report import load_results

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ["01_metadata", "02_linking", "03_fewshot", "04_voting", "05_checks", "06_trimming", "07_coder"]
OUT = ROOT / "results" / "per_question.csv"
# Test-split runs (all 468 non-dev questions, a superset of eval): only T1 vs C3 so far.
TEST_RUNS = ["06_trimming"]
OUT_TEST = ROOT / "results" / "per_question_test.csv"
RUN_5070 = "09_replication"  # test split, 28 configs x 468 questions
OUT_5070 = ROOT / "results" / "per_question_5070.csv"
COLUMNS = ["config", "experiment", "question_id", "db_id", "difficulty", "ex", "valid_sql",
           "prompt_tokens", "completion_tokens", "llm_calls", "latency_ms", "link_recall"]
MUST_MATCH = ["ex", "valid_sql", "prompt_tokens", "completion_tokens", "llm_calls", "sql"]


def same(a: pd.Series, b: pd.Series) -> bool:
    return a.equals(b) or bool((a.isna() & b.isna() | (a == b)).all())


def export_test(kept: dict[str, pd.DataFrame]) -> None:
    frames = []
    for exp in TEST_RUNS:
        df = load_results(ROOT / "results" / "raw" / f"{exp}__test.json")
        if df["provider_error"].any():
            raise SystemExit(f"{exp}: provider errors in the test run")
        frames.append(df.assign(experiment=exp))
    test = pd.concat(frames)
    for config, g in test.groupby("config", sort=False):
        ev = kept[config]
        sub = g[g["question_id"].isin(ev["question_id"])].sort_values("question_id").reset_index(drop=True)
        if len(sub) != len(ev):
            raise SystemExit(f"{config}: test run covers {len(sub)} of the {len(ev)} eval questions")
        for col in MUST_MATCH:
            if not same(ev[col], sub[col]):
                raise SystemExit(f"{config}: column {col!r} differs between eval and test on eval questions")
        print(f"{config}: test run identical to eval on its {len(ev)} eval questions ({len(g)} test rows)")
    out = test.sort_values(["config", "question_id"], kind="stable")[COLUMNS]
    out["latency_ms"] = out["latency_ms"].round().astype(int)
    out.to_csv(OUT_TEST, index=False)
    print(f"-> {OUT_TEST.relative_to(ROOT)}: {len(out)} rows, {out['config'].nunique()} configs, "
          f"{out['question_id'].nunique()} questions")


def export_5070() -> None:
    df = load_results(ROOT / "results" / "raw" / f"{RUN_5070}__test.json").assign(experiment=RUN_5070)
    if df["provider_error"].any():
        raise SystemExit(f"{RUN_5070}: provider errors in the test run")
    if not df["config"].str.contains("@5070", regex=False).all():
        raise SystemExit(f"{RUN_5070}: a label without @5070 would join the Mac's tables")
    qs = df.groupby("config")["question_id"].apply(frozenset)
    if qs.nunique() != 1:
        raise SystemExit(f"{RUN_5070}: configs cover different question sets")
    out = df.sort_values(["config", "question_id"], kind="stable")[COLUMNS]
    out["latency_ms"] = out["latency_ms"].round().astype(int)
    out.to_csv(OUT_5070, index=False)
    print(f"-> {OUT_5070.relative_to(ROOT)}: {len(out)} rows, {out['config'].nunique()} configs, "
          f"{out['question_id'].nunique()} questions")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=[RUN_5070], help="export just this experiment's table")
    if ap.parse_args().only == RUN_5070:
        export_5070()
        return
    frames = []
    for exp in EXPERIMENTS:
        df = load_results(ROOT / "results" / "raw" / f"{exp}__eval.json")
        if df["provider_error"].any():
            raise SystemExit(f"{exp}: provider errors in the eval run")
        frames.append(df.assign(experiment=exp))

    kept: dict[str, pd.DataFrame] = {}
    for df in frames:
        for config, g in df.groupby("config", sort=False):
            g = g.sort_values("question_id").reset_index(drop=True)
            if config not in kept:
                kept[config] = g
                continue
            first = kept[config]
            for col in MUST_MATCH:
                if not same(first[col], g[col]):
                    raise SystemExit(f"{config}: column {col!r} differs between "
                                     f"{first['experiment'][0]} and {g['experiment'][0]}")
            print(f"{config}: identical in {first['experiment'][0]} and {g['experiment'][0]}")

    out = pd.concat(kept.values())[COLUMNS]
    out["latency_ms"] = out["latency_ms"].round().astype(int)
    out.to_csv(OUT, index=False)
    print(f"-> {OUT.relative_to(ROOT)}: {len(out)} rows, {out['config'].nunique()} configs, "
          f"{out['question_id'].nunique()} questions")
    export_test(kept)
    if (ROOT / "results" / "raw" / f"{RUN_5070}__test.json").exists():
        export_5070()


if __name__ == "__main__":
    main()
