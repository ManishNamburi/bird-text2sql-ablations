"""promptfoo hooks for experiment 08 (D23), the native `ollama:chat` provider.

extract_sql: an output transform. The native provider returns the raw reply; every
    assertion should see just the SQL, extracted by the same rule as the pipeline.
add_schema: a transformVars hook. It adds `schema`, the exact schema text the C1 prompt
    shows, so the llm-rubric judge sees what the generator saw. No gold is added.
"""

from birdeval.llm import extract_sql as _extract
from birdeval.promptbuild import schema_text


def extract_sql(output, context):
    return _extract(output or "")


def add_schema(vars, context):
    return {**vars, "schema": schema_text(vars["db_id"], "bird")}
