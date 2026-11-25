"""Write a grading sheet for a random sample of LLM column summaries -> docs/summary_audit.md

Metadata is an input to every C2/C3+ config, so its quality is measured, not assumed:
each sampled long summary is graded against the profile it was generated from.
Grades: OK (all claims supported) / MINOR (a small unsupported or vague claim) /
WRONG (a factual error that could mislead SQL generation).

Run:  uv run python scripts/audit_summaries.py [--n 20] [--seed 7]
"""

import argparse
import json
import random
from pathlib import Path

from birdeval.profiling import DERIVED, load_profiles
from birdeval.sqlexec import DB_ROOT

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    items = []
    for db in sorted(p.name for p in DB_ROOT.iterdir() if p.is_dir()):
        summaries = json.loads((DERIVED / "summaries" / f"{db}.json").read_text(encoding="utf-8"))
        for p in load_profiles(db):
            items.append((db, p, summaries[f"{p['table']}.{p['column']}"]))
    sample = random.Random(a.seed).sample(items, a.n)

    lines = ["# LLM column-summary audit", "",
             f"Random sample of {a.n} of {len(items)} columns (seed {a.seed}). "
             "Each long summary is graded against the profile it was generated from.", "",
             "Grades: **OK** = every claim is supported. **MINOR** = a small unsupported or vague claim. "
             "**WRONG** = a factual error that could mislead SQL generation.", ""]
    for i, (db, p, s) in enumerate(sample, 1):
        lines += [f"## {i}. `{db}.{p['table']}.{p['column']}`", "",
                  f"**Profile:** {p['english']}", "",
                  f"**Short:** {s['short']}", "",
                  f"**Long:** {s['long']}", "",
                  "**Grade:** _TODO_", ""]
    out = ROOT / "docs" / "summary_audit.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
