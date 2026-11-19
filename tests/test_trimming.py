"""Prompt trims T1-T4 (D21): each is one PipelineConfig flag, and touches only the final call."""

import dataclasses
import json

import pytest

import birdeval.linking as lk
import birdeval.pipeline as pl
from birdeval import prompts
from birdeval.llm import LLMResult
from birdeval.profiling import MASK, load_summaries, mask_literals
from birdeval.sqlchecks import Issue, correction_messages
from birdeval.sqlexec import DATA_ROOT

BASE = pl.PipelineConfig(metadata="fused")  # C3
TRIMS = {
    "T1": dataclasses.replace(BASE, profile_detail="short"),
    "T2": dataclasses.replace(BASE, profile_values=False),
    "T3": dataclasses.replace(BASE, bird_values=False),
    "T4": dataclasses.replace(BASE, system="minimal"),
}


def _question(db="california_schools"):
    qs = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text())
    return next(q for q in qs if q["db_id"] == db)


@pytest.mark.parametrize("text, expected", [
    ("values 'D' (520) and 'S' (1749).", f"values {MASK} (520) and {MASK} (1749)."),
    ("Examples include 'St. Mary's Middle', 'Oak'.", f"Examples include {MASK}, {MASK}."),  # inner apostrophe
    ("the school's status is 'Active'", f"the school's status is {MASK}"),  # possessive is not a literal
    ("codes ('0', '16') and 'negative'", f"codes ({MASK}, {MASK}) and {MASK}"),
    ("such as 'http://en.wikipedia.org/wiki/1950_Belgian_Grand_Prix'.", f"such as {MASK}."),
    ("It's a code with no literals", "It's a code with no literals"),
])
def test_mask_literals(text, expected):
    assert mask_literals(text) == expected


@pytest.mark.needs_data
def test_masking_keeps_everything_but_values():
    s = load_summaries("california_schools")[("satscores", "rtype")]
    m = mask_literals(s)
    assert "'D'" in s and "'D'" not in m and "'S'" not in m
    assert [w for w in s.split() if "'" not in w] == [w for w in m.split() if "'" not in w]


def test_each_trim_is_one_field_away_from_the_base():
    base = dataclasses.asdict(BASE)
    for name, cfg in TRIMS.items():
        diff = {k for k, v in dataclasses.asdict(cfg).items() if base[k] != v}
        assert len(diff) == 1, (name, diff)


@pytest.mark.needs_data
def test_each_trim_changes_only_its_section_and_shortens_the_prompt():
    q = _question()
    base = pl.build_messages(q, BASE)
    assert base[0]["content"] == prompts.SYSTEM
    for name, cfg in TRIMS.items():
        m = pl.build_messages(q, cfg)
        assert len(m[0]["content"]) + len(m[1]["content"]) < len(base[0]["content"]) + len(base[1]["content"]), name
        if name == "T4":
            assert m[0]["content"] == prompts.SYSTEM_MINIMAL and m[1] == base[1]
        else:
            assert m[0] == base[0] and m[1] != base[1]
    t2 = pl.build_messages(q, TRIMS["T2"])[1]["content"]
    assert MASK in t2 and "'2014-2015'" in base[1]["content"] and "'2014-2015'" not in t2
    t3 = pl.build_messages(q, TRIMS["T3"])[1]["content"]
    assert "| values: " in base[1]["content"] and "| values: " not in t3


def test_unknown_system_fails_loudly():
    with pytest.raises(ValueError):
        pl.PipelineConfig(system="short")


@pytest.mark.needs_data
def test_minimal_system_reaches_corrections():
    msgs = pl.build_messages(_question(), TRIMS["T4"])
    out = correction_messages(msgs, "SELECT 1", [Issue("concat", "x", "msg")])
    assert out[0]["content"] == prompts.SYSTEM_MINIMAL


@pytest.mark.needs_data
def test_linking_prompts_ignore_the_system_trim(monkeypatch):
    log = []

    def chat(msgs, **kw):
        log.append(msgs)
        return LLMResult("```sql\nSELECT CDSCode FROM frpm\n```", "m", 10, 5, 1.0, 1.0, 2.0)

    monkeypatch.setattr(pl, "chat", chat)
    monkeypatch.setattr(lk, "chat", chat)
    monkeypatch.setattr(lk, "focused_fields", lambda *a: set())  # no embedding call needed
    cfg = dataclasses.replace(TRIMS["T4"], linking="llm", link_variants=("full_minimal",))
    pl.run(_question(), cfg)
    assert [m[0]["content"] for m in log] == [prompts.SYSTEM, prompts.SYSTEM_MINIMAL]
