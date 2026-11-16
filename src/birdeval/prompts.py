"""Prompt templates. Kept in one place so prompt-trimming experiments edit exactly one thing.

Layout rule: the schema comes FIRST and the question LAST. Every question on the same DB
then shares an identical prefix, and Ollama reuses its KV cache for it (measured in the
Phase 0 smoke test: ~4-6 s of prefill drops to ~0.3 s).
"""

SYSTEM = """You are an expert SQLite data analyst. Write one SQLite query that answers the question using the database schema provided.
Rules:
- Use only tables and columns that exist in the schema.
- Return exactly the columns the question asks for, in the order asked, and nothing else.
- Reply with only the SQL query in a ```sql code block."""


def user_message(schema: str, question: str, evidence: str | None = None,
                 examples: str | None = None) -> str:
    """Schema first (shared KV-cache prefix), then optional few-shot examples, then the question."""
    msg = f"Database schema:\n{schema}\n\n"
    if examples:
        msg += f"{examples}\n\n"
    msg += f"Question: {question}"
    if evidence:
        msg += f"\nHint: {evidence}"
    return msg


def few_shot_block(examples: list[dict], with_evidence: bool, cross_db: bool) -> str:
    """Few-shot examples (paper §4). Hints are shown only when the run itself uses hints."""
    where = ("from other databases (their tables differ from the schema above)" if cross_db
             else "previously asked on this database")
    parts = [f"Examples of similar questions and their SQL, {where}:"]
    for e in examples:
        hint = f"\nHint: {e['evidence']}" if with_evidence and e.get("evidence") else ""
        parts.append(f"Question: {e['question']}{hint}\nSQL: {e['SQL']}")
    return "\n\n".join(parts)


def literal_revision(missing: dict[str, list[str]]) -> str:
    """Paper §3 step 2.e.ii: ask the LLM to revise its query to use the fields that actually
    contain the literals it used. missing: {literal: ["table.column (e.g. 'stored value')", ...]}"""
    lines = [f"- '{lit}' appears in: {', '.join(where)}" for lit, where in missing.items()]
    return ("Some values in your query are compared against columns that do not contain them. "
            "In the database:\n" + "\n".join(lines) +
            "\nRevise the SQL query to use the appropriate columns (the schema above includes them). "
            "Reply with only the SQL query in a ```sql code block.")
