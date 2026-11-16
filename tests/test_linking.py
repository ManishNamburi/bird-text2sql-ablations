"""Schema linking tests with a stubbed LLM (no Ollama calls), anchored on the paper's
worked example (§3.1). The LLM is faked so the *control flow* - literal checking, revision
prompting, field collection, oracle restriction - is tested deterministically."""

import pytest

import birdeval.linking as linking
import birdeval.pipeline as pipeline
from birdeval.llm import LLMResult
from birdeval.sqlfields import extract_fields
from birdeval.valueindex import index_path

pytestmark = pytest.mark.skipif(not index_path("california_schools").exists(),
                                reason="run scripts/build_indexes.py first")

PAPER_Q = {"question_id": -1, "db_id": "california_schools", "evidence": "",
           "question": "Please list the zip code of all the charter schools in Fresno County Office of Education."}
# Paper §3.1: the first draft constrains the wrong field ...
DRAFT = ("SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode "
         "WHERE T1.`Charter School (Y/N)` = 1 AND T1.`County Name` = 'Fresno County Office of Education'")
# ... and the revision uses a field that contains the literal.
REVISED = ("SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode "
           "WHERE T1.`Charter School (Y/N)` = 1 AND T2.District = 'Fresno County Office of Education'")


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def __call__(self, messages, **kw):
        self.calls.append(messages)
        text = self.replies(messages)
        return LLMResult(f"```sql\n{text}\n```", "fake", 100, 10, 1.0, 1.0, 2.0)


@pytest.fixture
def no_embeddings(monkeypatch):
    # Semantic neighbours are stubbed so tests never call Ollama's embedding endpoint.
    monkeypatch.setattr(linking, "similar_columns",
                        lambda db, text, k: (("frpm", "Charter School (Y/N)", 0.9), ("schools", "Zip", 0.8)))


def test_question_literals_find_paper_fields():
    fields = linking.question_literal_fields("california_schools", PAPER_Q["question"])
    assert {("frpm", "district name"), ("satscores", "dname"), ("schools", "district")} <= fields


def test_paper_example_literal_revision(monkeypatch, no_embeddings):
    fake = FakeLLM(lambda m: REVISED if m[-1]["content"].startswith("Some values") else DRAFT)
    monkeypatch.setattr(linking, "chat", fake)
    res = linking.link(PAPER_Q, model="fake", hints=False, variants=("focused_minimal",), k=15,
                       max_retry=1, num_ctx=24576, seed=42)

    assert len(fake.calls) == 2  # draft + one revision
    trace = res.traces[0]
    assert "Fresno County Office of Education" in trace.missing_literals
    assert any(w.startswith("schools.District") for w in trace.missing_literals["Fresno County Office of Education"])
    assert ("schools", "district") in res.fields and ("frpm", "county name") not in res.fields
    revision_schema = fake.calls[1][1]["content"]  # augmented schema shown for the revision
    assert "District" in revision_schema


def test_no_revision_when_literal_is_in_used_field(monkeypatch, no_embeddings):
    fake = FakeLLM(lambda m: REVISED)
    monkeypatch.setattr(linking, "chat", fake)
    res = linking.link(PAPER_Q, model="fake", hints=False, variants=("focused_minimal", "full_minimal"),
                       k=15, max_retry=1, num_ctx=24576, seed=42)
    assert len(fake.calls) == 2  # one draft per variant, no revisions
    assert all(t.revised_sql is None for t in res.traces)


def test_full_maximal_variant_reuses_the_c2_prompt(monkeypatch, no_embeddings):
    """Same builder -> the linking draft is byte-identical to the C2 prompt (LLM cache hit)."""
    fake = FakeLLM(lambda m: REVISED)
    monkeypatch.setattr(linking, "chat", fake)
    linking.link(PAPER_Q, model="fake", hints=False, variants=("full_maximal",), k=15,
                 max_retry=1, num_ctx=24576, seed=42)
    c2 = pipeline.build_messages(PAPER_Q, pipeline.PipelineConfig(metadata="profile"))
    assert fake.calls[0] == c2


def test_oracle_linking_restricts_final_schema_to_gold_tables(monkeypatch):
    q = {"question_id": 5, "db_id": "california_schools", "evidence": "",
         "question": "How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?"}
    fake = FakeLLM(lambda m: "SELECT 1")
    monkeypatch.setattr(pipeline, "chat", fake)
    out = pipeline.run(q, pipeline.PipelineConfig(metadata="fused", linking="oracle"))
    prompt = fake.calls[0][1]["content"]
    assert "CREATE TABLE satscores" in prompt and "CREATE TABLE schools" in prompt
    assert "CREATE TABLE frpm" not in prompt  # gold SQL does not touch frpm
    assert out.extra["link_recall"] == 1.0


def test_oracle_fields_match_gold_sql():
    gold = linking._gold_sql()[5]
    assert linking.oracle_fields({"question_id": 5, "db_id": "california_schools"}) == extract_fields(gold, "california_schools")


def test_config_rejects_unknown_variant():
    with pytest.raises(ValueError):
        pipeline.PipelineConfig(linking="llm", link_variants=["focused_minimal", "typo"])
