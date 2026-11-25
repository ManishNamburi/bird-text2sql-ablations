"""Run one promptfoo experiment config on a frozen split.

    uv run python scripts/run_ablation.py promptfoo/configs/01_metadata.yaml --split dev

Two passes, because promptfoo's loop is `for test: for provider:`. With several configs
in one eval, consecutive Ollama calls would alternate between different prompts and
thrash Ollama's prefix KV cache (single slot).
  1. Warm-up: each config alone (--filter-providers), tests grouped by DB, concurrency 1.
     Fills birdeval's LLM disk cache with good KV-cache locality and comparable timings.
  2. Combined: all configs in one eval. Every LLM call is a disk-cache hit, so it is fast,
     and promptfoo gets one side-by-side table (`npm run view`). The original call timings
     are kept in the cache and reported via provider metadata. This pass runs with
     BIRDEVAL_CACHE_ONLY=1, so a cache miss is an error instead of a concurrent Ollama call.
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

from birdeval.llm import DEFAULT_MODEL, OLLAMA_URL
from birdeval.report import load_results, summarize

ROOT = Path(__file__).resolve().parents[1]
NODE22 = Path("/opt/homebrew/opt/node@22/bin")  # Homebrew's keg-only Node 22 (Mac); used only if present
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def promptfoo_env() -> dict:
    env = dict(os.environ)
    if NODE22.is_dir():
        env["PATH"] = f"{NODE22}{os.pathsep}{env['PATH']}"
    env["PROMPTFOO_PYTHON"] = str(VENV_PYTHON)
    env["PYTHONUTF8"] = "1"  # Windows: the cache and results files are UTF-8, not the ANSI code page
    # One Python worker per provider. promptfoo's default is one per -j slot per provider, so the
    # combined pass (-j 4) of a 28-config experiment started 112 numpy processes and exhausted
    # Windows' commit limit (09 dev, 32 GB RAM). Concurrency across tests is unchanged.
    env["PROMPTFOO_PYTHON_WORKERS"] = "1"
    env.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")  # promptfoo's ollama:chat (08/09 judge); see llm.OLLAMA_URL
    env["PROMPTFOO_CONFIG_DIR"] = str(ROOT / ".promptfoo")  # keep the eval DB in the project
    env["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
    env["PROMPTFOO_DISABLE_UPDATE"] = "1"
    env["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"
    # Per-test limit for the Python provider (promptfoo default: 300 s). One test is a whole
    # pipeline: the slowest dev question took 181 s, and voting (C6) triples the calls.
    env["REQUEST_TIMEOUT_MS"] = str(30 * 60 * 1000)
    return env


def promptfoo(args: list[str], extra_env: dict | None = None, cache: bool = False) -> None:
    """cache=False: promptfoo's response cache is off (D18: its key ignores our imported modules).
    Experiment 08's native provider imports none of them, so it runs with cache=True (D23)."""
    # On Windows, npx is a .cmd file run through cmd.exe, which would treat the `|` and `^` in a
    # --filter-providers regex as a pipe and an escape. Call promptfoo's entry point with node instead.
    want = os.environ.get("BIRDEVAL_OLLAMA_VERSION")  # pin: Ollama's updater replaced 0.40.16 mid-run in 09
    if want:
        import requests
        have = requests.get(f"{OLLAMA_URL}/api/version", timeout=30).json()["version"]
        if have != want:
            raise SystemExit(f"Ollama is {have}, expected {want} (BIRDEVAL_OLLAMA_VERSION): stopping")
    exe = (["node", str(ROOT / "node_modules" / "promptfoo" / "dist" / "src" / "entrypoint.js")] if os.name == "nt"
           else ["npx", "promptfoo"])
    cmd = [*exe, "eval", *args, *([] if cache else ["--no-cache"]), "--no-table", "--no-progress-bar"]
    print("$", " ".join(cmd), flush=True)
    env = {**promptfoo_env(), **(extra_env or {})}
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout.splitlines():
        if re.search(r"passed|failed|\d+ errors? \(|Duration|Error log", line):
            print("   ", line.strip(), flush=True)
    if proc.returncode not in (0, 100):  # promptfoo exits 100 when some tests fail: expected here
        print(proc.stdout[-3000:], proc.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"promptfoo failed with exit code {proc.returncode}")


