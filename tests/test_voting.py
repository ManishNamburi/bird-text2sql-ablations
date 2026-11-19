"""C6: majority vote on execution results, and the candidate calls the pipeline makes."""

import json
import re

import pytest

import birdeval.pipeline as pl
from birdeval.llm import LLMResult
from birdeval.sqlexec import DATA_ROOT
from birdeval.voting import pick, vote

A, B = frozenset({(1,)}), frozenset({(2,)})


def test_pick_majority_ties_and_failures():
    assert pick([A, B, B]) == (1, [1, 2, 2])  # two agree -> one of them
    assert pick([A, None, A]) == (0, [2, 0, 2])
    assert pick([A, B, frozenset()]) == (0, [1, 1, 1])  # no majority -> candidate 0
    assert pick([None, A, B]) == (1, [0, 1, 1])  # failures don't vote; lowest valid wins the tie
    assert pick([None, None, None]) == (0, [0, 0, 0])  # nothing executes -> candidate 0


@pytest.mark.needs_data
def test_vote_executes_and_ignores_invalid_sql():
    v = vote("california_schools", ["SELECT 1", "SELECT 2", "SELECT 2"])
    assert (v.winner, v.groups) == (1, [1, 2, 2])
    v = vote("california_schools", ["SELEC nonsense", "SELECT 2", ""])
    assert (v.winner, v.groups) == (1, [0, 1, 0])
    # Row order and duplicates don't matter (BIRD EX equality).
    v = vote("california_schools", ["SELECT 1 UNION ALL SELECT 2", "SELECT 2 UNION SELECT 1", "SELECT 3"])
    assert v.groups == [2, 2, 1]


def _question():
    qs = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text())
    return next(q for q in qs if q["db_id"] == "california_schools")


def _fake_chat(log, sql_by_seed):
    def chat(msgs, **kw):
        log.append({"msgs": msgs, **kw})
        return LLMResult(f"```sql\n{sql_by_seed[kw['seed']]}\n```", "m", 10, 5, 1.0, 1.0, 2.0)
    return chat


@pytest.mark.needs_data
def test_pipeline_candidates_and_vote(monkeypatch):
    log = []
    monkeypatch.setattr(pl, "chat", _fake_chat(log, {42: "SELECT 1", 43: "SELECT 2", 44: "SELECT 2"}))
    cfg = pl.PipelineConfig(metadata="fused", linking="oracle", votes=3, vote_temperature=0.7)
    q = _question()
    res = pl.run(q, cfg)

    # Candidate 0 is exactly the single-candidate call: same messages, no temperature override.
    assert "temperature" not in log[0]
    assert log[0]["msgs"] == pl.build_messages(q, pl.PipelineConfig(metadata="fused", linking="oracle"),
                                               pl.oracle_fields(q))
    assert [c["seed"] for c in log] == [42, 43, 44]
    assert [c.get("temperature") for c in log[1:]] == [0.7, 0.7]
    # Shuffled candidates hold the same schema lines (modulo separator commas), reordered.
    def lines(c):
        return [re.sub(r",( --|$)", r"\1", ln) for ln in c["msgs"][1]["content"].splitlines()]
    assert sorted(lines(log[0])) == sorted(lines(log[1])) == sorted(lines(log[2]))
    assert lines(log[0]) != lines(log[1]) != lines(log[2])

    assert res.sql == "SELECT 2" and res.messages == log[1]["msgs"]
    assert res.extra["vote_winner"] == 1 and res.extra["vote_groups"] == [1, 2, 2]
    assert res.extra["vote_unanimous"] is False and res.extra["vote_distinct_sql"] == 2
    assert len(res.calls) == 3


@pytest.mark.needs_data
def test_single_candidate_path_is_unchanged(monkeypatch):
    log = []
    monkeypatch.setattr(pl, "chat", _fake_chat(log, {42: "SELECT 1"}))
    res = pl.run(_question(), pl.PipelineConfig(metadata="fused", linking="oracle"))
    assert len(log) == 1 and "temperature" not in log[0]
    assert not any(k.startswith(("vote", "check")) for k in res.extra)


def test_vote_temperature_is_normalized_for_the_cache_key():
    # YAML `vote_temperature: 0` is an int; 0 and 0.0 serialize differently in the cache key.
    assert isinstance(pl.PipelineConfig(votes=3, vote_temperature=0).vote_temperature, float)
