"""The rendered schema is what the model sees, so it must be faithful to the real DB."""

import sqlite3

import pytest

from birdeval.schema import load_schema, quote, render
from birdeval.sqlexec import DB_ROOT, db_path

DBS = sorted(p.name for p in DB_ROOT.iterdir() if p.is_dir())


def _columns(con) -> dict[str, list[str]]:
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {t: [c[1] for c in con.execute(f"PRAGMA table_info({quote(t)})")] for t in tables}


@pytest.mark.parametrize("db_id", DBS)
@pytest.mark.parametrize("bird", [False, True])
def test_rendered_schema_is_valid_sqlite_and_matches_db(db_id, bird):
    """Executing the rendered DDL (comments included) must recreate the exact tables/columns."""
    mem = sqlite3.connect(":memory:")
    mem.executescript(render(db_id, bird=bird))
    real = sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True)
    assert _columns(mem) == _columns(real)


def test_bird_metadata_only_adds_comments():
    """C0 -> C1 must change nothing but the comments (one variable at a time)."""
    for db_id in DBS:
        strip = lambda s: "\n".join(line.split(" -- ")[0] for line in s.splitlines())
        assert strip(render(db_id, bird=True)) == render(db_id)


def test_reserved_word_and_space_identifiers_are_quoted():
    assert quote("order") == "`order`"
    assert quote("Academic Year") == "`Academic Year`"
    assert quote("CDSCode") == "CDSCode"


def test_every_db_has_some_bird_metadata():
    for db_id in DBS:
        assert any(c.bird_desc for t in load_schema(db_id) for c in t.columns), db_id


def test_profile_and_fused_metadata_only_add_comments():
    """C2/C3 must also differ from C0 only in comments; fused = BIRD || profile."""
    strip = lambda s: "\n".join(line.split(" -- ")[0] for line in s.splitlines())
    for db_id in DBS:
        fake = {(c.table.lower(), c.name.lower()): f"profile of {c.name}" for t in load_schema(db_id) for c in t.columns}
        assert strip(render(db_id, profile=fake)) == render(db_id)
        assert strip(render(db_id, bird=True, profile=fake)) == render(db_id)
    fused = render("superhero", bird=True, profile={("superhero", "full_name"): "PROFILE"})
    line = next(l for l in fused.splitlines() if l.strip().startswith("full_name"))
    assert line.endswith(" || PROFILE") and "the full name of the superhero" in line


def test_column_selection_keeps_keys_and_is_valid_sql():
    sel = {("frpm", "charter school (y/n)"), ("schools", "zip")}
    out = render("california_schools", columns=sel)
    mem = sqlite3.connect(":memory:")
    mem.executescript(out)  # still valid SQL
    tables = {r[0] for r in mem.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"frpm", "schools"}  # satscores dropped
    assert "CDSCode" in out and "FOREIGN KEY (CDSCode) REFERENCES schools(CDSCode)" in out  # join key kept
    assert "AdmFName1" not in out  # unselected column dropped


def test_shuffle_changes_order_not_content():
    tokens = lambda s: sorted(s.replace(",", "").split())
    base = render("european_football_2")
    shuffled = [render("european_football_2", shuffle_seed=s) for s in (1, 2)]
    assert shuffled[0] != base and shuffled[0] != shuffled[1]  # order actually changes
    assert all(tokens(s) == tokens(base) for s in shuffled)  # same columns, nothing lost
    assert render("european_football_2", shuffle_seed=1) == shuffled[0]  # deterministic per seed
