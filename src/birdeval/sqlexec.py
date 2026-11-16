"""Read-only SQLite execution and BIRD execution accuracy (EX).

BIRD's official EX (mini_dev/llm/src/evaluation_ex.py) is:
    set(predicted_rows) == set(gold_rows)
i.e. row order and duplicates are ignored, column order matters. We reproduce that
exactly so our numbers are comparable to the paper and the leaderboard.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "minidev" / "MINIDEV"
DB_ROOT = DATA_ROOT / "dev_databases"


class QueryTimeout(Exception):
    pass


@dataclass
class ExecResult:
    ok: bool
    rows: list[tuple] | None
    error: str | None
    ms: float


def db_path(db_id: str) -> Path:
    return DB_ROOT / db_id / f"{db_id}.sqlite"


@lru_cache(maxsize=None)
def _connect(db_id: str) -> sqlite3.Connection:
    # mode=ro guarantees model-generated SQL can never modify the benchmark DBs.
    con = sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True, check_same_thread=False)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return con


def execute(db_id: str, sql: str, timeout_s: float = 30.0, max_rows: int = 100_000) -> ExecResult:
    """Run SQL with a wall-clock timeout implemented via SQLite's progress handler
    (no threads, and the query is genuinely interrupted rather than abandoned)."""
    con = _connect(db_id)
    deadline = time.perf_counter() + timeout_s
    con.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
    t0 = time.perf_counter()
    try:
        cur = con.execute(sql)
        rows = cur.fetchmany(max_rows)
        return ExecResult(True, rows, None, (time.perf_counter() - t0) * 1000)
    except sqlite3.OperationalError as e:
        msg = "timeout" if "interrupted" in str(e) else str(e)
        return ExecResult(False, None, msg, (time.perf_counter() - t0) * 1000)
    except Exception as e:  # noqa: BLE001 - any failure means "not valid SQL" for scoring
        return ExecResult(False, None, f"{type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)
    finally:
        con.set_progress_handler(None, 0)


def results_match(pred_rows: list[tuple], gold_rows: list[tuple]) -> bool:
    """BIRD EX comparison: unordered set equality of result rows."""
    return set(pred_rows) == set(gold_rows)


@dataclass
class EXScore:
    match: bool
    valid_sql: bool
    error: str | None
    pred_rows_preview: list[tuple] | None
    gold_rows_preview: list[tuple] | None


# --- Gold result cache -------------------------------------------------------------
# Gold queries are executed once (scripts/cache_gold.py) and their rows cached.
# Why: two MiniDev gold queries take 37 s and 184 s on this machine, so BIRD's fixed
# 30 s timeout would mark those questions wrong for *every* config. Caching also halves
# per-test eval time. Pickle (not JSON) keeps row values bit-exact (floats, bytes).
GOLD_CACHE = Path(__file__).resolve().parents[2] / "data" / "derived" / "gold_results.pkl"
MIN_TIMEOUT_S = 30.0
GOLD_TIME_FACTOR = 2.0


@lru_cache(maxsize=1)
def load_gold() -> dict[int, dict]:
    import pickle

    if not GOLD_CACHE.exists():
        raise FileNotFoundError(f"{GOLD_CACHE} missing - run: uv run python scripts/cache_gold.py")
    return pickle.loads(GOLD_CACHE.read_bytes())


def timeout_for(question_id: int) -> float:
    """Per-question timeout: a correct-but-slow prediction gets 2x the gold query's runtime."""
    return max(MIN_TIMEOUT_S, GOLD_TIME_FACTOR * load_gold()[question_id]["ms"] / 1000)


def score_question(question_id: int, db_id: str, pred_sql: str) -> EXScore:
    gold_rows = load_gold()[question_id]["rows"]
    pred = execute(db_id, pred_sql, timeout_for(question_id))
    if not pred.ok:
        return EXScore(False, False, pred.error, None, gold_rows[:5])
    return EXScore(results_match(pred.rows, gold_rows), True, None, pred.rows[:5], gold_rows[:5])
