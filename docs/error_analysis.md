# Error analysis: C7 (full pipeline), no hints, eval split

C7 gets 62 of 150 questions right (41.3%). This page looks at the 88 it gets wrong. It has two parts: an automatic breakdown of all 88, and a manual read of 20 sampled at random. The numbers come from `uv run python analysis/error_analysis.py`, which needs the local raw results.

## 1. All 88 failures, automatically

Each prediction is executed and compared with the cached gold rows. The breakdown is crossed with whether schema linking dropped a column the gold SQL uses (`link_recall < 1`).

| What the prediction returned | Linking kept every needed column | Linking dropped a needed column | Total |
|---|---|---|---|
| Right number of rows, wrong values | 22 | 33 | 55 |
| Wrong number of rows | 9 | 12 | 21 |
| Empty result | 3 | 8 | 11 |
| Invalid SQL | 1 | 0 | 1 |
| **Total** | **35** | **53** | **88** |

- **Invalid SQL is solved.** Voting and the checks leave 1 execution error in 150.
- **Linking drops a needed column in 60% of failures** (53/88). Across all 150 questions, C7 is right on 14 of the 67 where linking dropped a needed column (21%), versus 48 of the 83 where it kept them all (58%). That's the same gap experiment 02 found. The oracle (53.3%) shows what fixing it is worth.
- **Most failures are well-formed queries that answer slightly the wrong thing:** 55 return the right number of rows with the wrong values.

## 2. Twenty failures, read by hand

**Method:** 20 failures sampled with `random_state=42`. For each, I (Claude, the coding assistant on this project) read the question, BIRD's hint (which C7 didn't see), both SQL queries and both results. I gave each case one primary cause. Whenever the cause pointed at the gold SQL, I executed queries against the database to confirm it before writing it down. These are one reader's judgements on 20 cases, so the shares below carry roughly ±20 pp of uncertainty.

| Primary cause | Cases | Question ids |
|---|---|---|
| Wrong column: the needed column wasn't in the linked schema, or a look-alike was used | 5 | 46, 125, 930, 1068, 1254 |
| Question is ambiguous without BIRD's hint, and the model's reading is defensible | 5 | 239, 366, 1028, 1122, 1473 |
| Wrong filter: condition or literal | 3 | 24, 1195, 1265 |
| Gold SQL is wrong or returns columns the question doesn't ask for | 3 | 879, 1168, 1427 |
| Output columns differ from gold (the question doesn't pin them down) | 2 | 159, 344 |
| Missing aggregation step | 1 | 518 |
| Wrong join path | 1 | 1115 |

### The cases

| qid | DB | Cause | What happened |
|---|---|---|---|
| 24 | california_schools | Wrong filter | "test takers whose score ≥ 1500" became `NumGE1500 IS NOT NULL` instead of `> 0`, which keeps schools with zero such takers. |
| 46 | california_schools | Wrong column | Returned the *state* and a SAT enrolment sum, not the school's name. Linking missed `DOC` and `Enrollment (K-12)` (recall 0.6). |
| 125 | financial | Wrong column | The question needs `A12`/`A13`, cryptic unemployment columns that only the hint names. Linking missed them (recall 0.57), and the model returned region names as the "percentage". |
| 159 | financial | Output columns | "List all the withdrawals": the model listed amount, date and operation, while gold lists `trans_id`. The same rows, described differently. |
| 239 | toxicology | Ambiguous | "atom 19" was read as one atom (`TR496_19`, 8 connections). The hint means every atom numbered 19 (377). |
| 344 | card_games | Output columns | Returned card names (duplicates collapse in the set), while gold returns ids. |
| 366 | card_games | Ambiguous | "rule of playing card" was read as its rulings text (none exist, so the result is empty). The hint says it means the legal formats. |
| 518 | card_games | Aggregation | Listed banned cards in *every* format, instead of only the format with the most bans. |
| 879 | formula_1 | **Gold bug** | Gold orders `fastestLapSpeed`, a TEXT column, alphabetically, so it picks 91.610 instead of the real maximum 257.320 (verified). The prediction casts to REAL and **is correct**. |
| 930 | formula_1 | Wrong column | Returned Hamilton's best finishing *position* (`1`), not the race name. Linking missed `races.name` (recall 0.5). |
| 1028 | european_football_2 | Ambiguous | "the 2010 season" was read as `2010/2011`. The hint says `2009/2010`. |
| 1068 | european_football_2 | Wrong column | "players higher than 170" became `overall_rating > 170` (no rows, so NULL) instead of `Player.height`. Linking missed `height` (recall 0.33). |
| 1115 | european_football_2 | Join | Joined two players through a `Match` row on a given date. They never shared one, so the result is empty. |
| 1122 | european_football_2 | Ambiguous | "the strongest player" was read as the `strength` attribute. The hint says `overall_rating`. |
| 1168 | thrombosis_prediction | **Gold extra column** | Gold returns a third column (`Birthday`) the question doesn't ask for, so no two-column answer can match. The prediction's age formula is also off by a year. |
| 1195 | thrombosis_prediction | Wrong filter | `Diagnosis LIKE '%SLE%'` matches other diagnoses that mention SLE. Gold uses `= 'SLE'`. |
| 1254 | thrombosis_prediction | Wrong column | Used the lab `Date` instead of `Patient.First Date`, and added an unrequested `Admission = '+'`. Linking missed `First Date`. Gold is also questionable: it counts 1,590 lab rows for "how many patients" (133 distinct, verified). |
| 1265 | thrombosis_prediction | Wrong filter | Used `RNP = '-'`, a value that doesn't occur. The data has `negative` and `0`, which only the hint explains. Gold has an operator-precedence bug: `A OR B AND C` gives 47 where the intended `(A OR B) AND C` gives 35 (verified). |
| 1427 | student_club | **Gold extra column** | The question asks for the budget category. Gold also returns `type`. The prediction's rows equal gold's first column exactly, so **it is correct**. |
| 1473 | debit_card_specializing | Ambiguous | "average monthly consumption": the model averaged the monthly rows. The hint (and gold) divide that by 12 again, although each row is already one month (~8 rows per customer in 2013, verified). |

## What this says

- **About 8 of 20 failures can't be fixed by a better pipeline without hints.**
  - In 5, the question only means what the gold says once you read the hint.
  - In 3, the gold SQL is wrong or over-specified. In 2 of those (879, 1427), C7's answer is right.
  - That fits paper §4.1.1, which reports wrong or ambiguous gold queries in BIRD dev. It's also part of why hints add +17 pp: much of a hint's value is defining what the question means.
- **Linking recall is the biggest fixable cause.** Wrong-column errors (5 of 20) and the automatic count (53 of 88 failures with a dropped column) agree.
- **The SQL checks target almost none of this.** Of 20 failures, none is NULL ordering, subquery-vs-LIMIT or concatenation. That's consistent with experiment 05's near-zero effect.
- **Gold bugs bound what's measurable.** If the 3 gold-side cases here are representative (3/20 = 15% of failures, so very roughly 9% of all questions), the measurable ceiling on this split sits a few points below 100%. The CIs are too wide to say more.

Gold bugs are reported here, never "fixed" in scoring. All configs are scored against the same gold, so the comparisons stay fair.
