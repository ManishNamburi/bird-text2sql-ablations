"""Run experiment 08 (promptfoo-native, D23) on a frozen split.

    uv run python scripts/run_native.py --split dev

promptfoo runs every provider on a test before the next test, and the two local models
don't fit in memory together, so one combined pass would reload a model on every call.
Three passes instead, with promptfoo's own response cache on:
  1-2. Generation, one model at a time (--filter-providers), with `--grader echo` so the
       llm-rubric judge makes no model call. Each writes its own JSON: these hold the
       original call timings (a cache hit reports ~0 ms).
  3.   The whole config: generation is all cache hits, and only the judge calls Ollama,
       so one model is loaded.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

from run_ablation import ROOT, promptfoo, provenance

CONFIG = Path("promptfoo/configs/08_native.yaml")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "eval"], required=True)
    ap.add_argument("--repro-only", action="store_true", help="only rerun the reproduction check on an existing run")
    a = ap.parse_args()
    if a.repro_only:
        repro(a.split, json.loads((ROOT / "results" / "raw" / f"08_native__{a.split}.json").read_text())["results"]["results"])
        return

    cfg = yaml.safe_load((ROOT / CONFIG).read_text())
    tests = f"promptfoo/tests/{a.split}.yaml"
    raw = ROOT / "results" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    tag = ["--tag", f"split={a.split}", "--tag", "experiment=08_native"]

    t0 = time.time()
    for p in cfg["providers"]:
        label = p["label"]
        print(f"\n== generation: {label} (judge off)", flush=True)
        promptfoo(["-c", str(CONFIG), "-t", tests, "--filter-providers", f"^{label}$", "--grader", "echo",
                   "-j", "1", "--no-write", "-o", str(raw / f"08_native__{a.split}__gen_{label}.json")], cache=True)

    out = raw / f"08_native__{a.split}.json"
    print("\n== full config: generation cached, judge live", flush=True)
    promptfoo(["-c", str(CONFIG), "-t", tests, "-j", "1", "-o", str(out),
               "--description", f"{cfg['description']} [{a.split}]", *tag], cache=True)

    rows = json.loads(out.read_text())["results"]["results"]
    errors = [r for r in rows if r.get("error") and not r.get("namedScores")]
    uncached = [r for r in rows if not (r.get("response") or {}).get("cached")]
    if errors:
        raise SystemExit(f"{len(errors)} provider errors in {out.name}")
    if uncached:
        raise SystemExit(f"{len(uncached)} generations were not promptfoo-cache hits in the full pass")

    print("\n== reproduction check: native SQL vs the custom provider's cached C1 rows", flush=True)
    repro(a.split, rows)

    md = ROOT / "results" / f"08_native__{a.split}.md"
    md.write_text(f"# {cfg['description']} — split `{a.split}`\n\n" + table(rows) + "\n" + provenance(cfg, out))
    print(f"\n{table(rows)}\nwall time {(time.time() - t0) / 60:.1f} min -> {md.relative_to(ROOT)}")


# Custom-provider rows that each native cell must reproduce: (raw file stem, config label).
CUSTOM = {("C1-native", "qwen3.5"): ("01_metadata", "C1-bird"),
          ("C1-native+hints", "qwen3.5"): ("01_metadata", "C1-bird+hints"),
          ("C1-native", "coder"): ("07_coder", "C1-bird@coder"),
          ("C1-native+hints", "coder"): ("07_coder", "C1-bird@coder+hints")}
MODELS = {"qwen3.5": "qwen3.5:9b", "coder": "qwen2.5-coder:7b"}


def repro(split: str, rows: list[dict]) -> None:
    """Analysis 1 (D23): compare each native SQL with the custom provider's cached row. Where they
    differ, make a fresh call through birdeval.llm.chat (use_cache=False never writes the cache):
    native == fresh means Ollama no longer reproduces the old cached reply (drift); native != fresh
    would be a real difference between the two providers."""
    from birdeval.llm import chat, extract_sql
    from birdeval.pipeline import PipelineConfig, build_messages

    custom = {}
    for (prompt, model), (stem, label) in CUSTOM.items():
        for r in json.loads((ROOT / "results" / "raw" / f"{stem}__{split}.json").read_text())["results"]["results"]:
            if r["provider"].get("label") == label:
                custom[(prompt, model, int(r["vars"]["question_id"]))] = r["response"]["output"]
    out = []
    for r in rows:
        prompt, model, qid = r["prompt"]["label"], r["provider"]["label"], int(r["vars"]["question_id"])
        native, cached = r["response"]["output"], custom[(prompt, model, qid)]
        fresh = None
        if native != cached:
            v = {k: r["vars"][k] for k in ("question_id", "db_id", "question", "evidence", "difficulty")}
            msgs = build_messages(v, PipelineConfig(metadata="bird", hints=prompt.endswith("+hints")))
            fresh = extract_sql(chat(msgs, model=MODELS[model], use_cache=False).text)
        out.append({"prompt": prompt, "model": model, "question_id": qid, "same_as_cached": native == cached,
                    "same_as_fresh": None if fresh is None else native == fresh})
    path = ROOT / "results" / "raw" / f"08_native__{split}__repro.json"
    path.write_text(json.dumps(out, indent=1))
    diff = [o for o in out if not o["same_as_cached"]]
    print(f"    same SQL as cached custom row: {len(out) - len(diff)}/{len(out)}; of the {len(diff)} that differ, "
          f"same as a fresh custom call: {sum(o['same_as_fresh'] for o in diff)} -> {path.name}")


def table(rows: list[dict]) -> str:
    """Per (prompt, provider) cell: the rate of each named metric, in %. The judge column is its pass
    verdict, not its score (llm-rubric scores can be fractional), as in analysis/export_native.py."""
    import pandas as pd

    def verdict(r: dict) -> int:
        return int(next(c["pass"] for c in r["gradingResult"]["componentResults"]
                        if c["assertion"]["type"] == "llm-rubric"))

    df = pd.DataFrame([{"prompt": r["prompt"]["label"], "provider": r["provider"]["label"],
                        **(r.get("namedScores") or {}), "judge": verdict(r)} for r in rows])
    metrics = ["ex", "valid_sql", "is_sql_sqlite", "is_sql_mysql", "single_select", "judge"]
    g = df.groupby(["prompt", "provider"], sort=False)
    out = (100 * g[metrics].mean()).round(1)
    out.insert(0, "n", g.size())
    return out.reset_index().to_markdown(index=False) + "\n"


if __name__ == "__main__":
    main()
