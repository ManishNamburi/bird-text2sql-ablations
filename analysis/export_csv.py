"""Merge the eval runs into one committed table: results/per_question.csv

results/raw/ (promptfoo JSON exports, ~100 MB) stays out of git. This CSV holds everything
the summary, figures and paired tests need, so they can be recomputed without models or data.

A config that appears in several experiments (C4-linked is in 02-05) must give the same answer
everywhere: its rows are compared column by column and the script fails on any difference.
Latency is the exception: for voting configs it includes executing the candidates, which is
re-measured on every run, so the first experiment's value is kept.

Run:  uv run python analysis/export_csv.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from birdeval.report import load_results

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ["01_metadata", "02_linking", "03_fewshot", "04_voting", "05_checks", "06_trimming"]
OUT = ROOT / "results" / "per_question.csv"
COLUMNS = ["config", "experiment", "question_id", "db_id", "difficulty", "ex", "valid_sql",
           "prompt_tokens", "completion_tokens", "llm_calls", "latency_ms", "link_recall"]
MUST_MATCH = ["ex", "valid_sql", "prompt_tokens", "completion_tokens", "llm_calls", "sql"]


def main() -> None:
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
                a, b = first[col], g[col]
                if not (a.equals(b) or (a.isna() & b.isna() | (a == b)).all()):
                    raise SystemExit(f"{config}: column {col!r} differs between "
                                     f"{first['experiment'][0]} and {g['experiment'][0]}")
            print(f"{config}: identical in {first['experiment'][0]} and {g['experiment'][0]}")

    out = pd.concat(kept.values())[COLUMNS]
    out["latency_ms"] = out["latency_ms"].round().astype(int)
    out.to_csv(OUT, index=False)
    print(f"-> {OUT.relative_to(ROOT)}: {len(out)} rows, {out['config'].nunique()} configs, "
          f"{out['question_id'].nunique()} questions")


if __name__ == "__main__":
    main()
