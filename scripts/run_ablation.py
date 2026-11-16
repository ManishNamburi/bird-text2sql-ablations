"""Run one promptfoo experiment config on a frozen split.

    uv run python scripts/run_ablation.py promptfoo/configs/01_metadata.yaml --split dev

Two passes, because promptfoo's loop is `for test: for provider:`. With several configs
in one eval, consecutive Ollama calls would alternate between different prompts and
thrash Ollama's prefix KV cache (single slot).
  1. Warm-up: each config alone (--filter-providers), tests grouped by DB, concurrency 1.
     Fills birdeval's LLM disk cache with good KV-cache locality and comparable timings.
  2. Combined: all configs in one eval. Every LLM call is a disk-cache hit, so it is fast,
     and promptfoo gets one side-by-side table (`npm run view`). The original call timings
     are kept in the cache and reported via provider metadata.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

from birdeval.report import load_results, summarize

ROOT = Path(__file__).resolve().parents[1]
NODE22 = "/opt/homebrew/opt/node@22/bin"


def promptfoo_env() -> dict:
    env = dict(os.environ)
    env["PATH"] = f"{NODE22}:{env['PATH']}"
    env["PROMPTFOO_PYTHON"] = str(ROOT / ".venv" / "bin" / "python")
    env["PROMPTFOO_CONFIG_DIR"] = str(ROOT / ".promptfoo")  # keep the eval DB in the project
    env["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
    env["PROMPTFOO_DISABLE_UPDATE"] = "1"
    env["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"
    return env


def promptfoo(args: list[str]) -> None:
    cmd = ["npx", "promptfoo", "eval", *args, "--no-cache", "--no-table", "--no-progress-bar"]
    print("$", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, env=promptfoo_env(), capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if re.search(r"passed|failed|errors|Duration|Error log", line):
            print("   ", line.strip(), flush=True)
    if proc.returncode not in (0, 100):  # promptfoo exits 100 when some tests fail: expected here
        print(proc.stdout[-3000:], proc.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"promptfoo failed with exit code {proc.returncode}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--split", choices=["dev", "eval", "test"], required=True)
    ap.add_argument("--providers", default=".*", help="regex over provider labels")
    ap.add_argument("--no-warmup", action="store_true")
    a = ap.parse_args()

    cfg = yaml.safe_load(a.config.read_text())
    labels = [p["label"] for p in cfg["providers"] if re.search(a.providers, p["label"])]
    if not labels:
        raise SystemExit(f"no provider label matches {a.providers!r}")
    tests = f"promptfoo/tests/{a.split}.yaml"
    config = str(a.config.relative_to(ROOT) if a.config.is_absolute() else a.config)

    t0 = time.time()
    if not a.no_warmup:
        for label in labels:
            print(f"\n== warm-up: {label}", flush=True)
            promptfoo(["-c", config, "-t", tests, "--filter-providers", f"^{re.escape(label)}$",
                       "--no-write", "-j", "1"])

    out = ROOT / "results" / "raw" / f"{a.config.stem}__{a.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    regex = "^(" + "|".join(re.escape(lbl) for lbl in labels) + ")$"
    print("\n== combined eval (cache hits)", flush=True)
    promptfoo(["-c", config, "-t", tests, "--filter-providers", regex, "-j", "4", "-o", str(out),
               "--description", f"{cfg.get('description', a.config.stem)} [{a.split}]"])

    summary = summarize(load_results(out), order=labels)
    md = ROOT / "results" / f"{a.config.stem}__{a.split}.md"
    md.write_text(f"# {cfg.get('description', a.config.stem)} — split `{a.split}`\n\n"
                  + summary.to_markdown(index=False) + "\n")
    print(f"\n{summary.to_string(index=False)}\n\nwall time {(time.time() - t0) / 60:.1f} min -> {md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
