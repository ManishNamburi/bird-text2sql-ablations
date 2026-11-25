"""Semantic column index (paper §3: "a second semantic similarity index ... on the long summary").

Each column is embedded as "<table>.<column>: <long LLM summary>" with nomic-embed-text
(via Ollama). Questions are embedded with the "search_query:" task prefix nomic expects.
Used by schema linking (C4) to build the *focused schema*: columns semantically close to
the question, plus the columns whose values match the question's literals (valueindex).

Tradeoff vs the paper's FAISS: ~800 columns total (<=200 per DB) -> exact brute-force
cosine similarity in numpy is instant and simpler than an ANN index.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import requests

from birdeval.llm import OLLAMA_URL
from birdeval.profiling import DERIVED

EMBED_MODEL = "nomic-embed-text"


def embed(texts: list[str], kind: str) -> np.ndarray:
    """Unit-normalized embeddings. kind: 'document' or 'query' (nomic task prefixes)."""
    prefix = {"document": "search_document: ", "query": "search_query: "}[kind]
    r = requests.post(f"{OLLAMA_URL}/api/embed",
                      json={"model": EMBED_MODEL, "input": [prefix + t for t in texts]}, timeout=600)
    r.raise_for_status()
    m = np.asarray(r.json()["embeddings"], dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def _path(db_id: str):
    return DERIVED / "embeddings" / f"{db_id}.npz"


def build(db_id: str) -> int:
    summaries = json.loads((DERIVED / "summaries" / f"{db_id}.json").read_text(encoding="utf-8"))
    keys = list(summaries)
    vecs = np.concatenate([embed([f"{k}: {summaries[k]['long']}" for k in keys[i : i + 64]], "document")
                           for i in range(0, len(keys), 64)])
    _path(db_id).parent.mkdir(parents=True, exist_ok=True)
    np.savez(_path(db_id), keys=np.array(keys), vecs=vecs)
    return len(keys)


@lru_cache(maxsize=None)
def _load(db_id: str) -> tuple[list[tuple[str, str]], np.ndarray]:
    d = np.load(_path(db_id))
    return [tuple(k.split(".", 1)) for k in d["keys"].tolist()], d["vecs"]


@lru_cache(maxsize=4096)
def similar_columns(db_id: str, text: str, k: int = 20) -> tuple[tuple[str, str, float], ...]:
    """Top-k (table, column, cosine) for a question/text."""
    keys, vecs = _load(db_id)
    scores = vecs @ embed([text], "query")[0]
    top = np.argsort(-scores)[:k]
    return tuple((keys[i][0], keys[i][1], round(float(scores[i]), 4)) for i in top)
