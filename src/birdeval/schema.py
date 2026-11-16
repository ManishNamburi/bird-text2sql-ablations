"""Schema loading and rendering for prompts.

All metadata variants share ONE renderer so ablation configs differ only in the
comment attached to each column (one variable at a time):

    CREATE TABLE frpm (
      CDSCode TEXT PRIMARY KEY,
      `Academic Year` TEXT, -- <metadata for this column, if any>
      ...
      FOREIGN KEY (CDSCode) REFERENCES schools(CDSCode)
    );

Structure comes from SQLite PRAGMAs (not the raw CREATE statements) so every DB is
rendered in the same canonical format regardless of how its DDL was written.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import warnings
from dataclasses import dataclass, field
from functools import lru_cache

from birdeval.sqlexec import DB_ROOT, db_path


@dataclass
class Column:
    table: str
    name: str
    type: str
    pk: int  # 0 = not in PK, else 1-based position in the (possibly composite) PK
    bird_desc: str = ""  # BIRD SME column description
    bird_values: str = ""  # BIRD SME value description


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    fks: list[tuple[str, str, str | None]] = field(default_factory=list)  # (col, ref_table, ref_col)


_SIMPLE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# SQLite keywords (https://www.sqlite.org/lang_keywords.html). BIRD has e.g. a table named `order`.
_SQLITE_KEYWORDS = frozenset("""
ABORT ACTION ADD AFTER ALL ALTER ALWAYS ANALYZE AND AS ASC ATTACH AUTOINCREMENT BEFORE BEGIN
BETWEEN BY CASCADE CASE CAST CHECK COLLATE COLUMN COMMIT CONFLICT CONSTRAINT CREATE CROSS
CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP DATABASE DEFAULT DEFERRABLE DEFERRED
DELETE DESC DETACH DISTINCT DO DROP EACH ELSE END ESCAPE EXCEPT EXCLUDE EXCLUSIVE EXISTS
EXPLAIN FAIL FILTER FIRST FOLLOWING FOR FOREIGN FROM FULL GENERATED GLOB GROUP GROUPS HAVING
IF IGNORE IMMEDIATE IN INDEX INDEXED INITIALLY INNER INSERT INSTEAD INTERSECT INTO IS ISNULL
JOIN KEY LAST LEFT LIKE LIMIT MATCH MATERIALIZED NATURAL NO NOT NOTHING NOTNULL NULL NULLS OF
OFFSET ON OR ORDER OTHERS OUTER OVER PARTITION PLAN PRAGMA PRECEDING PRIMARY QUERY RAISE
RANGE RECURSIVE REFERENCES REGEXP REINDEX RELEASE RENAME REPLACE RESTRICT RETURNING RIGHT
ROLLBACK ROW ROWS SAVEPOINT SELECT SET TABLE TEMP TEMPORARY THEN TIES TO TRANSACTION TRIGGER
UNBOUNDED UNION UNIQUE UPDATE USING VACUUM VALUES VIEW VIRTUAL WHEN WHERE WINDOW WITH WITHOUT
""".split())


def quote(name: str) -> str:
    if _SIMPLE_IDENT.match(name) and name.upper() not in _SQLITE_KEYWORDS:
        return name
    return f"`{name}`"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _one_line(s: str) -> str:
    s = re.sub(r"(?i)commonsense evidence:\s*", "", s)  # BIRD annotation label, not content
    return re.sub(r"\s+", " ", s).strip()


def _read_csv(path) -> list[dict]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:  # 4 BIRD description files are cp1252
        text = raw.decode("cp1252", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _bird_descriptions(db_id: str) -> dict[tuple[str, str], tuple[str, str]]:
    """{(table_lower, column_lower): (description, value_description)}"""
    out = {}
    for path in sorted((DB_ROOT / db_id / "database_description").glob("*.csv")):
        table = path.stem.lower()
        for row in _read_csv(path):
            col = (row.get("original_column_name") or "").strip()
            if not col:
                continue
            desc = _one_line(row.get("column_description") or "") or _one_line(row.get("column_name") or "")
            out[(table, col.lower())] = (desc, _one_line(row.get("value_description") or ""))
    return out


@lru_cache(maxsize=None)
def load_schema(db_id: str) -> tuple[Table, ...]:
    con = sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True)
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    bird = _bird_descriptions(db_id)
    used = set()
    tables = []
    for t in names:
        table = Table(t)
        for _cid, name, ctype, _notnull, _default, pk in con.execute(f"PRAGMA table_info({quote(t)})"):
            key = (t.lower(), name.lower())
            desc, values = bird.get(key, ("", ""))
            used.add(key)
            table.columns.append(Column(t, name, (ctype or "").strip().upper(), int(pk), desc, values))
        for fk in con.execute(f"PRAGMA foreign_key_list({quote(t)})"):
            table.fks.append((fk[3], fk[2], fk[4]))
        tables.append(table)
    for key in sorted(set(bird) - used):
        warnings.warn(f"{db_id}: BIRD description for non-existent column {key[0]}.{key[1]} ignored")
    return tuple(tables)


def bird_comment(col: Column, values: bool = True) -> str:
    """BIRD SME metadata as a one-line comment. Descriptions that merely repeat the column
    name carry no information and are dropped (saves tokens without losing content)."""
    parts = []
    if col.bird_desc and _norm(col.bird_desc) != _norm(col.name):
        parts.append(col.bird_desc)
    if values and col.bird_values:
        parts.append(f"values: {col.bird_values}")
    return " | ".join(parts)


def render(
    db_id: str,
    *,
    bird: bool = False,
    bird_values: bool = True,
    profile: dict[tuple[str, str], str] | None = None,
    columns: set[tuple[str, str]] | None = None,
    shuffle_seed: int | None = None,
) -> str:
    """Render the schema as canonical CREATE TABLE statements.
    bird: attach BIRD SME column metadata; bird_values: include BIRD value descriptions.
    profile: {(table_lower, column_lower): LLM profile summary} to attach (C2/C3).
    With both, the comment is "<BIRD> || <profile>" (fused metadata, C3).
    columns: {(table_lower, column_lower)} to keep (schema linking). Tables with no selected
      column are dropped; kept tables also keep their primary keys and the foreign keys
      (both ends) to other kept tables, so the model can still write the joins.
    shuffle_seed: shuffle column order within tables (candidate diversity for voting, C6)."""
    keep = _expand_selection(db_id, columns) if columns is not None else None
    blocks = []
    for table in load_schema(db_id):
        cols = [c for c in table.columns if keep is None or (table.name.lower(), c.name.lower()) in keep]
        if not cols:
            continue
        if shuffle_seed is not None:
            import random

            cols = cols[:]
            random.Random(f"{shuffle_seed}:{table.name}").shuffle(cols)
        kept_tables = None if keep is None else {t for t, _ in keep}
        items: list[tuple[str, str]] = []  # (sql fragment, comment)
        pk_cols = sorted((c for c in table.columns if c.pk), key=lambda c: c.pk)
        for col in cols:
            inline_pk = " PRIMARY KEY" if len(pk_cols) == 1 and col.pk else ""
            frag = f"{quote(col.name)} {col.type}".rstrip() + inline_pk
            parts = [bird_comment(col, bird_values) if bird else "",
                     (profile or {}).get((col.table.lower(), col.name.lower()), "")]
            items.append((frag, " || ".join(x for x in parts if x)))
        if len(pk_cols) > 1:  # composite key must be a table constraint
            items.append((f"PRIMARY KEY ({', '.join(quote(c.name) for c in pk_cols)})", ""))
        for col, ref_table, ref_col in table.fks:
            if kept_tables is not None and ref_table.lower() not in kept_tables:
                continue
            ref = f"{quote(ref_table)}({quote(ref_col)})" if ref_col else quote(ref_table)
            items.append((f"FOREIGN KEY ({quote(col)}) REFERENCES {ref}", ""))
        lines = []
        for i, (frag, comment) in enumerate(items):
            sep = "," if i < len(items) - 1 else ""
            lines.append(f"  {frag}{sep}" + (f" -- {comment}" if comment else ""))
        blocks.append(f"CREATE TABLE {quote(table.name)} (\n" + "\n".join(lines) + "\n);")
    return "\n\n".join(blocks)


def _expand_selection(db_id: str, columns: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Selected columns + PKs of their tables + FK columns (both ends) between kept tables."""
    selected = {(t.lower(), c.lower()) for t, c in columns}
    tables = {t for t, _ in selected}
    keep = set(selected)
    for t in load_schema(db_id):
        tl = t.name.lower()
        if tl not in tables:
            continue
        keep |= {(tl, c.name.lower()) for c in t.columns if c.pk}
        for col, ref_table, ref_col in t.fks:
            if ref_table.lower() in tables:
                keep.add((tl, col.lower()))
                if ref_col:
                    keep.add((ref_table.lower(), ref_col.lower()))
    return keep
