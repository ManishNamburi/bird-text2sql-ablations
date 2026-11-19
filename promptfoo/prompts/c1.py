"""promptfoo prompt functions for experiment 08 (D23): C1 for the native `ollama:chat` provider.

They call the pipeline's own `build_messages`, so the chat messages are byte-identical to
what the custom provider sends for C1-bird and C1-bird+hints. Returned as JSON, which
promptfoo parses back into chat messages for the provider.
"""

import json

from birdeval.pipeline import PipelineConfig, build_messages


def _messages(context: dict, hints: bool) -> str:
    return json.dumps(build_messages(context["vars"], PipelineConfig(metadata="bird", hints=hints)))


def no_hints(context: dict) -> str:
    return _messages(context, hints=False)


def with_hints(context: dict) -> str:
    return _messages(context, hints=True)
