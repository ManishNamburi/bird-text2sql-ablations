"""Headline results from the committed per-question table -> results/summary.md + docs/figures/

Reads only results/per_question.csv (built by analysis/export_csv.py), so every number here
can be recomputed without models, databases or promptfoo.

  - headline ladder C0 -> C1 -> C3 -> C4 -> C6 -> C7 (+ the C4-oracle upper bound), +/- hints:
    EX with Wilson 95% CI, delta vs the previous step (paired bootstrap CI, exact McNemar),
    cost, and the paper's GPT-4o number where the paper reports one
  - pairwise McNemar matrix over the ladder, Holm-adjusted for the number of tests
  - prompt trimming T1-T4 vs C3 with the pre-registered non-inferiority verdicts
  - T1 vs C3 on the 468-question test split (results/per_question_test.csv)
  - the headline configs on qwen2.5-coder:7b (labels ending in @coder): model gap, ladder, step x model
  - 09: the test-split replication on the RTX 5070 desktop (results/per_question_5070.csv and
    results/per_question_native_5070.csv): the pre-registered H1-H4, both ladders, 5070 vs Mac on eval
  - every eval config (cost and accuracy)
  - figures: the ladder, and cost vs accuracy with the Pareto frontier

Run:  uv run python analysis/summary.py
"""

from __future__ import annotations

import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.stats.contingency_tables import mcnemar  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

from birdeval.report import wilson  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "per_question.csv"
TEST_CSV = ROOT / "results" / "per_question_test.csv"  # T1 vs C3 on the test split only
CODER = "@coder"  # label suffix of the qwen2.5-coder:7b rerun (07); every other config is qwen3.5:9b
OUT = ROOT / "results" / "summary.md"
FIG = ROOT / "docs" / "figures"

# (label, short name, what changes vs the previous step)
LADDER = [
    ("C0-ddl", "C0", "DDL only"),
    ("C1-bird", "C1", "+ BIRD column descriptions"),
    ("C3-fused", "C3", "+ LLM profiling summaries (fused)"),
    ("C4-linked", "C4", "+ schema linking"),
    ("C6-vote", "C6", "+ 3 candidates, majority vote"),
    ("C7", "C7", "+ SQL sanity checks"),
]
ORACLE = ("C4-oracle", "Oracle", "gold SQL's columns only (upper bound)")
# Prompt trims (D21): each is one flag away from TRIM_BASE. (label, short name, what is removed)
TRIM_BASE = "C3-fused"
TRIMS = [
    ("T1-short-profile", "T1", "long → short profile summaries"),
    ("T2-masked-values", "T2", "example values in profile summaries masked"),
    ("T3-no-bird-values", "T3", "BIRD value descriptions dropped"),
    ("T4-minimal-system", "T4", "system prompt cut to one line"),
]
NONINFERIORITY_PP = -5.0  # pre-registered in tasks/todo.md before the eval run
# Paper (GPT-4o), from the PDF: Table 1 (metadata) and Table 2 (schema linking). (no hints, hints)
PAPER = {"C0-ddl": (49.8, None), "C1-bird": (59.6, 72.0), "C2-profile": (61.2, 72.6),
         "C3-fused": (63.2, 73.0), "C4-linked": (63.2, 73.0), "C4-oracle": (69.0, 77.4)}

# Reference palette (dataviz skill), light mode: categorical slots 1-2 + text/surface tokens.
SURFACE, TEXT, TEXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {False: ("#2a78d6", "No hints (realistic)"), True: ("#eb6834", "With BIRD hints")}


def lbl(config: str, hints: bool) -> str:
    return f"{config}+hints" if hints else config


def wide(df: pd.DataFrame, col: str = "ex") -> pd.DataFrame:
    return df.pivot_table(index="question_id", columns="config", values=col)


def paired(w: pd.DataFrame, a: str, b: str, n_boot: int = 10_000, seed: int = 0) -> dict:
    """b minus a. n_boot=0 skips the bootstrap CI (the McNemar matrix only needs p)."""
    x, y = w[a].to_numpy(), w[b].to_numpy()
    fixed, broke = int(((y == 1) & (x == 0)).sum()), int(((x == 1) & (y == 0)).sum())
    p = mcnemar([[0, broke], [fixed, 0]], exact=True).pvalue
    if n_boot == 0:
        return {"delta": 100 * (y.mean() - x.mean()), "fixed": fixed, "broke": broke, "p": float(p)}
    idx = np.random.default_rng(seed).integers(0, len(x), size=(n_boot, len(x)))
    lo, hi = np.percentile((y[idx] - x[idx]).mean(axis=1), [2.5, 97.5])
    return {"delta": 100 * (y.mean() - x.mean()), "lo": 100 * lo, "hi": 100 * hi,
            "fixed": fixed, "broke": broke, "p": float(p)}


