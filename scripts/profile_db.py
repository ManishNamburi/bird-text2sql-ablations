"""Profile every column of every MiniDev database -> data/derived/profiles/<db>.json

Run:  uv run python scripts/profile_db.py [db_id ...]
"""

import sys
import time

from birdeval.profiling import profile_db, save_profiles
from birdeval.sqlexec import DB_ROOT


def main() -> None:
    dbs = sys.argv[1:] or sorted(p.name for p in DB_ROOT.iterdir() if p.is_dir())
    total = time.time()
    for db in dbs:
        t0 = time.time()
        profiles = profile_db(db)
        path = save_profiles(db, profiles)
        print(f"{db:26s} {len(profiles):4d} columns  {time.time() - t0:6.1f}s -> {path.name}")
    print(f"total {time.time() - total:.0f}s")


if __name__ == "__main__":
    main()
