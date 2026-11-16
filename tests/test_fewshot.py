"""Few-shot pools and retrieval. Leakage checks are the most important tests here: an eval
question (or its exact SQL) appearing in a pool would inflate C5 for the wrong reason."""

import json

import numpy as np
import pytest

import birdeval.fewshot as fs
from birdeval import prompts
from birdeval.llm import LLMResult
from birdeval.sqlexec import DATA_ROOT

pytestmark = pytest.mark.skipif(not (fs.TRAIN_FILE.exists() and fs.DEV_FILE.exists()),
                                reason="few-shot source data not downloaded")
MINIDEV = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text())


def test_pools_do_not_leak_eval_questions():
    pools = fs.load_pools()
    eval_ids = {q["question_id"] for q in MINIDEV}
    eval_sql = {fs._norm_sql(q["SQL"]) for q in MINIDEV}
    eval_dbs = {q["db_id"] for q in MINIDEV}
    assert not {int(r["id"].split(":")[1]) for r in pools["querylog"]} & eval_ids
    assert not {fs._norm_sql(r["SQL"]) for r in pools["querylog"]} & eval_sql
    assert not {r["db_id"] for r in pools["train"]} & eval_dbs  # train = other databases
    assert len(pools["train"]) == 6601 and len(pools["querylog"]) == 1035


def _fake_chat(n_returned):
    def chat(messages, **kw):
        n = n_returned if n_returned is not None else 1
        return LLMResult(json.dumps({"masked": [f"m{i}" for i in range(n)]}), "fake", 1, 1, 1, 1, 1)
    return chat


def test_mask_batch_accepts_correct_count(monkeypatch):
    monkeypatch.setattr(fs, "chat", _fake_chat(3))
    assert fs.mask_batch(["a", "b", "c"]) == ["m0", "m1", "m2"]


def test_mask_batch_falls_back_per_item_on_wrong_count(monkeypatch):
    calls = []

    def chat(messages, **kw):
        calls.append(messages)
        n = 2 if len(calls) == 1 else 1  # batch reply is short by one -> per-item retries
        return LLMResult(json.dumps({"masked": ["x"] * n}), "fake", 1, 1, 1, 1, 1)

    monkeypatch.setattr(fs, "chat", chat)
    assert fs.mask_batch(["a", "b", "c"]) == ["x", "x", "x"]
    assert len(calls) == 4  # 1 batch + 3 single


def test_querylog_retrieval_stays_in_the_questions_database(tmp_path, monkeypatch):
    rows = [{"id": "dev:1", "db_id": "superhero", "question": "q1", "evidence": "", "SQL": "S1"},
            {"id": "dev:2", "db_id": "toxicology", "question": "q2", "evidence": "", "SQL": "S2"},
            {"id": "dev:3", "db_id": "superhero", "question": "q3", "evidence": "", "SQL": "S3"}]
    monkeypatch.setattr(fs, "FEWSHOT_DIR", tmp_path)
    monkeypatch.setattr(fs, "load_pools", lambda: {"querylog": rows, "train": rows})
    np.savez(tmp_path / "querylog.npz", ids=np.array([r["id"] for r in rows]),
             vecs=np.array([[1.0, 0.0], [1.0, 0.0], [0.6, 0.8]], dtype=np.float32))
    np.savez(tmp_path / "minidev.npz", ids=np.array(["mini:99"]), vecs=np.array([[1.0, 0.0]], dtype=np.float32))
    fs._pool.cache_clear(); fs._eval_vectors.cache_clear()
    try:
        got = fs.examples_for({"question_id": 99, "db_id": "superhero"}, "querylog", k=5)
    finally:
        fs._pool.cache_clear(); fs._eval_vectors.cache_clear()
    assert [e["id"] for e in got] == ["dev:1", "dev:3"]  # toxicology excluded despite equal similarity


def test_few_shot_block_placement_and_hints():
    ex = [{"question": "Q?", "evidence": "E", "SQL": "SELECT 1"}]
    with_hints = prompts.user_message("SCHEMA", "Real?", "H", prompts.few_shot_block(ex, True, True))
    assert with_hints.index("SCHEMA") < with_hints.index("Examples") < with_hints.index("Question: Real?")
    assert "Hint: E" in with_hints and "other databases" in with_hints
    no_hints = prompts.few_shot_block(ex, False, False)
    assert "Hint" not in no_hints and "this database" in no_hints
    assert prompts.user_message("S", "Q") == "Database schema:\nS\n\nQuestion: Q"  # unchanged without examples
