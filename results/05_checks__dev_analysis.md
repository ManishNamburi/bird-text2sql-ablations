# 05_checks__dev: paired analysis (30 questions)

## Accuracy and cost per config

| config           |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:-----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked        |  30 |   40   | 25–58    |          90   |        0 |          18525 |           6.2 |    54.4 |         0.93  |             6.3 |        66.7 |          31.2 |               20 |
| C4-checked       |  30 |   40   | 25–58    |          90   |        0 |          18548 |           6.3 |    54.6 |         0.93  |             6.3 |        66.7 |          31.2 |               20 |
| C6-vote          |  30 |   46.7 | 30–64    |         100   |        0 |          20275 |           8.2 |    64.2 |         0.93  |             6.3 |        77.8 |          37.5 |               20 |
| C7               |  30 |   46.7 | 30–64    |         100   |        0 |          20352 |           8.3 |    64.7 |         0.93  |             6.3 |        77.8 |          37.5 |               20 |
| C4-linked+hints  |  30 |   53.3 | 36–70    |          86.7 |        0 |          18200 |           6   |    54.2 |         0.927 |             5.4 |        77.8 |          50   |               20 |
| C4-checked+hints |  30 |   56.7 | 39–73    |          86.7 |        0 |          18237 |           6.1 |    54.4 |         0.927 |             5.4 |        88.9 |          50   |               20 |
| C6-vote+hints    |  30 |   60   | 42–75    |          96.7 |        0 |          19860 |           8   |    62.1 |         0.927 |             5.4 |        77.8 |          62.5 |               20 |
| C7+hints         |  30 |   60   | 42–75    |          96.7 |        0 |          19950 |           8.1 |    62.4 |         0.927 |             5.4 |        77.8 |          62.5 |               20 |

## Voting diagnostics

`pass@k` = any candidate correct (perfect-selector ceiling). `unanimous` = all candidates executed and returned the same rows.

| config        |   EX % (voted) |   EX % candidate 0 (= parent) |   EX % candidate 1 |   EX % candidate 2 |   pass@3 % |   unanimous % |   winner ≠ candidate 0 % |   distinct SQL/q |
|:--------------|---------------:|------------------------------:|-------------------:|-------------------:|-----------:|--------------:|-------------------------:|-----------------:|
| C6-vote       |           46.7 |                          40   |               53.3 |               43.3 |       66.7 |          43.3 |                     20   |             2.47 |
| C7            |           46.7 |                          40   |               53.3 |               43.3 |       66.7 |          43.3 |                     20   |             2.47 |
| C6-vote+hints |           60   |                          53.3 |               50   |               46.7 |       63.3 |          43.3 |                     20   |             2.23 |
| C7+hints      |           60   |                          56.7 |               50   |               46.7 |       63.3 |          46.7 |                     16.7 |             2.23 |

## SQL-check diagnostics

Per check, on the questions where it fired in any candidate. `fixed` / `broke` are EX against the parent config on those questions.

| config           | parent          | check           |   questions fired |   SQL changed |   correction calls |   fixed |   broke |
|:-----------------|:----------------|:----------------|------------------:|--------------:|-------------------:|--------:|--------:|
| C4-checked       | C4-linked       | null_order      |                 1 |             1 |                  1 |       0 |       0 |
| C4-checked       | C4-linked       | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked       | C4-linked       | minmax_subquery |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked       | C4-linked       | concat          |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked       | C4-linked       | any             |                 1 |             1 |                  1 |       0 |       0 |
| C7               | C6-vote         | null_order      |                 1 |             1 |                  1 |       0 |       0 |
| C7               | C6-vote         | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C7               | C6-vote         | minmax_subquery |                 1 |             1 |                  1 |       0 |       0 |
| C7               | C6-vote         | concat          |                 0 |             0 |                  0 |       0 |       0 |
| C7               | C6-vote         | any             |                 2 |             2 |                  2 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | null_order      |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | minmax_subquery |                 1 |             1 |                  1 |       1 |       0 |
| C4-checked+hints | C4-linked+hints | concat          |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | any             |                 1 |             1 |                  1 |       1 |       0 |
| C7+hints         | C6-vote+hints   | null_order      |                 0 |             0 |                  0 |       0 |       0 |
| C7+hints         | C6-vote+hints   | null_min        |                 1 |             1 |                  1 |       0 |       0 |
| C7+hints         | C6-vote+hints   | minmax_subquery |                 2 |             2 |                  2 |       0 |       0 |
| C7+hints         | C6-vote+hints   | concat          |                 0 |             0 |                  0 |       0 |       0 |
| C7+hints         | C6-vote+hints   | any             |                 2 |             2 |                  2 |       0 |       0 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from             | to               |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:-----------------|:-----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked        | C4-checked       |         0   | +0.0 to +0.0   |       0 |       0 |      1      | no         |
| C4-checked       | C6-vote          |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
| C6-vote          | C7               |         0   | +0.0 to +0.0   |       0 |       0 |      1      | no         |
| C4-linked+hints  | C4-checked+hints |         3.3 | +0.0 to +10.0  |       1 |       0 |      1      | no         |
| C4-checked+hints | C6-vote+hints    |         3.3 | -6.7 to +13.3  |       2 |       1 |      1      | no         |
| C6-vote+hints    | C7+hints         |         0   | +0.0 to +0.0   |       0 |       0 |      1      | no         |
| C4-linked        | C4-linked+hints  |        13.3 | -6.7 to +33.3  |       7 |       3 |      0.3438 | no         |
| C4-checked       | C4-checked+hints |        16.7 | -3.3 to +36.7  |       8 |       3 |      0.2266 | no         |
| C6-vote          | C6-vote+hints    |        13.3 | -10.0 to +36.7 |       8 |       4 |      0.3877 | no         |
| C7               | C7+hints         |        13.3 | -10.0 to +36.7 |       8 |       4 |      0.3877 | no         |
| C4-linked        | C6-vote          |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
| C4-linked+hints  | C6-vote+hints    |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
