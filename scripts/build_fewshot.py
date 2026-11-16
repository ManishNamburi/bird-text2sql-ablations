"""Mask + embed the few-shot pools and the MiniDev questions -> data/derived/fewshot/

  train.json/.npz      masked BIRD-train questions (6,601)
  querylog.json/.npz   masked BIRD-dev questions not in MiniDev (~1,035)
  minidev.json/.npz    masked MiniDev questions (question text only; never SQL)

LLM masking is batched (25 questions per call) and disk-cached, so reruns are free.
Run AFTER other LLM jobs finish (it competes for the GPU):
    uv run python scripts/build_fewshot.py
"""

import json
import time

from birdeval.fewshot import BATCH, load_pools, mask_batch, save_embeddings, save_masked
from birdeval.sqlexec import DATA_ROOT


def build(name: str, ids: list[str], questions: list[str]) -> None:
    t0, masked = time.time(), []
    for i in range(0, len(questions), BATCH):
        masked += mask_batch(questions[i : i + BATCH])
        if (i // BATCH) % 20 == 0:
            print(f"  {name}: {len(masked)}/{len(questions)} masked ({time.time() - t0:.0f}s)", flush=True)
    save_masked(name, ids, masked)
    save_embeddings(name, ids, masked)
    print(f"{name}: {len(ids)} masked + embedded in {(time.time() - t0) / 60:.1f} min", flush=True)


def main() -> None:
    pools = load_pools()
    seen, minidev = set(), []
    for q in json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text()):
        if q["question_id"] not in seen:
            seen.add(q["question_id"])
            minidev.append(q)
    build("minidev", [f"mini:{q['question_id']}" for q in minidev], [q["question"] for q in minidev])
    for name in ("querylog", "train"):
        build(name, [r["id"] for r in pools[name]], [r["question"] for r in pools[name]])


if __name__ == "__main__":
    main()