def per_config(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for config, g in df.groupby("config", sort=False):
        n, k = len(g), int(g["ex"].sum())
        lo, hi = wilson(k, n)
        rows.append({"config": config, "experiment": g["experiment"].iloc[0], "n": n,
                     "ex": 100 * k / n, "lo": 100 * lo, "hi": 100 * hi,
                     "valid": 100 * g["valid_sql"].mean(), "tok": g["prompt_tokens"].mean(),
                     "calls": g["llm_calls"].mean(), "sec": g["latency_ms"].mean() / 1000})
    return pd.DataFrame(rows).set_index("config")


def fmt_p(p: float, eq: bool = False) -> str:
    """eq=True renders 'p = 0.015' / 'p < 0.001'; otherwise just the value."""
    if p < 0.001:
        return "p < 0.001" if eq else "<0.001"
    return f"p = {p:.3f}" if eq else f"{p:.3f}"


def ladder_table(stats: pd.DataFrame, w: pd.DataFrame, suffix: str = "") -> str:
    """suffix selects a model's labels: "" for qwen3.5:9b, CODER for qwen2.5-coder:7b."""
    head = ("| Step | What changes | EX no hints (95% CI) | Δ vs previous (95% CI), p | "
            "EX with hints (95% CI) | Δ vs previous (95% CI), p | Prompt tok/q | s/q | "
            "Paper, GPT-4o (no hints / hints) |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for i, (config, short, what) in enumerate([*LADDER, ORACLE]):
        cells = [f"**{short}**", what]
        for hints in (False, True):
            s = stats.loc[lbl(config + suffix, hints)]
            cells.append(f"{s.ex:.1f} ({s.lo:.0f}–{s.hi:.0f})")
            if 0 < i < len(LADDER):
                prev = lbl(LADDER[i - 1][0] + suffix, hints)
                r = paired(w, prev, lbl(config + suffix, hints))
                cells.append(f"{r['delta']:+.1f} ({r['lo']:+.1f} to {r['hi']:+.1f}), {fmt_p(r['p'], True)}")
            elif config == ORACLE[0]:
                r = paired(w, lbl("C4-linked" + suffix, hints), lbl(config + suffix, hints))
                cells.append(f"{r['delta']:+.1f} vs C4 ({r['lo']:+.1f} to {r['hi']:+.1f}), {fmt_p(r['p'], True)}")
            else:
                cells.append("—")
        s = stats.loc[config + suffix]
        paper = PAPER.get(config)
        cells += [f"{s.tok:,.0f}", f"{s.sec:.1f}",
                  " / ".join("—" if v is None else f"{v:.1f}" for v in paper) if paper else "not isolated"]
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def trimming_table(stats: pd.DataFrame, w: pd.DataFrame) -> str:
    """Each trim vs C3, both hint settings: paired Δ with bootstrap CI, McNemar p Holm-adjusted over
    all 2 × len(TRIMS) tests, and the pre-registered verdict."""
    tests = [(c, h) for c, _, _ in TRIMS for h in (False, True)]
    res = {t: paired(w, lbl(TRIM_BASE, t[1]), lbl(*t)) for t in tests}
    adj = dict(zip(tests, multipletests([res[t]["p"] for t in tests], method="holm")[1]))
    base = stats.loc[TRIM_BASE]
    head = ("| Trim | What is removed | Δ EX no hints (95% CI) | fixed / broke, Holm p | "
            "Δ EX with hints (95% CI) | fixed / broke, Holm p | Prompt tok/q (vs C3) | s/q | Verdict |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = [f"| **C3** | base: fused metadata, full schema | {base.ex:.1f} | — | "
             f"{stats.loc[lbl(TRIM_BASE, True)].ex:.1f} | — | {base.tok:,.0f} | {base.sec:.1f} | — |"]
    for config, short, what in TRIMS:
        cells = [f"**{short}**", what]
        for h in (False, True):
            r = res[(config, h)]
            cells += [f"{r['delta']:+.1f} ({r['lo']:+.1f} to {r['hi']:+.1f})",
                      f"{r['fixed']} / {r['broke']}, {fmt_p(adj[(config, h)], True)}"]
        s = stats.loc[config]
        cells += [f"{s.tok:,.0f} ({100 * (s.tok / base.tok - 1):+.0f}%)", f"{s.sec:.1f}",
                  verdict([res[(config, h)] for h in (False, True)], [adj[(config, h)] for h in (False, True)])]
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def verdict(results: list[dict], holm_ps: list[float]) -> str:
    """The pre-registered D21 rule over the no-hints and hints comparisons of one trim."""
    if any(p < 0.05 and r["delta"] < 0 for r, p in zip(results, holm_ps)):
        return "hurts"
    if all(r["lo"] > NONINFERIORITY_PP for r in results):
        return "safe to trim"
    return "inconclusive"


def t1_test_table(test: pd.DataFrame, eval_ids: set[int], trim: str = "T1-short-profile") -> str:
    """T1 vs C3 on the 468-question test split (verdict, Holm over its 2 tests), then the same
    comparison on the questions outside eval alone, as a secondary check without a verdict."""
    head = ("| Questions | n | C3 EX no hints / hints | T1 EX no hints / hints | Δ no hints (95% CI) | "
            "fixed / broke, p | Δ with hints (95% CI) | fixed / broke, p | Verdict |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for name, keep in [("all test", None), ("not in eval", lambda q: ~q.isin(eval_ids))]:
        df = test if keep is None else test[keep(test["question_id"])]
        w = wide(df)
        res = [paired(w, lbl(TRIM_BASE, h), lbl(trim, h)) for h in (False, True)]
        ps = [r["p"] for r in res]
        if keep is None:
            ps = list(multipletests(ps, method="holm")[1])
        cells = [name, str(len(w)),
                 " / ".join(f"{100 * w[lbl(TRIM_BASE, h)].mean():.1f}" for h in (False, True)),
                 " / ".join(f"{100 * w[lbl(trim, h)].mean():.1f}" for h in (False, True))]
        for r, p in zip(res, ps):
            cells += [f"{r['delta']:+.1f} ({r['lo']:+.1f} to {r['hi']:+.1f})",
                      f"{r['fixed']} / {r['broke']}, {fmt_p(p, True)}{' (Holm)' if keep is None else ''}"]
        cells.append(verdict(res, ps) if keep is None else "— (secondary)")
        lines.append("| " + " | ".join(cells) + " |")
    s = per_config(test)
    cost = (f"\nCost on all {test['question_id'].nunique()} test questions, no hints: C3 "
            f"{s.loc[TRIM_BASE].tok:,.0f} prompt tok/q, {s.loc[TRIM_BASE].sec:.1f} s/q; T1 {s.loc[trim].tok:,.0f} tok/q "
            f"({100 * (s.loc[trim].tok / s.loc[TRIM_BASE].tok - 1):+.0f}%), {s.loc[trim].sec:.1f} s/q. "
            f"Valid SQL: C3 {s.loc[TRIM_BASE].valid:.1f}%, T1 {s.loc[trim].valid:.1f}%.\n")
    return head + "\n".join(lines) + "\n" + cost


def mcnemar_matrix(w: pd.DataFrame, hints: bool, suffix: str = "") -> str:
    names = [(lbl(c + suffix, hints), s) for c, s, _ in [*LADDER, ORACLE]]
    pairs = list(itertools.combinations(range(len(names)), 2))
    res = [paired(w, names[i][0], names[j][0], n_boot=0) for i, j in pairs]
    adj = multipletests([r["p"] for r in res], method="holm")[1]
    cell = {}
    for (i, j), r, pa in zip(pairs, res, adj):
        mark = "**" if pa < 0.05 else ""
        cell[(i, j)] = f"{mark}{r['delta']:+.1f} ({fmt_p(pa)}){mark}"
    head = "| from ↓ / to → | " + " | ".join(s for _, s in names[1:]) + " |\n"
    head += "|---" * len(names) + "|\n"
    rows = []
    for i in range(len(names) - 1):
        rows.append(f"| **{names[i][1]}** | " + " | ".join(
            cell.get((i, j), "") for j in range(1, len(names))) + " |")
    return head + "\n".join(rows) + "\n"


def model_gap_table(stats: pd.DataFrame, w: pd.DataFrame) -> str:
    """Pre-registered primary test of the coder rerun: coder minus qwen3.5 per headline config,
    paired on the same questions, McNemar Holm-adjusted over all 2 × 7 configs."""
    configs = [*LADDER, ORACLE]
    tests = [(c, h) for c, _, _ in configs for h in (False, True)]
    res = {t: paired(w, lbl(t[0], t[1]), lbl(t[0] + CODER, t[1])) for t in tests}
    adj = dict(zip(tests, multipletests([res[t]["p"] for t in tests], method="holm")[1]))
    head = ("| Config | qwen3.5 / coder, no hints | Δ coder − qwen3.5 (95% CI), fixed / broke, Holm p | "
            "qwen3.5 / coder, with hints | Δ (95% CI), fixed / broke, Holm p | Coder valid SQL % | "
            "Coder tok/q | Coder s/q |\n|---|---|---|---|---|---|---|---|\n")
    lines = []
    for config, short, _ in configs:
        cells = [f"**{short}**"]
        for h in (False, True):
            r = res[(config, h)]
            cells += [f"{stats.loc[lbl(config, h)].ex:.1f} / {stats.loc[lbl(config + CODER, h)].ex:.1f}",
                      f"{r['delta']:+.1f} ({r['lo']:+.1f} to {r['hi']:+.1f}), {r['fixed']} / {r['broke']}, "
                      f"{fmt_p(adj[(config, h)], True)}"]
        s = stats.loc[config + CODER]
        cells += [f"{s.valid:.1f}", f"{s.tok:,.0f}", f"{s.sec:.1f}"]
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def step_by_model_table(w: pd.DataFrame, n_boot: int = 10_000, seed: int = 0) -> str:
    """Exploratory: does a step's gain depend on the model? Δstep(coder) − Δstep(qwen3.5), with a
    bootstrap CI that resamples questions jointly for all four configs involved."""
    steps = [(LADDER[i - 1][0], c, s) for i, (c, s, _) in enumerate(LADDER) if i > 0]
    steps.append(("C4-linked", ORACLE[0], "Oracle vs C4"))
    head = ("| Step | Δ qwen3.5 / Δ coder, no hints | difference (95% CI) | "
            "Δ qwen3.5 / Δ coder, with hints | difference (95% CI) |\n|---|---|---|---|---|\n")
    idx = np.random.default_rng(seed).integers(0, len(w), size=(n_boot, len(w)))
    lines = []
    for a, b, short in steps:
        cells = [f"**{short}**" if short.startswith("Oracle") else f"→ **{short}**"]
        for h in (False, True):
            dq = (w[lbl(b, h)] - w[lbl(a, h)]).to_numpy()
            dc = (w[lbl(b + CODER, h)] - w[lbl(a + CODER, h)]).to_numpy()
            lo, hi = np.percentile((dc - dq)[idx].mean(axis=1), [2.5, 97.5])
            cells += [f"{100 * dq.mean():+.1f} / {100 * dc.mean():+.1f}",
                      f"{100 * (dc - dq).mean():+.1f} ({100 * lo:+.1f} to {100 * hi:+.1f})"]
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def coder_section(df: pd.DataFrame) -> str:
    stats, w = per_config(df), wide(df)
    return (
        "\n## qwen2.5-coder:7b rerun of the headline configs (D22)\n\n"
        "Same pipeline, prompts, seeds and frozen eval split; only the model changes. The profile summaries and "
        "embeddings stay qwen3.5's. Analysis fixed before the run in `tasks/todo.md`.\n\n"
        "### Model gap per config (primary)\n\n"
        f"Δ = coder − qwen3.5 on the same {len(w)} questions, paired bootstrap CI; exact McNemar, Holm over the "
        f"{2 * (len(LADDER) + 1)} tests in this table. Cost columns are the no-hints config.\n\n"
        + model_gap_table(stats, w) +
        "\n### The ladder on qwen2.5-coder:7b\n\n" + ladder_table(stats, w, CODER) +
        "\n*Paper column: GPT-4o, as in the qwen3.5 ladder above.*\n\n"
        "#### Pairwise tests, Holm-adjusted (coder)\n\n"
        "No hints:\n\n" + mcnemar_matrix(w, False, CODER) + "\nWith hints:\n\n" + mcnemar_matrix(w, True, CODER) +
        "\n### Does a step's gain depend on the model? (exploratory)\n\n"
        "Difference = Δstep(coder) − Δstep(qwen3.5), bootstrap CI over questions. Expected to be wide; a CI that "
        "includes 0 means unknown, not equal.\n\n" + step_by_model_table(w))


NATIVE_CSV = ROOT / "results" / "per_question_native.csv"  # experiment 08 (D23)
NATIVE_CELLS = [("C1-native", "qwen3.5", "C1-bird"), ("C1-native+hints", "qwen3.5", "C1-bird+hints"),
                ("C1-native", "coder", "C1-bird@coder"), ("C1-native+hints", "coder", "C1-bird@coder+hints")]
CHEAP_CHECKS = [("is_sql_sqlite", "`is-sql`, `databaseType: Sqlite`"), ("is_sql_mysql", "`is-sql`, default (MySQL)"),
                ("single_select", "`javascript`: one SELECT/WITH statement")]


def _pct_ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f} ({100 * lo:.0f}–{100 * hi:.0f}), {k}/{n}" if n else "—"


def _kappa(a: np.ndarray, b: np.ndarray) -> float:
    po = (a == b).mean()
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def native_section(nat: pd.DataFrame, df: pd.DataFrame, n_boot: int = 10_000, seed: int = 0) -> str:
    """Experiment 08: promptfoo's native provider and built-in assertions, measured against EX (D23)."""
    w = wide(df)
    rows = ["| Prompt | Model | n | Same SQL as the custom provider's cached row | Of the rest: same as a fresh "
            "custom call | EX native / custom |", "|---|---|---|---|---|---|"]
    for prompt, model, custom in NATIVE_CELLS:
        g = nat[(nat["prompt"] == prompt) & (nat["model"] == model)]
        d = g[g["same_as_cached"] == 0]
        rows.append(f"| {prompt} | {model} | {len(g)} | {int(g['same_as_cached'].sum())} | "
                    f"{int(d['same_as_fresh'].sum())} of {len(d)} | {100 * g['ex'].mean():.1f} / "
                    f"{100 * w.loc[g['question_id'], custom].mean():.1f} |")
    repro = "\n".join(rows) + "\n"

    valid, ex = nat["valid_sql"].to_numpy(), nat["ex"].to_numpy()
    rows = ["| Check | Pass rate | Rejects SQL that executes (false reject) | Accepts SQL that fails to execute "
            "(false accept) | Pass rate when EX is wrong |", "|---|---|---|---|---|"]
    for col, name in CHEAP_CHECKS:
        c = nat[col].to_numpy()
        rows.append(f"| {name} | {_pct_ci(int(c.sum()), len(c))} | {_pct_ci(int((c[valid == 1] == 0).sum()), int(valid.sum()))} "
                    f"| {_pct_ci(int(c[valid == 0].sum()), int((valid == 0).sum()))} "
                    f"| {_pct_ci(int(c[ex == 0].sum()), int((ex == 0).sum()))} |")
    v = nat[nat["valid_sql"] == 1]
    only_mysql = int(((v["is_sql_mysql"] == 0) & (v["is_sql_sqlite"] == 1)).sum())
    only_sqlite = int(((v["is_sql_sqlite"] == 0) & (v["is_sql_mysql"] == 1)).sum())
    p = mcnemar([[0, only_sqlite], [only_mysql, 0]], exact=True).pvalue
    by_model = "; ".join(f"{m}: {_pct_ci(int((g['is_sql_mysql'] == 0).sum()), len(g))}"
                         for m, g in v.groupby("model", sort=False))
    checks = ("\n".join(rows) + f"\n\nOn SQL that executes, the MySQL default rejects {only_mysql} queries the SQLite "
              f"dialect accepts, and the reverse happens {only_sqlite} times (exact McNemar {fmt_p(p, True)}). "
              f"MySQL false-reject rate by model: {by_model}.\n")

    j = nat["judge"].to_numpy()
    rows = ["| Prompt | Model | EX % | Judge pass % | Judge − EX (pp) |", "|---|---|---|---|---|"]
    for prompt, model, _ in NATIVE_CELLS:
        g = nat[(nat["prompt"] == prompt) & (nat["model"] == model)]
        rows.append(f"| {prompt} | {model} | {100 * g['ex'].mean():.1f} | {100 * g['judge'].mean():.1f} | "
                    f"{100 * (g['judge'].mean() - g['ex'].mean()):+.1f} |")
    # Bootstrap over questions: each resample keeps all of a question's rows together.
    qids = nat["question_id"].unique()
    by_q = {q: i for i, q in enumerate(qids)}
    qi = nat["question_id"].map(by_q).to_numpy()
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(qi == i) for i in range(len(qids))]
    kappas, prefs = [], []
    is_qwen = (nat["model"] == "qwen3.5").to_numpy()
    gap = j - ex
    for _ in range(n_boot):
        rows_b = np.concatenate([groups[i] for i in rng.integers(0, len(qids), len(qids))])
        kappas.append(_kappa(j[rows_b], ex[rows_b]))
        b_q = is_qwen[rows_b]
        prefs.append(gap[rows_b][b_q].mean() - gap[rows_b][~b_q].mean())
    klo, khi = np.nanpercentile(kappas, [2.5, 97.5])
    plo, phi = np.percentile(prefs, [2.5, 97.5])
    pref = gap[is_qwen].mean() - gap[~is_qwen].mean()
    # The cell comparison an eval would act on: the effect of hints, as EX and as the judge measure it.
    wq = nat.pivot_table(index="question_id", columns=["model", "prompt"], values=["ex", "judge"])
    hint_rows = ["| Model | Hint effect by EX (pp) | Hint effect by the judge (pp) | Judge − EX (pp, 95% CI) |",
                 "|---|---|---|---|"]
    for model in ("qwen3.5", "coder"):
        d_ex, d_j = ((wq[m][model]["C1-native+hints"] - wq[m][model]["C1-native"]).to_numpy() for m in ("ex", "judge"))
        boot = [(d_j[b] - d_ex[b]).mean() for b in (rng.integers(0, len(d_ex), len(d_ex)) for _ in range(n_boot))]
        lo, hi = np.percentile(boot, [2.5, 97.5])
        hint_rows.append(f"| {model} | {100 * d_ex.mean():+.1f} | {100 * d_j.mean():+.1f} | "
                         f"{100 * (d_j - d_ex).mean():+.1f} ({100 * lo:+.1f} to {100 * hi:+.1f}) |")
    judge = ("\n".join(rows) + "\n\nThe effect of hints, as each metric measures it, paired by question (bootstrap CI). "
             "Not a pre-registered test: it puts a number on the ranking question above.\n\n" + "\n".join(hint_rows)
             + f"\n\nOver all {len(nat)} outputs: agreement with EX "
             f"{100 * (j == ex).mean():.1f}%, Cohen's κ = {_kappa(j, ex):.2f} ({klo:.2f} to {khi:.2f}). "
             f"Sensitivity (passes when EX is right): {_pct_ci(int(j[ex == 1].sum()), int(ex.sum()))}. "
             f"Specificity (fails when EX is wrong): {_pct_ci(int((j[ex == 0] == 0).sum()), int((ex == 0).sum()))}. "
             f"Grader errors (reply not readable as a verdict; counted as fails, as promptfoo does): "
             f"{int(nat['grader_error'].sum())}.\n\n"
             f"*Exploratory, self-preference:* (judge − EX) on qwen3.5's SQL minus the same on the coder's: "
             f"{100 * pref:+.1f} pp ({100 * plo:+.1f} to {100 * phi:+.1f}). The judge is qwen3.5:9b.\n")
    return (
        "\n## promptfoo-native evaluation (08, D23)\n\n"
        "C1 (BIRD descriptions, one call) on promptfoo's `ollama:chat` provider, as a prompts × providers matrix "
        "(C1 ± hints × qwen3.5:9b / qwen2.5-coder:7b), with promptfoo's built-in assertions scored next to EX. "
        f"Source: `{NATIVE_CSV.relative_to(ROOT).as_posix()}`. Analysis fixed before the run in `tasks/todo.md`.\n\n"
        "### 1. Does the native provider reproduce the custom provider?\n\n" + repro +
        "\n*A differing row is re-run through `birdeval.llm.chat` without its cache. qwen3.5 runs on Ollama's MLX "
        "runner, which doesn't reproduce every reply between runs (D23); the coder's llama.cpp runner does.*\n\n"
        "### 2. Cheap checks against execution\n\n"
        "Rates in %, with Wilson 95% CIs and counts; pooled over the 4 cells. \"Executes\" = `valid_sql`.\n\n"
        + checks +
        "\n### 3. The LLM judge (`llm-rubric`, reference-free) against EX\n\n"
        "The grader is qwen3.5:9b. It sees the question, BIRD's hint (in every cell, including the no-hints "
        "ones), the C1 schema and the SQL, never gold. κ CI: bootstrap over questions.\n\n" + judge)


# --- 09: test-split replication on the RTX 5070 desktop (D24) ------------------------------

CSV_5070 = ROOT / "results" / "per_question_5070.csv"
NATIVE_5070 = ROOT / "results" / "per_question_native_5070.csv"
Q5070, C5070 = "@5070", "@coder@5070"  # label suffixes: qwen3.5:9b (llama.cpp build) / qwen2.5-coder:7b
# Pre-registered in tasks/todo.md (09 spec) before any model call on the 5070: (name, hypothesis,
# predicted sign, eval estimate in pp). H1/H2 are qwen3.5.
HYPOTHESES = [
    ("H1a", "C7 > C1, no hints", +1, 8.7), ("H1b", "C7 > C1, with hints", +1, 8.0),
    ("H2a", "C4 > C3 (schema linking), no hints", +1, 4.7), ("H2b", "C4 > C3, with hints", +1, 3.3),
    ("H3", "hints help the coder less: mean over the 7 configs of Δhints(coder) − Δhints(qwen3.5) < 0", -1, -7.9),
    ("H4", "the judge overstates the coder's hint gain on C1: Δhints(judge) − Δhints(EX) > 0", +1, 8.7),
]


def _boot(x: np.ndarray, n_boot: int, seed: int) -> tuple[float, float, float]:
    """Mean of per-question values, percentile 95% CI and two-sided bootstrap p (floored at 1/n_boot)."""
    b = x[np.random.default_rng(seed).integers(0, len(x), size=(n_boot, len(x)))].mean(axis=1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    p = max(min(2 * min((b <= 0).mean(), (b >= 0).mean()), 1.0), 1 / n_boot)
    return 100 * lo, 100 * hi, float(p)


def hypothesis_tests(w: pd.DataFrame, nat: pd.DataFrame, qids: list[int], n_boot: int = 10_000,
                     seed: int = 0) -> list[dict]:
    """The 09 family on one question set. H1/H2: paired Δ, bootstrap CI, exact McNemar.
    H3/H4 are interactions (no McNemar): per-question contrast, bootstrap CI and p."""
    w = w.loc[qids]
    res = []
    for (a, b), h in [(("C1-bird", "C7"), False), (("C1-bird", "C7"), True),
                      (("C3-fused", "C4-linked"), False), (("C3-fused", "C4-linked"), True)]:
        res.append(paired(w, lbl(a + Q5070, h), lbl(b + Q5070, h), n_boot, seed))
    hint_gain = {m: np.mean([(w[lbl(c + m, True)] - w[lbl(c + m, False)]).to_numpy()
                             for c, _, _ in [*LADDER, ORACLE]], axis=0) for m in (Q5070, C5070)}
    for x in (hint_gain[C5070] - hint_gain[Q5070],
              (lambda g: (g["judge"]["C1-native+hints"] - g["judge"]["C1-native"])
               - (g["ex"]["C1-native+hints"] - g["ex"]["C1-native"]))(
                  nat[nat["model"] == "coder"].pivot_table(index="question_id", columns="prompt",
                                                            values=["ex", "judge"]).loc[qids]).to_numpy()):
        lo, hi, p = _boot(x, n_boot, seed)
        res.append({"delta": 100 * x.mean(), "lo": lo, "hi": hi, "p": p})
    adj = multipletests([r["p"] for r in res], method="holm")[1]
    for r, pa in zip(res, adj):
        r["holm"] = float(pa)
    return res


def _h_verdict(r: dict, sign: int) -> str:
    if r["holm"] < 0.05 and np.sign(r["delta"]) == sign:
        return "**supported**"
    if (sign > 0 and r["hi"] < 0) or (sign < 0 and r["lo"] > 0):
        return "**contradicted**"
    return "unknown"


def hypothesis_table(w: pd.DataFrame, nat: pd.DataFrame, fresh: list[int], all_q: list[int],
                     eval_q: list[int]) -> str:
    f, a, e = (hypothesis_tests(w, nat, q) for q in (fresh, all_q, eval_q))
    head = (f"| # | Hypothesis | Eval estimate (Mac) | 5070, the same {len(eval_q)} eval questions: Δ (95% CI) | "
            f"Fresh {len(fresh)}: Δ (95% CI) | fixed / broke, p, Holm p | Verdict | All {len(all_q)}: Δ (95% CI) | "
            "Holm p |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for (name, what, sign, est), rf, ra, re_ in zip(HYPOTHESES, f, a, e):
        test = (f"{rf['fixed']} / {rf['broke']}, {fmt_p(rf['p'], True)}" if "fixed" in rf
                else f"bootstrap {fmt_p(rf['p'], True)}") + f", Holm {fmt_p(rf['holm'])}"
        lines.append(f"| {name} | {what} | {est:+.1f} | {re_['delta']:+.1f} ({re_['lo']:+.1f} to {re_['hi']:+.1f}) | "
                     f"{rf['delta']:+.1f} ({rf['lo']:+.1f} to {rf['hi']:+.1f}) | "
                     f"{test} | {_h_verdict(rf, sign)} | {ra['delta']:+.1f} ({ra['lo']:+.1f} to {ra['hi']:+.1f}) | "
                     f"{fmt_p(ra['holm'])} |")
    return head + "\n".join(lines) + "\n"


def machine_gap_table(w9: pd.DataFrame, mac: pd.DataFrame) -> str:
    """Secondary, no verdict: 5070 − Mac on the 150 eval questions, per config. Different machine,
    runtime and qwen3.5 build (the coder's digest is the same), so not a model effect."""
    wm = wide(mac)
    w9 = w9.loc[wm.index]
    head = ("| Config | qwen3.5 no hints: 5070 / Mac, Δ (95% CI) | with hints | coder no hints | with hints |\n"
            "|---|---|---|---|---|\n")
    lines = []
    for config, short, _ in [*LADDER, ORACLE]:
        cells = [f"**{short}**"]
        for mac_sfx, sfx in (("", Q5070), (CODER, C5070)):
            for h in (False, True):
                x, y = wm[lbl(config + mac_sfx, h)], w9[lbl(config + sfx, h)]
                r = paired(pd.DataFrame({"mac": x, "pc": y}), "mac", "pc")
                cells.append(f"{100 * y.mean():.1f} / {100 * x.mean():.1f}, {r['delta']:+.1f} "
                             f"({r['lo']:+.1f} to {r['hi']:+.1f})")
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def judge_5070_table(nat: pd.DataFrame, w9: pd.DataFrame) -> str:
    custom = {("C1-native", "qwen3.5"): "C1-bird" + Q5070, ("C1-native+hints", "qwen3.5"): "C1-bird" + Q5070 + "+hints",
              ("C1-native", "coder"): "C1-bird" + C5070, ("C1-native+hints", "coder"): "C1-bird" + C5070 + "+hints"}
    rows = ["| Prompt | Model | n | Same SQL as the custom row | Of the rest: same as a fresh custom call | "
            "EX native / custom | Judge pass % | Grader errors |", "|---|---|---|---|---|---|---|---|"]
    for (prompt, model), label in custom.items():
        g = nat[(nat["prompt"] == prompt) & (nat["model"] == model)]
        d = g[g["same_as_cached"] == 0]
        rows.append(f"| {prompt} | {model} | {len(g)} | {int(g['same_as_cached'].sum())} | "
                    f"{int(d['same_as_fresh'].sum())} of {len(d)} | {100 * g['ex'].mean():.1f} / "
                    f"{100 * w9.loc[g['question_id'], label].mean():.1f} | {100 * g['judge'].mean():.1f} | "
                    f"{int(g['grader_error'].sum())} |")
    j, ex = nat["judge"].to_numpy(), nat["ex"].to_numpy()
    return ("\n".join(rows) + f"\n\nOver all {len(nat):,} outputs: judge agrees with EX on {100 * (j == ex).mean():.1f}%, "
            f"Cohen's κ = {_kappa(j, ex):.2f}. Sensitivity {_pct_ci(int(j[ex == 1].sum()), int(ex.sum()))}; "
            f"specificity {_pct_ci(int((j[ex == 0] == 0).sum()), int((ex == 0).sum()))}.\n")


def replication_section(d9: pd.DataFrame, nat: pd.DataFrame, mac: pd.DataFrame) -> str:
    eval_ids = set(mac["question_id"])
    all_q = sorted(d9["question_id"].unique())
    fresh = [q for q in all_q if q not in eval_ids]
    stats, w = per_config(d9), wide(d9)
    return (
        "\n## Test-split replication on the RTX 5070 desktop (09, D24)\n\n"
        f"The headline configs ± hints on both models, on all {len(all_q)} test questions, run on a Windows desktop "
        "(RTX 5070, Ollama 0.40.17 on llama.cpp). qwen3.5:9b is a different build from the Mac's (Q4_K_M, digest "
        "`56671c2ab938`, vs nvfp4 on MLX); qwen2.5-coder:7b is the same digest. Labels carry `@5070`, and nothing "
        f"here joins the Mac's rows. Source: `{CSV_5070.relative_to(ROOT).as_posix()}` and "
        f"`{NATIVE_5070.relative_to(ROOT).as_posix()}`. Hypotheses and rules fixed before the run in `tasks/todo.md`.\n\n"
        "### Pre-registered tests (confirmatory: the questions outside eval)\n\n"
        f"Every lead was chosen on the {len(eval_ids)} eval questions, so the verdict uses the {len(fresh)} test "
        "questions outside eval; all test questions are reported beside them. Holm over the 6 tests in each set. "
        "H1/H2: exact McNemar. H3/H4 are interactions, so their p is a two-sided paired bootstrap (10,000 "
        "resamples of questions). H4 uses the promptfoo-native C1 cells (their EX and the judge on the same rows). "
        "**Supported** = Holm p < 0.05 with the predicted sign; **contradicted** = the CI excludes 0 on the other "
        "side; anything else is unknown, not \"no effect\". The eval-questions column is the 5070's own run on the "
        "questions the leads were chosen on: descriptive, no test.\n\n"
        + hypothesis_table(w, nat, fresh, all_q, sorted(eval_ids & set(all_q))) +
        f"\n### The ladder on the 5070: qwen3.5:9b, all {len(all_q)} test questions\n\n"
        + ladder_table(stats, w, Q5070) +
        f"\n### The ladder on the 5070: qwen2.5-coder:7b, all {len(all_q)} test questions\n\n"
        + ladder_table(stats, w, C5070) +
        "\n*Per-step p values in the ladders are unadjusted and descriptive; the tests above carry the claims. "
        "Paper column: GPT-4o, as in the first ladder.*\n\n"
        f"### 5070 vs Mac on the {len(eval_ids)} eval questions (secondary)\n\n"
        "Same questions, prompts and seeds, different machine and runtime, and for qwen3.5 a different build. "
        "Paired bootstrap CI, no test or verdict: a gap here is a build-and-machine difference, not a model effect.\n\n"
        + machine_gap_table(w, mac) +
        "\n### The judge cells on the 5070 (promptfoo-native C1)\n\n"
        "A row that differs from the custom provider's cached SQL is re-run through `birdeval.llm.chat` without its "
        "cache. Grader errors (reply not readable as a verdict) count as fails, as promptfoo does.\n\n"
        + judge_5070_table(nat, w))


def all_configs_table(stats: pd.DataFrame) -> str:
    base = [c for c in stats.index if not c.endswith("+hints")]
    head = ("| Config | Experiment | EX no hints (95% CI) | EX with hints (95% CI) | Valid SQL % (no hints) | "
            "LLM calls/q | Prompt tok/q | s/q |\n|---|---|---|---|---|---|---|---|\n")
    lines = []
    for c in base:
        s, h = stats.loc[c], stats.loc[lbl(c, True)] if lbl(c, True) in stats.index else None
        lines.append(f"| {c} | {s.experiment} | {s.ex:.1f} ({s.lo:.0f}–{s.hi:.0f}) | "
                     + (f"{h.ex:.1f} ({h.lo:.0f}–{h.hi:.0f})" if h is not None else "—")
                     + f" | {s.valid:.1f} | {s.calls:.1f} | {s.tok:,.0f} | {s.sec:.1f} |")
    return head + "\n".join(lines) + "\n"


# --- figures ---------------------------------------------------------------------------

def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(TEXT2)
    ax.tick_params(colors=TEXT2, labelsize=10, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", facecolor=SURFACE, metadata={"Date": None})
    fig.savefig(FIG / f"{name}.png", facecolor=SURFACE, dpi=200, metadata={"Software": None})
    plt.close(fig)


def ladder_figure(stats: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=SURFACE)
    _style(ax)
    xs = np.arange(len(LADDER))
    for hints, dx in ((False, -0.09), (True, 0.09)):
        color, name = SERIES[hints]
        s = [stats.loc[lbl(c, hints)] for c, _, _ in LADDER]
        y = [r.ex for r in s]
        err = [[r.ex - r.lo for r in s], [r.hi - r.ex for r in s]]
        ax.errorbar(xs + dx, y, yerr=err, fmt="o", color=color, ecolor=color, elinewidth=2,
                    capsize=0, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, label=name, zorder=3)
        ax.plot(xs + dx, y, color=color, linewidth=2, alpha=0.35, zorder=2)
        o = stats.loc[lbl(ORACLE[0], hints)]
        ax.axhline(o.ex, color=color, linewidth=1.5, linestyle=(0, (4, 3)), zorder=1)
        ax.text(len(LADDER) - 1.5, o.ex + 0.6, f"oracle {o.ex:.1f}", color=TEXT2, fontsize=9,
                va="bottom", ha="center")  # in the gap between C6 and C7
        ax.text(xs[-1] + dx + 0.12, y[-1], f"{y[-1]:.1f}", color=TEXT, fontsize=10, va="center")
        ax.text(xs[0] + dx - 0.12, y[0], f"{y[0]:.1f}", color=TEXT, fontsize=10, va="center", ha="right")
    ticks = ["DDL only", "+ BIRD\ndescriptions", "+ profiling\n(fused)", "+ schema\nlinking",
             "+ 3-way\nvote", "+ SQL\nchecks"]
    ax.set_xticks(xs, [f"{s}\n{t}" for (_, s, _), t in zip(LADDER, ticks)], fontsize=9, color=TEXT2)
    ax.set_xlim(-0.6, len(LADDER) - 0.4)
    ax.set_ylim(0, 80)
    ax.set_ylabel("Execution accuracy, % (95% CI)", color=TEXT2, fontsize=10)
    ax.set_title("Each step of the paper's pipeline, qwen3.5:9b on 150 BIRD MiniDev questions\n"
                 "dashed: oracle linking (the gold SQL's columns), an upper bound",
                 loc="left", color=TEXT, fontsize=12, pad=12)
    ax.legend(loc="lower right", frameon=False, fontsize=10, labelcolor=TEXT)
    fig.tight_layout()
    _save(fig, "ladder")


def _short(config: str) -> str:
    if config.startswith("T") and config[1].isdigit():
        return config[:2]
    for suffix in ("+hints", "-linked", "-fused", "-bird", "-ddl", "-profile"):
        config = config.replace(suffix, "")
    return config


# Label offsets (points) where frontier points crowd each other around 40-50 s.
_OFFSETS = {"C4": (-24, -4), "C2": (-18, -14), "C3": (4, 6), "C4-checked": (-62, 6), "C7": (6, -4), "C6-vote": (6, -12),
            "C6-shuffle": (-58, 4), "T1": (-22, 6)}


def pareto_figure(stats: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=SURFACE)
    for ax, hints in zip(axes, (False, True)):
        _style(ax)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        color, name = SERIES[hints]
        s = stats[[c.endswith("+hints") == hints for c in stats.index]].sort_values("sec")
        oracle = s[s.index.str.startswith(ORACLE[0])]
        s = s.drop(oracle.index)  # not deployable: it reads the gold SQL, so it stays off the frontier
        best, front = -1.0, []
        for c, r in s.iterrows():  # Pareto frontier: nothing cheaper is at least as accurate
            if r.ex > best:
                front.append((c, r))
                best = r.ex
        ax.step([r.sec for _, r in front], [r.ex for _, r in front], where="post", color=color,
                linewidth=2, alpha=0.5, zorder=2)
        ax.scatter(s.sec, s.ex, s=64, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter(oracle.sec, oracle.ex, s=64, facecolor=SURFACE, edgecolor=color, linewidth=2, zorder=3)
        ax.annotate("oracle linking\n(upper bound)", (oracle.sec.iloc[0], oracle.ex.iloc[0]), xytext=(8, 0),
                    textcoords="offset points", fontsize=9, color=TEXT2, va="center")
        for c, r in front:
            ax.annotate(_short(c), (r.sec, r.ex), xytext=_OFFSETS.get(_short(c), (6, -12)),
                        textcoords="offset points", fontsize=9, color=TEXT)
        ax.set_xscale("log")
        ax.set_xticks([3, 5, 10, 20, 40, 60], ["3", "5", "10", "20", "40", "60"])
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel("Seconds per question (log scale)", color=TEXT2, fontsize=10)
        ax.set_title(name, loc="left", color=TEXT, fontsize=11)
    axes[0].set_ylabel("Execution accuracy, %", color=TEXT2, fontsize=10)
    fig.suptitle("Cost vs accuracy for every eval config. Line = Pareto frontier (labelled); "
                 "dots below it cost more for less", x=0.01, ha="left", color=TEXT, fontsize=12)
    fig.tight_layout()
    _save(fig, "pareto")


def main() -> None:
    full = pd.read_csv(CSV)
    df = full[~full["config"].str.contains(CODER, regex=False)]  # the qwen3.5 sections and figures
    stats, w = per_config(df), wide(df)
    n_q = df["question_id"].nunique()
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "birdeval", "svg.fonttype": "none"})
    ladder_figure(stats)
    pareto_figure(stats)
    OUT.write_text(
        f"# Summary: {n_q} eval questions, qwen3.5:9b\n\n"
        "Generated by `analysis/summary.py` from `results/per_question.csv`. Do not edit by hand.\n"
        "EX = BIRD execution accuracy. CIs: Wilson for accuracies, paired bootstrap (10,000 resamples of "
        "questions) for differences. p: exact McNemar on the questions where the two configs disagree.\n\n"
        "## The ladder (each step changes one thing)\n\n" + ladder_table(stats, w) +
        "\n*Paper numbers are GPT-4o with the paper's full pipeline (its Tables 1–2), for shape only. "
        "C4 maps to its Table 2 \"our schema linking\" row, the oracle to \"perfect schema linking\". "
        "The paper doesn't isolate voting or the SQL checks. Note the paper's own full-schema fused number differs "
        "between Table 1 (63.2 / 73.0) and Table 2 (61.2 / 71.2).*\n\n"
        "## Pairwise tests over the ladder, Holm-adjusted\n\n"
        "Cell = Δ EX in pp (column minus row), with the Holm-adjusted McNemar p over all "
        f"{len(LADDER) + 1} × {len(LADDER)} / 2 = {(len(LADDER) + 1) * len(LADDER) // 2} pairs in that table. "
        "**Bold** = significant after adjustment.\n\n"
        "### No hints\n\n" + mcnemar_matrix(w, False) + "\n### With hints\n\n" + mcnemar_matrix(w, True) +
        "\n## Prompt trimming on C3 (T1–T4, D21)\n\n"
        "Each trim removes one prompt section from C3 (fused metadata, full schema, one call). "
        f"Holm adjustment over the {2 * len(TRIMS)} tests in this table. Verdicts were fixed before the eval run: "
        f"**safe to trim** = the 95% CI lower bound of Δ is above {NONINFERIORITY_PP:.0f} pp with and without hints; "
        "**hurts** = Holm p < 0.05 with Δ < 0; otherwise **inconclusive**. Token and time columns are the no-hints "
        "config.\n\n" + trimming_table(stats, w) +
        "\n## T1 on the 468-question test split\n\n"
        "Test = every non-dev question, so it contains the 150 eval questions above (their answers are the same "
        "cached calls). Same pre-registered rule, Holm over the 2 tests in the first row. The second row repeats "
        "the comparison on the questions outside eval only; it is a secondary check and gets no verdict. "
        f"Source: `{TEST_CSV.relative_to(ROOT).as_posix()}`.\n\n"
        + t1_test_table(pd.read_csv(TEST_CSV), set(df["question_id"])) +
        (coder_section(full) if len(df) < len(full) else "") +
        (native_section(pd.read_csv(NATIVE_CSV), full) if NATIVE_CSV.exists() else "") +
        (replication_section(pd.read_csv(CSV_5070), pd.read_csv(NATIVE_5070), full)
         if CSV_5070.exists() and NATIVE_5070.exists() else "") +
        "\n## Every eval config (qwen3.5:9b)\n\n" + all_configs_table(stats) +
        "\n![ladder](../docs/figures/ladder.png)\n\n![pareto](../docs/figures/pareto.png)\n", encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}, {FIG.relative_to(ROOT)}/ladder.*, pareto.*")


if __name__ == "__main__":
    main()
