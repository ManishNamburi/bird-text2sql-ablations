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

    out = ROOT / "results" / f"{a.results.stem}_analysis.md"
    out.write_text(
        f"# {a.results.stem}: paired analysis ({n_q} questions)\n\n"
        "## Accuracy and cost per config\n\n" + summary.to_markdown(index=False) + "\n\n"
        "## Paired comparisons\n\n"
        "`fixed` = questions only the second config gets right; `broke` = only the first. "
        "McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).\n\n"
        + comp.to_markdown(index=False) + "\n")
    print(summary.to_string(index=False), "\n")
    print(comp.to_string(index=False))
    print(f"\n-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
