"""Majority vote over candidate SQLs by execution result (paper §4, C6).

Paper: "Each of the up to three candidates are executed, and their results converted to
sets. If there is agreement among two of the candidates, one of them is chosen. Else, an
answer is chosen among the candidates randomly."

Ours differs in one place: with no majority we return the lowest-numbered candidate that
executes (candidate 0 is the parent config's answer), instead of a random one. So any
difference from the parent config comes from an actual majority, and runs are deterministic.
Only the database is consulted - never the gold SQL or its runtime.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from birdeval.sqlexec import execute

VOTE_TIMEOUT_S = 30.0  # fixed: a gold-derived timeout would leak information into selection


@dataclass
class Vote:
    winner: int  # index of the chosen candidate
    groups: list[int]  # per candidate: size of its agreement group, 0 if it failed to execute
    exec_ms: float


def pick(keys: list[frozenset | None]) -> tuple[int, list[int]]:
    """keys: per candidate, its result rows as a set, or None if it failed to execute.
    Largest agreement group wins; ties go to the group holding the lowest index."""
    groups: dict[frozenset, list[int]] = {}
    for i, k in enumerate(keys):
        if k is not None:
            groups.setdefault(k, []).append(i)
    sizes = [len(groups[k]) if k is not None else 0 for k in keys]
    if not groups:
        return 0, sizes
    best = max(groups.values(), key=lambda g: (len(g), -g[0]))
    return best[0], sizes


def vote(db_id: str, sqls: list[str], timeout_s: float = VOTE_TIMEOUT_S) -> Vote:
    t0 = time.perf_counter()
    keys = []
    for sql in sqls:
        r = execute(db_id, sql, timeout_s) if sql.strip() else None
        keys.append(frozenset(r.rows) if r is not None and r.ok else None)
    winner, sizes = pick(keys)
    return Vote(winner, sizes, (time.perf_counter() - t0) * 1000)
