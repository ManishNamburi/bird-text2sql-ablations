"""promptfoo assertion: BIRD execution accuracy (EX).

Executes the predicted SQL read-only and compares its rows to the cached gold rows with
set equality, exactly like BIRD's official evaluation/evaluation_ex.py (calculate_ex).
Gold SQL never reaches the model: it is looked up here by question_id.
"""

from birdeval.sqlexec import score_question


def get_assert(output, context):
    v = context["vars"]
    s = score_question(int(v["question_id"]), v["db_id"], output or "")
    if s.match:
        reason = "EX match"
    elif not s.valid_sql:
        reason = f"invalid SQL: {s.error}"
    else:
        reason = f"wrong result: got {s.pred_rows_preview!r}, expected {s.gold_rows_preview!r}"
    return {
        "pass": s.match,
        "score": float(s.match),
        "reason": reason[:500],
        "namedScores": {"ex": float(s.match), "valid_sql": float(s.valid_sql)},
    }
