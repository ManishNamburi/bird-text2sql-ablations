"""Thin Ollama chat client with a content-addressed disk cache.

Why a cache: ablation runs repeat many identical calls (e.g. the same baseline prompt
appears in several configs, and promptfoo reruns are common while iterating). Caching
by the full request payload makes reruns free and fully deterministic.

Tradeoff: a cache hit has ~0 ms latency, so we store the *original* timings in the
cache entry and report those. Latency numbers therefore always describe a real call.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"

CACHE_DIR = Path(os.environ.get("BIRDEVAL_CACHE", Path(__file__).resolve().parents[2] / ".cache" / "llm"))

DEFAULT_MODEL = os.environ.get("BIRDEVAL_MODEL", "qwen3.5:9b")

# One context size for every config and model (D13). The largest prompt (european_football_2,
# fused long profiles + hints) is ~19.7K tokens. Ollama's MLX runner (qwen3.5) ignores
# num_ctx, but the llama.cpp runner (e.g. qwen2.5-coder) enforces it and would silently
# truncate - so it is set high enough everywhere, and chat() refuses prompts that reach it.
DEFAULT_NUM_CTX = 24576


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    prompt_ms: float  # prefill time (prompt evaluation)
    gen_ms: float  # decode time
    total_ms: float  # wall clock of the original (uncached) call
    cached: bool = False


def _cache_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def chat(
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    seed: int = 42,
    num_ctx: int = DEFAULT_NUM_CTX,
    num_predict: int = 1024,
    think: bool = False,
    format: str | dict | None = None,
    use_cache: bool = True,
    timeout_s: float = 600,
) -> LLMResult:
    """One non-streaming chat call. Thinking is off by default (Qwen3.5 is a reasoning model;
    thinking multiplies latency and is not what the paper's pipeline relied on).
    format: "json" or a JSON schema -> Ollama constrains decoding to valid JSON."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        **({"format": format} if format is not None else {}),
        "options": {
            "temperature": temperature,
            "seed": seed,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        },
    }
    key = _cache_key(payload)
    path = CACHE_DIR / key[:2] / f"{key}.json"
    if use_cache and path.exists():
        data = json.loads(path.read_text())
        return LLMResult(**{**data, "cached": True})

    t0 = time.perf_counter()
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout_s)
    resp.raise_for_status()
    body = resp.json()
    wall_ms = (time.perf_counter() - t0) * 1000

    result = LLMResult(
        text=body["message"]["content"],
        model=model,
        prompt_tokens=body.get("prompt_eval_count", 0),
        completion_tokens=body.get("eval_count", 0),
        prompt_ms=body.get("prompt_eval_duration", 0) / 1e6,
        gen_ms=body.get("eval_duration", 0) / 1e6,
        total_ms=wall_ms,
    )
    if result.prompt_tokens >= num_ctx:
        raise RuntimeError(
            f"prompt used {result.prompt_tokens} tokens >= num_ctx={num_ctx}: it may have been "
            "truncated (llama.cpp runner) - raise num_ctx rather than accept a silently cut schema")
    if use_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(result)
        data.pop("cached")
        path.write_text(json.dumps(data, ensure_ascii=False))
    return result


_FENCE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    """Pull the SQL out of a model reply: last fenced block if present, else the raw text.
    Strips <think> blocks in case a model emits reasoning despite think=False."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    blocks = _FENCE.findall(text)
    sql = blocks[-1] if blocks else text
    return sql.strip().rstrip(";").strip()
