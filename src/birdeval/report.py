"""Turn a promptfoo JSON export into per-config numbers (accuracy with 95% CI, cost)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval: well-behaved for small n and accuracies near 0 or 1."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half, centre + half)


def load_results(path: str | Path) -> pd.DataFrame:
    """One row per (config, question)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for r in data["results"]["results"]:
        resp = r.get("response") or {}
        meta = resp.get("metadata") or {}
        usage = resp.get("tokenUsage") or {}
        named = r.get("namedScores") or {}
        rows.append({
            "config": r["provider"].get("label") or r["provider"]["id"],
            "question_id": int(r["vars"]["question_id"]),
            "db_id": r["vars"]["db_id"],
            "difficulty": r["vars"]["difficulty"],
            "ex": int(named.get("ex", 0)),
            "valid_sql": int(named.get("valid_sql", 0)),
            "provider_error": bool(r.get("error")) and not named,
            "prompt_tokens": usage.get("prompt", 0),
            "completion_tokens": usage.get("completion", 0),
            "llm_calls": meta.get("llm_calls", 0),
            "latency_ms": meta.get("latency_ms", 0),
            "link_recall": meta.get("link_recall"),
            "link_size": meta.get("link_size"),
            "vote_sqls": meta.get("vote_sqls"),
            "vote_winner": meta.get("vote_winner"),
            "vote_unanimous": meta.get("vote_unanimous"),
            "vote_distinct_sql": meta.get("vote_distinct_sql"),
            "check_fired": meta.get("check_fired"),
            "check_calls": meta.get("check_calls"),
            "check_changed": meta.get("check_changed"),
            "sql": resp.get("output", ""),
        })
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, order: list[str] | None = None) -> pd.DataFrame:
    """order: config labels in YAML order (promptfoo's result order is not guaranteed)."""
    out = []
    for config in order or list(dict.fromkeys(df["config"])):
        g = df[df["config"] == config]
        n, k = len(g), int(g["ex"].sum())
        lo, hi = wilson(k, n)
        out.append({
            "config": config,
            "n": n,
            "EX %": round(100 * k / n, 1),
            "95% CI": f"{100 * lo:.0f}–{100 * hi:.0f}",
            "valid SQL %": round(100 * g["valid_sql"].mean(), 1),
            "errors": int(g["provider_error"].sum()),
            "prompt tok/q": round(g["prompt_tokens"].mean()),
            "LLM calls/q": round(g["llm_calls"].mean(), 1),
            "sec/q": round(g["latency_ms"].mean() / 1000, 1),
            **({"link recall": round(g["link_recall"].mean(), 3), "linked cols/q": round(g["link_size"].mean(), 1)}
               if g["link_recall"].notna().any() else {}),
            **{f"EX {d}": round(100 * g[g["difficulty"] == d]["ex"].mean(), 1)
               for d in ("simple", "moderate", "challenging") if (g["difficulty"] == d).any()},
        })
    return pd.DataFrame(out)
