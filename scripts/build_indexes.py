"""Build per-DB indexes used by schema linking (paper §3):
  - value LSH index        -> data/derived/valueindex/<db>.pkl
  - column-summary vectors -> data/derived/embeddings/<db>.npz   (needs summaries + Ollama)

Run:  uv run python scripts/build_indexes.py [--only values|embeddings] [db_id ...]
"""

import sys
import time

from birdeval import embed, valueindex
from birdeval.sqlexec import DB_ROOT


def main() -> None:
    args = sys.argv[1:]
    only = None
    if args[:1] == ["--only"]:
        only, args = args[1], args[2:]
    dbs = args or sorted(p.name for p in DB_ROOT.iterdir() if p.is_dir())
    total = time.time()
    for db in dbs:
        if only in (None, "values"):
            t0 = time.time()
            n = valueindex.save(db)
            size = valueindex.index_path(db).stat().st_size / 1e6
            print(f"{db:26s} {n:8,} values   {time.time() - t0:6.1f}s  {size:6.1f} MB", flush=True)
        if only in (None, "embeddings"):
            t0 = time.time()
            n = embed.build(db)
            print(f"{db:26s} {n:8,} columns  {time.time() - t0:6.1f}s  (embeddings)", flush=True)
    print(f"total {time.time() - total:.0f}s")


if __name__ == "__main__":
    main()
