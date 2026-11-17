"""Approximate value index: which columns contain a value like this literal? (paper §3)

The paper attaches a MinHash-LSH index on character shingles of up to N=10,000 distinct
values per field, so literals from a question or a generated query can be matched to the
fields that actually contain them, approximately (case, spacing and small spelling
differences) but not semantically.

Design: one MinHashLSH per database; each key is (table, column, value). A query returns
candidate keys from LSH, which we re-score with exact shingle Jaccard similarity.
Columns indexed: non-numeric, non-JSON values up to 100 chars (free text such as post
bodies is not where question literals live).
"""

from __future__ import annotations

import pickle
import sqlite3
from dataclasses import dataclass
from functools import lru_cache

from datasketch import LeanMinHash, MinHash, MinHashLSH

from birdeval.profiling import DERIVED, SAMPLE_N, load_profiles
from birdeval.schema import quote
from birdeval.sqlexec import db_path

NUM_PERM = 64
LSH_THRESHOLD = 0.5
MAX_VALUE_LEN = 100


def shingles(value: str, k: int = 3) -> set[str]:
    s = " ".join(str(value).lower().split())
    if len(s) <= k:
        return {s}
    return {s[i : i + k] for i in range(len(s) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass
class Match:
    table: str
    column: str
    value: str
    similarity: float


def _indexable(p: dict) -> bool:
    return (not p["all_numeric"] and not p["looks_json"] and p["n_distinct"] > 0
            and (p["max_len"] or 0) <= MAX_VALUE_LEN)


def build(db_id: str) -> tuple[MinHashLSH, dict[str, tuple[str, str, str]]]:
    con = sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
    keys: dict[str, tuple[str, str, str]] = {}
    for p in filter(_indexable, load_profiles(db_id)):
        t, c = quote(p["table"]), quote(p["column"])
        values = [str(r[0]) for r in con.execute(
            f"SELECT DISTINCT {c} FROM {t} WHERE {c} IS NOT NULL LIMIT {SAMPLE_N}")]
        sets = [{s.encode() for s in shingles(v)} for v in values]
        for v, mh in zip(values, MinHash.bulk(sets, num_perm=NUM_PERM)):
            key = f"{len(keys)}"
            keys[key] = (p["table"], p["column"], v)
            lsh.insert(key, LeanMinHash(mh), check_duplication=False)
    return lsh, keys


def index_path(db_id: str):
    return DERIVED / "valueindex" / f"{db_id}.pkl"


def save(db_id: str) -> int:
    lsh, keys = build(db_id)
    path = index_path(db_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps((lsh, keys), protocol=pickle.HIGHEST_PROTOCOL))
    return len(keys)


@lru_cache(maxsize=None)
def _load(db_id: str):
    return pickle.loads(index_path(db_id).read_bytes())


def lookup(db_id: str, literal: str, min_similarity: float = 0.6, top_k: int = 10) -> list[Match]:
    """Columns whose sampled values approximately match `literal`, best match per column."""
    lsh, keys = _load(db_id)
    q = shingles(literal)
    mh = MinHash(num_perm=NUM_PERM)
    mh.update_batch([s.encode() for s in q])
    best: dict[tuple[str, str], Match] = {}
    # lsh.query returns a set: iterate in index order so ties (equal similarity) resolve the same
    # way in every process. Otherwise the revision prompt depends on PYTHONHASHSEED.
    for key in sorted(lsh.query(mh), key=int):
        table, column, value = keys[key]
        sim = jaccard(q, shingles(value))
        if sim >= min_similarity and sim > best.get((table, column), Match("", "", "", -1)).similarity:
            best[(table, column)] = Match(table, column, value, round(sim, 3))
    return sorted(best.values(), key=lambda m: -m.similarity)[:top_k]
