"""Execute every MiniDev gold query once and cache rows + runtime.

Run:  uv run python scripts/cache_gold.py
Takes ~4 minutes (dominated by two slow gold queries). Fails loudly if any gold query errors.
"""

import json
import pickle
import sys

from birdeval.sqlexec import DATA_ROOT, GOLD_CACHE, execute


def main() -> int:
    questions = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text())
    cache, failures = {}, []
    for i, q in enumerate(questions, 1):
        r = execute(q["db_id"], q["SQL"], timeout_s=900)
        if not r.ok:
            failures.append((q["question_id"], r.error))
            continue
        cache[q["question_id"]] = {"rows": r.rows, "ms": r.ms, "db_id": q["db_id"]}
        if r.ms > 5000:
            print(f"  slow gold: qid={q['question_id']} {q['db_id']} {r.ms / 1000:.1f}s")
        if i % 100 == 0:
            print(f"{i}/{len(questions)}")
    if failures:
        print("Gold queries failed:", failures, file=sys.stderr)
        return 1
    GOLD_CACHE.parent.mkdir(parents=True, exist_ok=True)
    GOLD_CACHE.write_bytes(pickle.dumps(cache))
    print(f"cached {len(cache)} gold results -> {GOLD_CACHE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
