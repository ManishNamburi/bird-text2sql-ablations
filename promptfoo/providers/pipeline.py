"""promptfoo custom provider: runs birdeval's pipeline for one test case.

The provider `config:` block in a promptfoo YAML maps 1:1 onto PipelineConfig, so an
unknown or misspelled key fails loudly instead of silently running the wrong ablation.
promptfoo's own prompt string is unused: the pipeline builds its prompts from the vars,
because multi-step configs (linking, voting) need more than one prompt per question.
"""

from birdeval.pipeline import PipelineConfig, run

# Keys promptfoo itself injects into / reads from a Python provider's config.
PROMPTFOO_KEYS = {"basePath", "pythonExecutable", "workers", "timeout"}


def call_api(prompt, options, context):
    raw = {k: v for k, v in (options.get("config") or {}).items() if k not in PROMPTFOO_KEYS}
    cfg = PipelineConfig(**raw)
    v = context["vars"]
    try:
        result = run(v, cfg)
    except Exception as e:  # surface as a provider error, which promptfoo reports per test
        return {"error": f"{type(e).__name__}: {e}"}

    calls = result.calls
    prompt_tokens = sum(c.prompt_tokens for c in calls)
    completion_tokens = sum(c.completion_tokens for c in calls)
    return {
        "output": result.sql,
        "tokenUsage": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens,
            "numRequests": len(calls),
        },
        "metadata": {
            "llm_calls": len(calls),
            # Timings of the ORIGINAL (uncached) calls; promptfoo's own latency column shows
            # ~0 ms on cache hits, so analysis uses these instead.
            "latency_ms": round(sum(c.total_ms for c in calls)),
            "prefill_ms": round(sum(c.prompt_ms for c in calls)),
            "decode_ms": round(sum(c.gen_ms for c in calls)),
            "all_cached": all(c.cached for c in calls),
            "model": cfg.model,
            "raw_reply": calls[-1].text if calls else "",
            **result.extra,
        },
    }
