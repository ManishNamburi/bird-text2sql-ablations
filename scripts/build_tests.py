"""Write promptfoo test files for each frozen split: promptfoo/tests/{dev,eval,test}.yaml

Tests are sorted by db_id so consecutive calls share the schema prefix (Ollama KV-cache reuse).
Gold SQL is deliberately NOT a var: the assertion looks it up by question_id, so it can
never leak into a prompt template.

Run:  uv run python scripts/build_tests.py
"""

import json
from pathlib import Path

import yaml

from birdeval.sqlexec import DATA_ROOT

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    splits = json.loads((ROOT / "data" / "subset_ids.json").read_text(encoding="utf-8"))
    by_id = {q["question_id"]: q for q in json.loads((DATA_ROOT / "mini_dev_sqlite.json").read_text(encoding="utf-8"))}
    out_dir = ROOT / "promptfoo" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    for split in ("dev", "eval", "test"):
        qs = sorted((by_id[i] for i in splits[split]), key=lambda q: (q["db_id"], q["question_id"]))
        tests = [
            {
                "description": f"q{q['question_id']} {q['db_id']} [{q['difficulty']}]",
                "vars": {k: q[k] for k in ("question_id", "db_id", "question", "evidence", "difficulty")},
                "metadata": {"db_id": q["db_id"], "difficulty": q["difficulty"]},
            }
            for q in qs
        ]
        path = out_dir / f"{split}.yaml"
        path.write_text(yaml.safe_dump(tests, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        print(f"{split}: {len(tests)} tests -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
