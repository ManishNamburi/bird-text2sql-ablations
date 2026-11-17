"""Headline results from the committed per-question table -> results/summary.md + docs/figures/

Reads only results/per_question.csv (built by analysis/export_csv.py), so every number here
can be recomputed without models, databases or promptfoo.

  - headline ladder C0 -> C1 -> C3 -> C4 -> C6 -> C7 (+ the C4-oracle upper bound), +/- hints:
    EX with Wilson 95% CI, delta vs the previous step (paired bootstrap CI, exact McNemar),
    cost, and the paper's GPT-4o number where the paper reports one
  - pairwise McNemar matrix over the ladder, Holm-adjusted for the number of tests
  - prompt trimming T1-T4 vs C3 with the pre-registered non-inferiority verdicts
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


def ladder_table(stats: pd.DataFrame, w: pd.DataFrame) -> str:
    head = ("| Step | What changes | EX no hints (95% CI) | Δ vs previous (95% CI), p | "
            "EX with hints (95% CI) | Δ vs previous (95% CI), p | Prompt tok/q | s/q | "
            "Paper, GPT-4o (no hints / hints) |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for i, (config, short, what) in enumerate([*LADDER, ORACLE]):
        cells = [f"**{short}**", what]
        for hints in (False, True):
            s = stats.loc[lbl(config, hints)]
            cells.append(f"{s.ex:.1f} ({s.lo:.0f}–{s.hi:.0f})")
            if 0 < i < len(LADDER):
                prev = lbl(LADDER[i - 1][0], hints)
                r = paired(w, prev, lbl(config, hints))
                cells.append(f"{r['delta']:+.1f} ({r['lo']:+.1f} to {r['hi']:+.1f}), {fmt_p(r['p'], True)}")
            elif config == ORACLE[0]:
                r = paired(w, lbl("C4-linked", hints), lbl(config, hints))
                cells.append(f"{r['delta']:+.1f} vs C4 ({r['lo']:+.1f} to {r['hi']:+.1f}), {fmt_p(r['p'], True)}")
            else:
                cells.append("—")
        s = stats.loc[config]
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
        rs = [res[(config, h)] for h in (False, True)]
        if any(adj[(config, h)] < 0.05 and res[(config, h)]["delta"] < 0 for h in (False, True)):
            verdict = "hurts"
        elif all(r["lo"] > NONINFERIORITY_PP for r in rs):
            verdict = "safe to trim"
        else:
            verdict = "inconclusive"
        cells += [f"{s.tok:,.0f} ({100 * (s.tok / base.tok - 1):+.0f}%)", f"{s.sec:.1f}", verdict]
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def mcnemar_matrix(w: pd.DataFrame, hints: bool) -> str:
    names = [(lbl(c, hints), s) for c, s, _ in [*LADDER, ORACLE]]
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
    df = pd.read_csv(CSV)
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
        "\n## Every eval config\n\n" + all_configs_table(stats) +
        "\n![ladder](../docs/figures/ladder.png)\n\n![pareto](../docs/figures/pareto.png)\n")
    print(f"-> {OUT.relative_to(ROOT)}, {FIG.relative_to(ROOT)}/ladder.*, pareto.*")


if __name__ == "__main__":
    main()
