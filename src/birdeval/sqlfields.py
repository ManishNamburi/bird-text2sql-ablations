"""Extract the (table, column) fields and string literals a SQL query references.

Used by schema linking (paper §3: "collect the fields and literals in the generated query")
and by oracle linking (fields of the gold SQL). Resolution uses sqlglot's qualifier with
the real schema, so aliases (T1.x), unqualified columns and subqueries resolve to base
tables. Model-generated SQL can be invalid; extraction is then best-effort, never raising.
"""

from __future__ import annotations

from functools import lru_cache

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

from birdeval.schema import load_schema

Field = tuple[str, str]  # (table_lower, column_lower)


@lru_cache(maxsize=None)
def _schema(db_id: str) -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    """sqlglot schema mapping {table: {column: type}} and {table_lower: {column_lower}}."""
    mapping, cols = {}, {}
    for t in load_schema(db_id):
        mapping[t.name] = {c.name: (c.type or "TEXT") for c in t.columns}
        cols[t.name.lower()] = {c.name.lower() for c in t.columns}
    return mapping, cols


def _parse(sql: str) -> exp.Expression | None:
    try:
        return sqlglot.parse_one(sql, read="sqlite")
    except Exception:  # noqa: BLE001 - invalid model SQL is expected
        return None


def extract_fields(sql: str, db_id: str) -> set[Field]:
    """Real (table, column) pairs referenced anywhere in the query, lowercased."""
    tree = _parse(sql)
    if tree is None:
        return set()
    mapping, cols = _schema(db_id)
    try:
        tree = qualify(tree, schema=mapping, dialect="sqlite", validate_qualify_columns=False,
                       quote_identifiers=False, identify=False)
    except Exception:  # noqa: BLE001 - fall back to the unqualified tree
        pass

    alias_to_table: dict[str, str] = {}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name in cols:
            alias_to_table[(t.alias_or_name or name).lower()] = name
            alias_to_table.setdefault(name, name)
    query_tables = set(alias_to_table.values())

    fields: set[Field] = set()
    for c in tree.find_all(exp.Column):
        col = c.name.lower()
        table = alias_to_table.get(c.table.lower()) if c.table else None
        if table and col in cols[table]:
            fields.add((table, col))
        else:  # unresolved: attribute to every query table that has this column
            fields.update((t, col) for t in query_tables if col in cols[t])
    return fields


def extract_literals(sql: str) -> list[str]:
    """String literals in the query, with LIKE wildcards stripped, deduplicated in order."""
    tree = _parse(sql)
    if tree is None:
        return []
    out: list[str] = []
    for lit in tree.find_all(exp.Literal):
        if lit.is_string:
            v = lit.this.strip("%").strip()
            if v and v not in out:
                out.append(v)
    return out
