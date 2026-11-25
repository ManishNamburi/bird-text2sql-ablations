"""Few-shot example retrieval via masked-question similarity (paper §4, after [LPKP24]).

Every question (pool and eval) is rewritten by the LLM with names/values/numbers/dates
replaced by placeholders, so retrieval matches question *shape* ("How many <name> cards
have power <number>?") rather than topic. Masked questions are embedded; for an eval
question we return the k pool examples with the most similar masked question.

Two pools (docs/decisions.md D16):
  train     BIRD train (filtered): 6,601 pairs over 69 OTHER databases  - paper setup
  querylog  BIRD dev minus every MiniDev question (and SQL-identical leaks): ~1,035 pairs
            on the SAME 11 databases, retrieved within the question's database - the
            paper's §5-6 "query log" scenario
Masking runs in batches of the same source (scripts/build_fewshot.py); eval questions are
masked from their text only, never their SQL.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from birdeval.embed import embed
from birdeval.llm import DEFAULT_MODEL, chat
from birdeval.profiling import DERIVED
from birdeval.sqlexec import DATA_ROOT

ROOT = Path(__file__).resolve().parents[2]
FEWSHOT_DIR = DERIVED / "fewshot"
TRAIN_FILE = ROOT / "data" / "raw" / "bird_train" / "train.jsonl"
DEV_FILE = ROOT / "data" / "raw" / "bird_dev" / "dev_20251106.json"
BATCH = 25

MASK_SYSTEM = "You turn database questions into templates by masking specific values."
MASK_INSTRUCTIONS = """Replace every specific name, entity, title, code, literal value, number and date in each question with a placeholder: <name>, <value>, <number> or <date>. Keep all other words and the sentence structure exactly as they are.
Example: "How many cards illustrated by Stephen Daniel have a power of 5?" -> "How many cards illustrated by <name> have a power of <number>?"
Return JSON {"masked": [...]} with exactly one masked question per input, in the same order.

Questions:
"""


def _norm_sql(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower().rstrip(";"))


def load_pools() -> dict[str, list[dict]]:
    """{'train': [...], 'querylog': [...]} with keys id, db_id, question, evidence, SQL."""
    train = [json.loads(line) for line in TRAIN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    train = [{**r, "id": f"train:{i}"} for i, r in enumerate(train)]
    minidev = json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text(encoding="utf-8"))
    eval_ids = {q["question_id"] for q in minidev}
    eval_sql = {_norm_sql(q["SQL"]) for q in minidev}
    dev = json.loads(DEV_FILE.read_text(encoding="utf-8"))
    querylog = [{**r, "id": f"dev:{r['question_id']}"} for r in dev
                if r["question_id"] not in eval_ids and _norm_sql(r["SQL"]) not in eval_sql]
    return {"train": train, "querylog": querylog}


def mask_batch(questions: list[str], model: str = DEFAULT_MODEL) -> list[str]:
    """Mask a batch with one LLM call; falls back to one call per question if the model
    returns the wrong number of items."""
    listing = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    schema = {"type": "object", "required": ["masked"],
              "properties": {"masked": {"type": "array", "items": {"type": "string"}}}}
    r = chat([{"role": "system", "content": MASK_SYSTEM},
              {"role": "user", "content": MASK_INSTRUCTIONS + listing}],
             model=model, format=schema, num_predict=60 * len(questions) + 100)
    try:
        out = json.loads(r.text)["masked"]
    except (json.JSONDecodeError, KeyError, TypeError):
        out = []
    if len(out) == len(questions) and all(isinstance(x, str) and x.strip() for x in out):
        return [x.strip() for x in out]
    if len(questions) == 1:
        return [questions[0]]  # give up gracefully: unmasked text still embeds
    return [m for q in questions for m in mask_batch([q], model)]


def _path(name: str) -> Path:
    return FEWSHOT_DIR / f"{name}.json"


def save_masked(name: str, ids: list[str], masked: list[str]) -> None:
    FEWSHOT_DIR.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(json.dumps(dict(zip(ids, masked)), indent=1, ensure_ascii=False), encoding="utf-8")


def save_embeddings(name: str, ids: list[str], texts: list[str]) -> None:
    vecs = np.concatenate([embed(texts[i : i + 64], "query") for i in range(0, len(texts), 64)])
    np.savez(FEWSHOT_DIR / f"{name}.npz", ids=np.array(ids), vecs=vecs)


@lru_cache(maxsize=None)
def _pool(name: str) -> tuple[dict[str, dict], list[str], np.ndarray]:
    rows = {r["id"]: r for r in load_pools()[name]}
    d = np.load(FEWSHOT_DIR / f"{name}.npz")
    return rows, d["ids"].tolist(), d["vecs"]


@lru_cache(maxsize=None)
def _eval_vectors() -> tuple[dict[int, int], np.ndarray]:
    d = np.load(FEWSHOT_DIR / "minidev.npz")
    return {int(i.split(":")[1]): n for n, i in enumerate(d["ids"].tolist())}, d["vecs"]


def examples_for(q: dict, pool: str, k: int) -> list[dict]:
    """Top-k pool examples by masked-question similarity. 'querylog' stays within q's DB."""
    rows, ids, vecs = _pool(pool)
    pos, eval_vecs = _eval_vectors()
    scores = vecs @ eval_vecs[pos[int(q["question_id"])]]
    if pool == "querylog":
        same_db = np.array([rows[i]["db_id"] == q["db_id"] for i in ids])
        scores = np.where(same_db, scores, -np.inf)
    top = [i for i in np.argsort(-scores)[:k] if np.isfinite(scores[i])]
    return [{**rows[ids[i]], "similarity": round(float(scores[i]), 4)} for i in top]
