"""SQL sanity checks (paper §4, C7): constructions "likely to indicate an incorrect response".

The paper names four; each detector returns Issues that the correction prompt spells out.
  null_order       ascending ORDER BY on a column f with no NULL-excluding predicate on f
  null_min         MIN(f) in the select list, same condition
  minmax_subquery  min/max via a nested subquery (`f = (SELECT MAX(f) ...)`), not ORDER BY ... LIMIT
  concat           string concatenation of fields in the output (`||`, CONCAT)
The NULL checks fire only if f actually holds NULLs in the database (declared deviation, D20):
otherwise a correction costs a call and cannot change the result.

Detectors work on sqlglot's AST, with aliases (T1.x) and unqualified columns resolved to base
tables through the same qualifier as schema linking. Unparseable SQL yields no issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sqlglot import exp

from birdeval.sqlexec import execute
from birdeval.sqlfields import _parse, _schema, qualify

CHECKS = ("null_order", "null_min", "minmax_subquery", "concat")

# Predicates that are never true for NULL f: if f appears directly in one, NULLs are excluded.
_NULL_EXCLUDING = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like, exp.ILike,
                   exp.In, exp.Between, exp.Glob)


@dataclass(frozen=True)
class Issue:
    check: str
    field: str  # "table.column" (real case) or a short SQL fragment
    message: str


@lru_cache(maxsize=None)
def has_nulls(db_id: str, table: str, column: str) -> bool:
    r = execute(db_id, f'SELECT 1 FROM "{table}" WHERE "{column}" IS NULL LIMIT 1', timeout_s=30)
    return bool(r.ok and r.rows)


class _Resolver:
    """Maps column references to (real table, real column) for one query."""

    def __init__(self, tree: exp.Expression, db_id: str):
        mapping, cols = _schema(db_id)
        self.real = {t.lower(): (t, {c.lower(): c for c in cs}) for t, cs in mapping.items()}
        self.alias: dict[str, str] = {}
        for t in tree.find_all(exp.Table):
            name = t.name.lower()
            if name in cols:
                self.alias[(t.alias_or_name or name).lower()] = name
                self.alias.setdefault(name, name)
        self.tables = set(self.alias.values())

    def __call__(self, c: exp.Column) -> tuple[str, str] | None:
        col = c.name.lower()
        if c.table:
            t = self.alias.get(c.table.lower())
            cands = [t] if t else []
        else:
            cands = [t for t in self.tables if col in self.real[t][1]]
        if len(cands) != 1 or col not in self.real[cands[0]][1]:
            return None
        table, cols = self.real[cands[0]]
        return table, cols[col]


def _null_excluded(select: exp.Select, key: tuple[str, str], resolve: _Resolver) -> bool:
    """True if a WHERE / JOIN ON / HAVING predicate of this SELECT rules out NULL for the field."""
    conds = [select.args.get("where"), select.args.get("having")]
    conds += [j.args.get("on") for j in select.args.get("joins") or []]
    for cond in filter(None, conds):
        for c in cond.find_all(exp.Column):
            if c.find_ancestor(exp.Select) is not select or resolve(c) != key:
                continue  # a subquery's filter does not cover this SELECT
            p = c.parent
            while isinstance(p, (exp.Paren, exp.Cast, exp.Lower, exp.Upper, exp.Trim, exp.Substring)):
                p = p.parent
            if isinstance(p, exp.Not) or (isinstance(p, exp.Is) and isinstance(p.parent, exp.Not)):
                return True  # f IS NOT NULL / NOT (f IS NULL)
            if isinstance(p, _NULL_EXCLUDING):
                return True
    return False


def _outer_selects(tree: exp.Expression) -> list[exp.Select]:
    if isinstance(tree, exp.Select):
        return [tree]
    if isinstance(tree, exp.SetOperation):  # UNION / INTERSECT / EXCEPT
        return _outer_selects(tree.left) + _outer_selects(tree.right)
    return []


def check_sql(sql: str, db_id: str, checks: tuple[str, ...] = CHECKS) -> list[Issue]:
    tree = _parse(sql)
    if tree is None:
        return []
    mapping, _ = _schema(db_id)
    try:
        tree = qualify(tree, schema=mapping, dialect="sqlite", validate_qualify_columns=False,
                       quote_identifiers=False, identify=False)
    except Exception:  # noqa: BLE001 - fall back to the unqualified tree
        pass
    resolve = _Resolver(tree, db_id)
    issues: list[Issue] = []

    def add(check: str, field: str, message: str) -> None:
        if check in checks and not any(i.check == check and i.field == field for i in issues):
            issues.append(Issue(check, field, message))

    for select in tree.find_all(exp.Select):
        order = select.args.get("order")
        for o in (order.expressions if order else []):
            if o.args.get("desc") or not isinstance(o.this, exp.Column):
                continue
            key = resolve(o.this)
            if key and has_nulls(db_id, *key) and not _null_excluded(select, key, resolve):
                f = f"{key[0]}.{key[1]}"
                add("null_order", f, f"The query sorts `{f}` in ascending order, but `{f}` contains NULLs, "
                    "and SQLite sorts NULLs first. Add `IS NOT NULL` on it unless NULL rows belong in the answer.")
        for m in (n for e in select.expressions for n in e.find_all(exp.Min)):
            if not isinstance(m.this, exp.Column) or m.find_ancestor(exp.Select) is not select:
                continue
            key = resolve(m.this)
            if key and has_nulls(db_id, *key) and not _null_excluded(select, key, resolve):
                f = f"{key[0]}.{key[1]}"
                add("null_min", f, f"The query takes MIN(`{f}`), but `{f}` contains NULLs. "
                    "Add `IS NOT NULL` on it unless NULL rows belong in the answer.")

    for cmp in tree.find_all(exp.EQ, exp.In):
        sub = cmp.args.get("query") if isinstance(cmp, exp.In) else next(
            (s for s in (cmp.left, cmp.right) if isinstance(s, exp.Subquery)), None)
        inner = sub.this if isinstance(sub, exp.Subquery) else sub
        if isinstance(inner, exp.Select) and len(inner.expressions) == 1:
            agg = inner.expressions[0].unalias()
            if isinstance(agg, (exp.Max, exp.Min)):
                kind = "MAX" if isinstance(agg, exp.Max) else "MIN"
                add("minmax_subquery", kind, f"The query finds a {kind.lower()}imum with a nested subquery "
                    f"(`... = (SELECT {kind}(...) ...)`). Use ORDER BY ... LIMIT 1 instead, "
                    "unless the question asks for every tied row.")

    for select in _outer_selects(tree):
        for e in select.expressions:
            for node in e.find_all(exp.DPipe, exp.Concat, exp.ConcatWs):
                if any(True for _ in node.find_all(exp.Column)):
                    add("concat", "output", "The query concatenates fields into one output string "
                        "(`||` or CONCAT). Return them as separate columns instead, unless the question "
                        "asks for a single combined string.")
    return issues


CORRECTION = ("Review this query. These problems were found:\n{problems}\n"
              "Reply with only the corrected SQL query in a ```sql code block.")


def correction_messages(messages: list[dict], sql: str, issues: list[Issue]) -> list[dict]:
    """The candidate's own conversation, its SQL as the assistant turn, then the problems."""
    problems = "\n".join(f"- {i.message}" for i in issues)
    return [*messages, {"role": "assistant", "content": f"```sql\n{sql}\n```"},
            {"role": "user", "content": CORRECTION.format(problems=problems)}]
