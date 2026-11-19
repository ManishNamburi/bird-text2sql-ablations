"""Experiment 08 (D23): the promptfoo-native config must send the pipeline's exact C1 prompt,
and the LLM judge must see no gold and run locally."""

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from birdeval.llm import extract_sql
from birdeval.pipeline import PipelineConfig, build_messages
from birdeval.promptbuild import schema_text
from birdeval.sqlexec import DATA_ROOT

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "promptfoo"))
from asserts import native  # noqa: E402
from prompts import c1  # noqa: E402

HAVE_DATA = (DATA_ROOT / "mini_dev_sqlite.json").exists()
pytestmark = pytest.mark.skipif(not HAVE_DATA, reason="MiniDev not downloaded")
CONFIG = yaml.safe_load((ROOT / "promptfoo/configs/08_native.yaml").read_text())
QUESTIONS = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text()) if HAVE_DATA else []


def _vars(q):
    return {k: q[k] for k in ("question_id", "db_id", "question", "evidence", "difficulty")}


def test_prompt_functions_send_the_pipelines_c1_messages():
    for q in QUESTIONS[::50]:
        v = _vars(q)
        assert json.loads(c1.no_hints({"vars": v})) == build_messages(v, PipelineConfig(metadata="bird"))
        assert json.loads(c1.with_hints({"vars": v})) == build_messages(v, PipelineConfig(metadata="bird", hints=True))


def test_transform_is_the_pipelines_extraction():
    reply = "Here:\n```sql\nSELECT 1;\n```"
    assert native.extract_sql(reply, {}) == extract_sql(reply) == "SELECT 1"


def test_judge_sees_no_gold():
    for q in QUESTIONS:
        v = native.add_schema(_vars(q), {})
        assert set(v) == set(_vars(q)) | {"schema"}
        assert v["schema"] == schema_text(q["db_id"], "bird")
        assert q["SQL"].strip() not in v["schema"]
    judge = next(a for a in CONFIG["defaultTest"]["assert"] if a["type"] == "llm-rubric")
    assert set(re.findall(r"{{\s*(\w+)\s*}}", judge["value"])) == {"schema", "question", "evidence"}


def test_judge_is_pinned_to_local_ollama():
    # Without a grader provider, llm-rubric falls back to promptfoo's remote grading.
    assert CONFIG["defaultTest"]["options"]["provider"]["id"].startswith("ollama:")
