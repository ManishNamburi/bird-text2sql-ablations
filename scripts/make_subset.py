"""Freeze the evaluation splits (run once; output is committed).

Splits over the 498 unique MiniDev questions, stratified by (db_id, difficulty):
  dev   (30)  - the ONLY questions we look at while iterating on prompts/pipeline code
  eval  (150) - every ablation config runs here; disjoint from dev
  test  (468) - all non-dev questions (superset of eval); for the 2-3 headline configs

Why keep dev out of the headline set: any question we tuned on would inflate the score.

Allocation uses the largest-remainder method so each stratum gets its proportional share.
Run:  uv run python scripts/make_subset.py
"""

import json
import random
from collections import defaultdict
from pathlib import Path

from birdeval.sqlexec import DATA_ROOT

SEED = 42
N_DEV, N_EVAL = 30, 150
OUT = Path(__file__).resolve().parents[1] / "data" / "subset_ids.json"


def unique_questions() -> list[dict]:
    seen, out = set(), []
    for q in json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text()):
        if q["question_id"] not in seen:  # MiniDev contains exact duplicates of qid 137 and 138
            seen.add(q["question_id"])
            out.append(q)
    return out


def allocate(strata: dict[tuple, list], n: int) -> dict[tuple, int]:
    total = sum(len(v) for v in strata.values())
    quotas = {k: n * len(v) / total for k, v in strata.items()}
    alloc = {k: int(q) for k, q in quotas.items()}
    by_remainder = sorted(quotas, key=lambda k: (quotas[k] - alloc[k], k), reverse=True)
    for k in by_remainder[: n - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def stratified_sample(qs: list[dict], n: int, rng: random.Random) -> list[int]:
    strata = defaultdict(list)
    for q in qs:
        strata[(q["db_id"], q["difficulty"])].append(q["question_id"])
    picked = []
    for k, m in allocate(strata, n).items():
        ids = sorted(strata[k])
        rng.shuffle(ids)
        picked += ids[:m]
    return sorted(picked)


def main() -> None:
    qs = unique_questions()
    rng = random.Random(SEED)
    dev = stratified_sample(qs, N_DEV, rng)
    rest = [q for q in qs if q["question_id"] not in set(dev)]
    eval_ = stratified_sample(rest, N_EVAL, rng)
    test = sorted(q["question_id"] for q in rest)
    assert not set(dev) & set(eval_) and not set(dev) & set(test) and set(eval_) <= set(test)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"seed": SEED, "dev": dev, "eval": eval_, "test": test}, indent=1))

    by_id = {q["question_id"]: q for q in qs}
    for name, ids in [("dev", dev), ("eval", eval_), ("test", test)]:
        diff = defaultdict(int)
        dbs = defaultdict(int)
        for i in ids:
            diff[by_id[i]["difficulty"]] += 1
            dbs[by_id[i]["db_id"]] += 1
        print(f"{name:5s} n={len(ids):3d} difficulty={dict(sorted(diff.items()))} dbs={len(dbs)}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
