"""C7 detectors (paper §4 SQL sanity checks) on hand-written SQL against a real database."""

import pytest

from birdeval.sqlchecks import check_sql, correction_messages, has_nulls

pytestmark = pytest.mark.needs_data
DB = "california_schools"  # schools.ClosedDate has NULLs; schools.CDSCode has none


def checks(sql):
    return [(i.check, i.field) for i in check_sql(sql, DB)]


def test_null_guard_uses_the_data():
    assert has_nulls(DB, "schools", "ClosedDate") and not has_nulls(DB, "schools", "CDSCode")


@pytest.mark.parametrize("sql, expected", [
    ("SELECT T1.School FROM schools AS T1 ORDER BY T1.ClosedDate LIMIT 1", [("null_order", "schools.ClosedDate")]),
    ("SELECT School FROM schools ORDER BY ClosedDate ASC LIMIT 1", [("null_order", "schools.ClosedDate")]),
    ("SELECT School FROM schools WHERE ClosedDate IS NOT NULL ORDER BY ClosedDate LIMIT 1", []),
    ("SELECT School FROM schools WHERE NOT ClosedDate IS NULL ORDER BY ClosedDate LIMIT 1", []),
    ("SELECT School FROM schools WHERE ClosedDate > '2000-01-01' ORDER BY ClosedDate LIMIT 1", []),
    ("SELECT School FROM schools ORDER BY ClosedDate DESC LIMIT 1", []),
    ("SELECT School FROM schools ORDER BY CDSCode LIMIT 1", []),  # no NULLs in the data
    ("SELECT MIN(ClosedDate) FROM schools", [("null_min", "schools.ClosedDate")]),
    ("SELECT MIN(T.ClosedDate) FROM schools T WHERE T.ClosedDate IS NOT NULL", []),
    ("SELECT School FROM schools WHERE ClosedDate = (SELECT MAX(ClosedDate) FROM schools)", [("minmax_subquery", "MAX")]),
    ("SELECT School FROM schools WHERE CDSCode IN (SELECT MIN(CDSCode) FROM schools)", [("minmax_subquery", "MIN")]),
    ("SELECT City || ', ' || State FROM schools", [("concat", "output")]),
    ("SELECT 'a' || 'b' FROM schools", []),  # no fields involved
    ("SELECT City FROM schools WHERE City || State = 'x'", []),  # not in the output
    ("SELECT City || State FROM schools UNION SELECT School FROM schools", [("concat", "output")]),
    ("SELEC nonsense", []),
])
def test_detectors(sql, expected):
    assert checks(sql) == expected


def test_null_check_is_per_select():
    # The NOT NULL filter in the subquery does not cover the outer ORDER BY.
    sql = ("SELECT School FROM schools WHERE CDSCode IN (SELECT CDSCode FROM schools WHERE ClosedDate IS NOT NULL) "
           "ORDER BY ClosedDate LIMIT 1")
    assert ("null_order", "schools.ClosedDate") in checks(sql)


def test_correction_messages_extend_the_candidate_conversation():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    issues = check_sql("SELECT MIN(ClosedDate) FROM schools", DB)
    out = correction_messages(msgs, "SELECT MIN(ClosedDate) FROM schools", issues)
    assert out[:2] == msgs and out[2]["role"] == "assistant" and "SELECT MIN" in out[2]["content"]
    assert out[3]["role"] == "user" and "IS NOT NULL" in out[3]["content"]


# --- correction loop (pipeline.correct) ---------------------------------------------

import birdeval.pipeline as pl  # noqa: E402
from birdeval.llm import LLMResult  # noqa: E402

FLAGGED = "SELECT School FROM schools ORDER BY ClosedDate LIMIT 1"
FIXED = "SELECT School FROM schools WHERE ClosedDate IS NOT NULL ORDER BY ClosedDate LIMIT 1"
Q = {"question_id": 0, "db_id": DB, "question": "q"}


def _scripted(monkeypatch, replies):
    log = []

    def chat(msgs, **kw):
        log.append(msgs)
        return LLMResult(f"```sql\n{replies[len(log) - 1]}\n```", "m", 1, 1, 1.0, 1.0, 1.0)
    monkeypatch.setattr(pl, "chat", chat)
    return log


def test_correction_adopts_a_fix(monkeypatch):
    log = _scripted(monkeypatch, [FIXED])
    calls = []
    sql, t = pl.correct(Q, pl.PipelineConfig(checks=True), [{"role": "user", "content": "u"}], FLAGGED, 42, calls)
    assert sql == FIXED and t["fired"] == ["null_order"] and t["remaining"] == [] and t["retries"] == 1
    assert len(calls) == 1 and log[0][-2]["role"] == "assistant" and FLAGGED in log[0][-2]["content"]


def test_correction_rejects_a_revision_that_breaks_execution(monkeypatch):
    _scripted(monkeypatch, ["SELECT nope FROM nowhere"])
    sql, t = pl.correct(Q, pl.PipelineConfig(checks=True), [], FLAGGED, 42, [])
    assert sql == FLAGGED and t["retries"] == 1 and not t["changed"]


def test_correction_stops_on_unchanged_and_caps_retries(monkeypatch):
    _scripted(monkeypatch, [FLAGGED])
    sql, t = pl.correct(Q, pl.PipelineConfig(checks=True), [], FLAGGED, 42, [])
    assert sql == FLAGGED and t["retries"] == 1  # a T=0 retry would repeat itself
    still_flagged = [f"SELECT School FROM schools ORDER BY ClosedDate LIMIT {n}" for n in (2, 3, 4, 5)]
    _scripted(monkeypatch, still_flagged)
    sql, t = pl.correct(Q, pl.PipelineConfig(checks=True), [], FLAGGED, 42, [])
    assert t["retries"] == 3 and sql == still_flagged[2] and t["remaining"] == ["null_order"]


def test_clean_sql_costs_no_call(monkeypatch):
    log = _scripted(monkeypatch, [])
    sql, t = pl.correct(Q, pl.PipelineConfig(checks=True), [], FIXED, 42, [])
    assert sql == FIXED and t["retries"] == 0 and log == []
