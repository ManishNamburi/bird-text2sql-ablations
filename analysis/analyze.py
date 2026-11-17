"""Paired analysis of one experiment run -> results/<experiment>__<split>_analysis.md

Every config answers the SAME questions, so comparisons are paired:
  - McNemar exact test on discordant questions (A right / B wrong vs A wrong / B right)
  - paired bootstrap 95% CI for the accuracy difference (resampling questions)
Paired tests detect much smaller differences than comparing two independent CIs.

Comparisons: consecutive configs in YAML order within each hints group, each config vs its
"+hints" twin, plus any extra --pairs "A>B,C>D" (B minus A is reported).

Run:  uv run python analysis/analyze.py results/raw/01_metadata__eval.json [--pairs "C1-bird>C3-fused"]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from statsmodels.stats.contingency_tables import mcnemar

from birdeval.report import load_results, summarize

ROOT = Path(__file__).resolve().parents[1]


def paired(df, a: str, b: str, n_boot: int = 10_000, seed: int = 0) -> dict:
    wide = df.pivot_table(index="question_id", columns="config", values="ex")
    x, y = wide[a].to_numpy(), wide[b].to_numpy()
    b_only, a_only = int(((y == 1) & (x == 0)).sum()), int(((x == 1) & (y == 0)).sum())
    p = mcnemar([[0, a_only], [b_only, 0]], exact=True).pvalue
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    diffs = (y[idx] - x[idx]).mean(axis=1)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"from": a, "to": b, "Δ EX (pp)": round(100 * (y.mean() - x.mean()), 1),
            "95% CI (pp)": f"{100 * lo:+.1f} to {100 * hi:+.1f}",
            "fixed": b_only, "broke": a_only, "McNemar p": round(float(p), 4),
            "sig@0.05": "yes" if p < 0.05 else "no"}


def voting_table(df, labels: list[str]):
    """C6 diagnostics. pass@k = any candidate is correct: the ceiling for a perfect selector
    (uses gold rows, so analysis-only - selection itself never sees them)."""
    import pandas as pd

    from birdeval.sqlexec import score_question

    rows = []
    for config in labels:
        g = df[(df["config"] == config) & df["vote_sqls"].notna()]
        if g.empty:
            continue
        k = len(g["vote_sqls"].iloc[0])
        cand_ok = [[score_question(r.question_id, r.db_id, s).match for s in r.vote_sqls]
                   for r in g.itertuples()]
        rows.append({
            "config": config,
            "EX % (voted)": round(100 * g["ex"].mean(), 1),
            "EX % candidate 0 (= parent)": round(100 * sum(c[0] for c in cand_ok) / len(g), 1),
            **{f"EX % candidate {i}": round(100 * sum(c[i] for c in cand_ok) / len(g), 1) for i in range(1, k)},
            f"pass@{k} %": round(100 * sum(any(c) for c in cand_ok) / len(g), 1),
            "unanimous %": round(100 * g["vote_unanimous"].mean(), 1),
            "winner ≠ candidate 0 %": round(100 * (g["vote_winner"] != 0).mean(), 1),
            "distinct SQL/q": round(g["vote_distinct_sql"].mean(), 2),
        })
    return pd.DataFrame(rows) if rows else None


def checks_table(df, labels: list[str]):
    """C7 diagnostics, per checked config and check type, against the previous config in YAML
    order (its parent: C4-checked <- C4-linked, C7 <- C6-vote). On the questions where a check
    fired: how often a correction changed the SQL, and EX fixed / broke vs the parent."""
    import pandas as pd

    from birdeval.sqlchecks import CHECKS

    wide = df.pivot_table(index="question_id", columns="config", values="ex")
    rows = []
    for i, config in enumerate(labels):
        g = df[(df["config"] == config) & df["check_fired"].notna()]
        if g.empty or i == 0:
            continue
        parent = labels[i - 1]
        for check in (*CHECKS, "any"):
            hit = g[g["check_fired"].map(lambda f: bool(f) if check == "any" else check in f)]
            qids = hit["question_id"]
            x, y = wide.loc[qids, parent], wide.loc[qids, config]
            rows.append({"config": config, "parent": parent, "check": check,
                         "questions fired": len(hit), "SQL changed": int(hit["check_changed"].sum()),
                         "correction calls": int(hit["check_calls"].sum()),
                         "fixed": int(((y == 1) & (x == 0)).sum()), "broke": int(((x == 1) & (y == 0)).sum())})
    return pd.DataFrame(rows) if rows else None


def default_pairs(labels: list[str]) -> list[tuple[str, str]]:
    base = [lbl for lbl in labels if not lbl.endswith("+hints")]
    hinted = [lbl for lbl in labels if lbl.endswith("+hints")]
    pairs = list(zip(base, base[1:])) + list(zip(hinted, hinted[1:]))
    pairs += [(lbl, f"{lbl}+hints") for lbl in base if f"{lbl}+hints" in labels]
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", type=Path)
    ap.add_argument("--pairs", default="", help='extra comparisons, e.g. "C1-bird>C3-fused,C0-ddl>C2-profile"')
    a = ap.parse_args()

    df = load_results(a.results)
    labels = list(dict.fromkeys(df["config"]))
    import yaml  # config order is the source of truth for label order

    stem = a.results.stem.split("__")[0]
    cfg_path = ROOT / "promptfoo" / "configs" / f"{stem}.yaml"
    if cfg_path.exists():
        order = [p["label"] for p in yaml.safe_load(cfg_path.read_text())["providers"]]
        labels = [lbl for lbl in order if lbl in labels]

    pairs = default_pairs(labels) + [tuple(p.split(">")) for p in a.pairs.split(",") if p]
    import pandas as pd

    comp = pd.DataFrame([paired(df, x, y) for x, y in pairs])
    summary = summarize(df, order=labels)
    n_q = df["question_id"].nunique()
    votes = voting_table(df, labels)
    chk = checks_table(df, labels)
    chk_md = ("## SQL-check diagnostics\n\nPer check, on the questions where it fired in any candidate. "
              "`fixed` / `broke` are EX against the parent config on those questions.\n\n"
              + chk.to_markdown(index=False) + "\n\n") if chk is not None else ""
    vote_md = ("## Voting diagnostics\n\n`pass@k` = any candidate correct (perfect-selector ceiling). "
               "`unanimous` = all candidates executed and returned the same rows.\n\n"
               + votes.to_markdown(index=False) + "\n\n") if votes is not None else ""

    out = ROOT / "results" / f"{a.results.stem}_analysis.md"
    out.write_text(
        f"# {a.results.stem}: paired analysis ({n_q} questions)\n\n"
        "## Accuracy and cost per config\n\n" + summary.to_markdown(index=False) + "\n\n"
        + vote_md + chk_md + "## Paired comparisons\n\n"
        "`fixed` = questions only the second config gets right; `broke` = only the first. "
        "McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).\n\n"
        + comp.to_markdown(index=False) + "\n")
    print(summary.to_string(index=False), "\n")
    if votes is not None:
        print(votes.to_string(index=False), "\n")
    if chk is not None:
        print(chk.to_string(index=False), "\n")
    print(comp.to_string(index=False))
    print(f"\n-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
