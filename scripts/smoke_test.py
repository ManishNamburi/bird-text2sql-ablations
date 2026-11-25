"""Phase 0 smoke test: a few questions end-to-end (DDL-only prompt -> model -> SQLite -> EX),
with prefill vs decode timing. Also demonstrates Ollama's prefix (KV) cache: questions on
the same DB share the schema prefix, so the 2nd+ call should have a much smaller prefill.

Run:  uv run python scripts/smoke_test.py [model]
"""

import json
import sqlite3
import sys

from birdeval.llm import chat, extract_sql
from birdeval.sqlexec import DATA_ROOT, db_path, score_question

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:9b"
DB = "california_schools"


def ddl(db_id: str) -> str:
    con = sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True)
    rows = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL").fetchall()
    return "\n\n".join(r[0] for r in rows)


questions = [q for q in json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text(encoding="utf-8")) if q["db_id"] == DB][:3]
schema = ddl(DB)
print(f"model={MODEL} db={DB} schema_chars={len(schema)}\n")
for q in questions:
    messages = [
        {"role": "system", "content": "You write a single correct SQLite query. Reply with only the SQL in a ```sql block."},
        # Schema first, question last: identical prefixes across questions -> KV-cache reuse.
        {"role": "user", "content": f"Database schema:\n{schema}\n\nQuestion: {q['question']}"},
    ]
    r = chat(messages, model=MODEL, use_cache=False)
    sql = extract_sql(r.text)
    s = score_question(q["question_id"], q["db_id"], sql)
    print(f"qid={q['question_id']} [{q['difficulty']}] EX={int(s.match)} valid={s.valid_sql}")
    print(f"  prompt_tokens={r.prompt_tokens} prefill={r.prompt_ms:.0f}ms "
          f"completion_tokens={r.completion_tokens} decode={r.gen_ms:.0f}ms "
          f"({r.completion_tokens / max(r.gen_ms, 1) * 1000:.1f} tok/s) wall={r.total_ms:.0f}ms")
    print(f"  Q: {q['question']}\n  SQL: {sql}\n  err: {s.error}\n")
