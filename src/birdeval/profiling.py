"""Database profiling (paper §2): per-column statistics -> a mechanical English profile.

Stats per column (all computed in SQLite, so they reflect what queries will actually see):
  - row count, NULL count, distinct count, min/max
  - top-10 most common values with counts
  - storage classes via typeof()  -> catches numbers stored as TEXT (paper Q1260: RF < 20)
  - over a sample of up to 10,000 distinct values: length range, "looks numeric",
    JSON-looking values, and dominant format patterns (digits->9, letters->A/a), e.g. a
    date column stored as '2013-06-01' -> 9999-99-99 vs one stored as '201306' -> 999999.

The English rendering follows the paper's example format for frpm.CDSCode.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from birdeval.schema import load_schema, quote
from birdeval.sqlexec import db_path

DERIVED = Path(__file__).resolve().parents[2] / "data" / "derived"
SAMPLE_N = 10_000  # distinct values sampled per column (paper uses N=10000)
MAX_VALUE_CHARS = 60  # truncate long text values when showing them


@dataclass
class ColumnProfile:
    table: str
    column: str
    declared_type: str
    n_rows: int
    n_null: int
    n_distinct: int
    min_value: str | None
    max_value: str | None
    top_values: list[tuple[str, int]]
    storage: dict[str, int]  # typeof() -> count (non-null)
    min_len: int | None = None
    max_len: int | None = None
    all_numeric: bool = False
    looks_json: bool = False
    patterns: list[tuple[str, float]] = field(default_factory=list)  # (pattern, share of sample)


def _show(v) -> str:
    s = str(v)
    return s if len(s) <= MAX_VALUE_CHARS else s[:MAX_VALUE_CHARS] + "..."


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _pattern(s: str) -> str:
    return re.sub(r"[a-z]", "a", re.sub(r"[A-Z]", "A", re.sub(r"[0-9]", "9", s)))


def profile_column(con: sqlite3.Connection, table: str, column: str, declared_type: str) -> ColumnProfile:
    t, c = quote(table), quote(column)
    n_rows, n_nonnull, n_distinct, mn, mx = con.execute(
        f"SELECT COUNT(*), COUNT({c}), COUNT(DISTINCT {c}), MIN({c}), MAX({c}) FROM {t}").fetchone()
    top = con.execute(
        f"SELECT {c}, COUNT(*) AS n FROM {t} WHERE {c} IS NOT NULL GROUP BY {c} ORDER BY n DESC LIMIT 10").fetchall()
    storage = dict(con.execute(f"SELECT typeof({c}), COUNT(*) FROM {t} WHERE {c} IS NOT NULL GROUP BY 1").fetchall())
    sample = [str(r[0]) for r in con.execute(
        f"SELECT DISTINCT {c} FROM {t} WHERE {c} IS NOT NULL LIMIT {SAMPLE_N}")]

    p = ColumnProfile(table, column, declared_type, n_rows, n_rows - n_nonnull, n_distinct,
                      None if mn is None else _show(mn), None if mx is None else _show(mx),
                      [(_show(v), n) for v, n in top], storage)
    if sample:
        lens = [len(s) for s in sample]
        p.min_len, p.max_len = min(lens), max(lens)
        p.all_numeric = all(_is_number(s) for s in sample)
        p.looks_json = sum(s[:1] in "[{" for s in sample) > 0.9 * len(sample) and _parses_json(sample[0])
        # Patterns add nothing when the top-10 list already shows every distinct value.
        if not p.all_numeric and p.max_len <= 40 and n_distinct > len(top):
            pats = Counter(_pattern(s) for s in sample)
            common = pats.most_common(3)
            if common[0][1] / len(sample) >= 0.3:  # only report when a format clearly dominates
                p.patterns = [(pat, round(n / len(sample), 2)) for pat, n in common if n / len(sample) >= 0.05]
    return p


def _parses_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except ValueError:
        return False


def english(p: ColumnProfile) -> str:
    """Mechanical English profile, in the format of the paper's §2.1 example."""
    out = [f"Column {p.column} has {p.n_null} NULL values out of {p.n_rows} records."]
    if p.n_rows == p.n_null:
        return " ".join(out + ["The column is always NULL."])
    out.append(f"There are {p.n_distinct} distinct values.")
    out.append(f"The minimum value is '{p.min_value}' and the maximum value is '{p.max_value}'.")
    if p.top_values:
        vals = ", ".join(f"'{v}' ({n})" for v, n in p.top_values)
        out.append(f"Most common non-NULL column values (with counts) are {vals}.")
    if p.min_len is not None:
        out.append(f"The values are always {p.min_len} characters long." if p.min_len == p.max_len
                   else f"Value lengths range from {p.min_len} to {p.max_len} characters.")
    # Always state the storage class: profiles quote every value ('14872'), and without this
    # sentence the summarizer guessed "stored as text" for INTEGER columns (spot-check, D11).
    stored = {k: v for k, v in p.storage.items() if v}
    if p.all_numeric and set(stored) == {"text"}:
        out.append("Every column value looks like a number, but the values are stored as TEXT.")
    elif p.all_numeric:
        out.append("Every column value looks like a number.")
    if len(stored) == 1 and not (p.all_numeric and set(stored) == {"text"}):
        out.append(f"Values are stored as {next(iter(stored)).upper()}.")
    elif len(stored) > 1:
        out.append("Values are stored with mixed types: " + ", ".join(f"{k} ({v})" for k, v in stored.items()) + ".")
    if p.looks_json:
        out.append("The values look like JSON documents.")
    if p.patterns:
        pats = ", ".join(f"'{pat}' ({share:.0%})" for pat, share in p.patterns)
        out.append(f"Value formats (9 = digit, A/a = letter) are {pats}.")
    return " ".join(out)


def profile_db(db_id: str) -> list[ColumnProfile]:
    con = sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return [profile_column(con, t.name, col.name, col.type) for t in load_schema(db_id) for col in t.columns]


def profiles_path(db_id: str) -> Path:
    return DERIVED / "profiles" / f"{db_id}.json"


def save_profiles(db_id: str, profiles: list[ColumnProfile]) -> Path:
    path = profiles_path(db_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{**asdict(p), "english": english(p)} for p in profiles], indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def load_profiles(db_id: str) -> list[dict]:
    return json.loads(profiles_path(db_id).read_text(encoding="utf-8"))


# A quoted literal in an LLM summary: opens after a non-word char, closes before one. An inner
# apostrophe between letters stays inside ('St. Mary's Middle'); a possessive (school's) never
# opens a literal, since its quote follows a letter.
_LITERAL = re.compile(r"(?<![\w'])'(?:[^'\n]|(?<=\w)'(?=\w))*'(?!\w)")
MASK = "'…'"


def mask_literals(text: str) -> str:
    """T2 trim: replace every quoted example value in a profile summary with a placeholder.
    Counts, lengths and formats stay, so only the value information is removed."""
    return _LITERAL.sub(MASK, text)


@lru_cache(maxsize=None)
def load_summaries(db_id: str, detail: str = "long") -> dict[tuple[str, str], str]:
    """LLM profile summaries (scripts/summarize_profiles.py) keyed for schema.render()."""
    if detail not in ("short", "long"):
        raise ValueError(f"detail must be 'short' or 'long', got {detail!r}")
    path = DERIVED / "summaries" / f"{db_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run: uv run python scripts/summarize_profiles.py")
    out = {}
    for key, s in json.loads(path.read_text(encoding="utf-8")).items():
        table, column = key.split(".", 1)
        out[(table.lower(), column.lower())] = " ".join(s[detail].split())
    return out
