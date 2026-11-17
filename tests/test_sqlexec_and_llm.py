"""Evaluator correctness tests. The metric is the foundation of every result in this
project, so it is tested before any model is run ("eval the eval")."""

import json

import pytest

from birdeval.llm import extract_sql
from birdeval.sqlexec import DATA_ROOT, execute, load_gold, results_match, score_question, timeout_for

QUESTIONS = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text())
FAST = [q for q in QUESTIONS if load_gold()[q["question_id"]]["ms"] < 200]


def test_results_match_is_order_and_duplicate_insensitive():
    assert results_match([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])
    assert results_match([(1,), (1,)], [(1,)])  # BIRD uses set semantics
    assert not results_match([(1, "a")], [("a", 1)])  # column order matters
    assert not results_match([(1,)], [(1,), (2,)])


def test_gold_cache_complete():
    # MiniDev's 500 entries contain 2 exact duplicates (qid 137 and 138), so 498 unique questions.
    gold = load_gold()
    assert len(gold) == len({q["question_id"] for q in QUESTIONS}) == 498


def test_gold_sql_scores_100_percent():
    """Gold vs cached gold must be 100% — otherwise the evaluator (or the data) is broken.
    Uses the fast queries so the suite stays quick; cache_gold.py already ran all 500."""
    for q in FAST:
        s = score_question(q["question_id"], q["db_id"], q["SQL"])
        assert s.match, f"question {q['question_id']} gold does not self-match"


def test_slow_gold_gets_longer_timeout():
    slowest = max(load_gold().items(), key=lambda kv: kv[1]["ms"])[0]
    assert timeout_for(slowest) > 30
    assert timeout_for(FAST[0]["question_id"]) == 30


def test_wrong_sql_scores_zero_and_invalid_sql_flagged():
    q = FAST[0]
    wrong = score_question(q["question_id"], q["db_id"], "SELECT 12345678")
    assert wrong.valid_sql and not wrong.match
    broken = score_question(q["question_id"], q["db_id"], "SELEC nonsense FROM")
    assert not broken.valid_sql and not broken.match and broken.error


def test_databases_are_read_only():
    q = QUESTIONS[0]
    r = execute(q["db_id"], "CREATE TABLE should_fail (x INT)")
    assert not r.ok and "readonly" in r.error.replace(" ", "").lower()


def test_timeout_interrupts_runaway_query():
    q = QUESTIONS[0]
    runaway = (
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c"
    )
    r = execute(q["db_id"], runaway, timeout_s=0.5)
    assert not r.ok and r.error == "timeout"


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("```sql\nSELECT 1;\n```", "SELECT 1"),
        ("Here you go:\n```\nSELECT a FROM t\n```\nDone.", "SELECT a FROM t"),
        ("<think>hmm</think>SELECT 2;", "SELECT 2"),
        ("```sql\nSELECT 1\n```\nrevised:\n```sql\nSELECT 3\n```", "SELECT 3"),
    ],
)
def test_extract_sql(reply, expected):
    assert extract_sql(reply) == expected


def test_cache_only_mode_refuses_misses_but_serves_hits(tmp_path, monkeypatch):
    """run_ablation's combined pass sets BIRDEVAL_CACHE_ONLY=1: a miss must raise before any
    request reaches Ollama, while hits are served as usual."""
    import json

    from birdeval import llm

    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("BIRDEVAL_CACHE_ONLY", "1")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called Ollama")))
    msgs = [{"role": "user", "content": "hi"}]
    with pytest.raises(llm.CacheMiss):
        llm.chat(msgs)
    payload = {"model": llm.DEFAULT_MODEL, "messages": msgs, "stream": False, "think": False,
               "options": {"temperature": 0.0, "seed": 42, "num_ctx": llm.DEFAULT_NUM_CTX, "num_predict": 1024}}
    key = llm._cache_key(payload)
    (tmp_path / key[:2]).mkdir()
    (tmp_path / key[:2] / f"{key}.json").write_text(json.dumps(
        {"text": "ok", "model": llm.DEFAULT_MODEL, "prompt_tokens": 1, "completion_tokens": 1,
         "prompt_ms": 1, "gen_ms": 1, "total_ms": 2}))
    assert llm.chat(msgs).cached
