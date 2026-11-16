"""The value index must reproduce the paper's worked example (§3.1) and fix the literal
mismatches we observed on the dev slice."""

import pytest

from birdeval.valueindex import index_path, jaccard, lookup, shingles

pytestmark = pytest.mark.skipif(not index_path("california_schools").exists(),
                                reason="run scripts/build_indexes.py first")


def fields(db, literal):
    return {f"{m.table}.{m.column}" for m in lookup(db, literal)}


def test_paper_example_fresno():
    # Paper §3.1: the literal occurs in frpm.`District Name`, satscores.dname, schools.District
    assert {"frpm.District Name", "satscores.dname", "schools.District"} <= fields(
        "california_schools", "Fresno County Office of Education")


@pytest.mark.parametrize("db, literal, field", [
    ("card_games", "Coldsnap", "sets.name"),  # dev q486: model used cards.setCode
    ("card_games", "banned", "legalities.status"),  # dev q522: stored as 'Banned'
    ("codebase_community", "csgillespie", "users.DisplayName"),  # dev q537
])
def test_dev_slice_literal_mismatches_are_resolved(db, literal, field):
    assert field in fields(db, literal)


def test_shingles_are_case_and_space_insensitive():
    assert jaccard(shingles("Marvel  Comics"), shingles("marvel comics")) == 1.0
    assert shingles("ab") == {"ab"}