def provenance(cfg: dict, raw: Path) -> str:
    """Project rule: every results file records model tag + digest, Ollama and promptfoo versions."""
    import json

    import requests

    def model(p: dict) -> str:  # promptfoo's native provider names the model in its id
        if p["id"].startswith("ollama:chat:"):
            return p["id"].removeprefix("ollama:chat:")
        return (p.get("config") or {}).get("model", DEFAULT_MODEL)

    models = sorted({model(p) for p in cfg["providers"]})
    tags = {m["name"]: m for m in requests.get(f"{OLLAMA_URL}/api/tags", timeout=10).json()["models"]}
    ollama = requests.get(f"{OLLAMA_URL}/api/version", timeout=10).json()["version"]
    meta = json.loads(raw.read_text(encoding="utf-8")).get("metadata", {})
    def quant(m: str) -> str:
        d = requests.post(f"{OLLAMA_URL}/api/show", json={"model": m}, timeout=10).json().get("details", {})
        return f"{d.get('parameter_size')}, {d.get('quantization_level')}, {d.get('runner') or d.get('format')}"

    lines = [f"- `{m}`: digest `{tags[m]['digest'][:12]}` ({quant(m)}), pulled {tags[m]['modified_at'][:16]}"
             for m in models]
    return ("\n**Provenance:** " + f"Ollama {ollama}, promptfoo {meta.get('promptfooVersion')}, "
            f"Node {meta.get('nodeVersion')}, exported {meta.get('exportedAt', '')[:16]}Z.\n" + "\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--split", choices=["dev", "eval", "test"], required=True)
    ap.add_argument("--providers", default=".*", help="regex over provider labels")
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--replay", action="store_true",
                    help="the warm-ups already filled the cache: run only the combined pass, cache-only")
    ap.add_argument("--jobs", type=int, default=4, help="concurrency of a cache-only combined pass "
                    "(09: lowered to 1 after the machine crashed under the -j 4 load)")
    a = ap.parse_args()
    if os.name == "nt":  # keep Windows from idle-sleeping during the run (caffeinate -i on the Mac)
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    labels = [p["label"] for p in cfg["providers"] if re.search(a.providers, p["label"])]
    if not labels:
        raise SystemExit(f"no provider label matches {a.providers!r}")
    tests = f"promptfoo/tests/{a.split}.yaml"
    config = str(a.config.relative_to(ROOT) if a.config.is_absolute() else a.config)

    t0 = time.time()
    if not (a.no_warmup or a.replay):
        for label in labels:
            print(f"\n== warm-up: {label}", flush=True)
            promptfoo(["-c", config, "-t", tests, "--filter-providers", f"^{re.escape(label)}$",
                       "--no-write", "-j", "1"])

    out = ROOT / "results" / "raw" / f"{a.config.stem}__{a.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    regex = "^(" + "|".join(re.escape(lbl) for lbl in labels) + ")$"
    print("\n== combined eval (cache hits)", flush=True)
    warmed = a.replay or not a.no_warmup  # without a warm-up the combined pass must call Ollama: run it serially
    promptfoo(["-c", config, "-t", tests, "--filter-providers", regex, "-j", str(a.jobs) if warmed else "1",
               "-o", str(out), "--description", f"{cfg.get('description', a.config.stem)} [{a.split}]",
               "--tag", f"split={a.split}", "--tag", f"experiment={a.config.stem}"],
              extra_env={"BIRDEVAL_CACHE_ONLY": "1"} if warmed else None)

    df = load_results(out)
    if df["provider_error"].any():
        bad = df[df["provider_error"]].groupby("config").size().to_dict()
        raise SystemExit(f"provider errors in {out.name} (e.g. cache misses in the combined pass): {bad}")
    summary = summarize(df, order=labels)
    md = ROOT / "results" / f"{a.config.stem}__{a.split}.md"
    md.write_text(f"# {cfg.get('description', a.config.stem)} — split `{a.split}`\n\n"
                  + summary.to_markdown(index=False) + "\n" + provenance(cfg, out), encoding="utf-8")
    print(f"\n{summary.to_string(index=False)}\n\nwall time {(time.time() - t0) / 60:.1f} min -> {md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
