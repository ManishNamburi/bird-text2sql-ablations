# 05_checks__eval: paired analysis (150 questions)

## Accuracy and cost per config

| config           |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:-----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked        | 150 |   39.3 | 32–47    |          94.7 |        0 |          18387 |           6.3 |    40.8 |         0.85  |             6.5 |        55.8 |          36.5 |             24.2 |
| C4-checked       | 150 |   40.7 | 33–49    |          94.7 |        0 |          18477 |           6.4 |    41.2 |         0.85  |             6.5 |        55.8 |          36.5 |             30.3 |
| C6-vote          | 150 |   40   | 33–48    |          99.3 |        0 |          20252 |           8.3 |    49.7 |         0.85  |             6.5 |        58.1 |          35.1 |             27.3 |
| C7               | 150 |   41.3 | 34–49    |          99.3 |        0 |          20523 |           8.6 |    50.9 |         0.85  |             6.5 |        58.1 |          35.1 |             33.3 |
| C4-linked+hints  | 150 |   56.7 | 49–64    |          94.7 |        0 |          18942 |           6.3 |    39.2 |         0.909 |             5.9 |        65.1 |          54.1 |             51.5 |
| C4-checked+hints | 150 |   57.3 | 49–65    |          94.7 |        0 |          19046 |           6.5 |    39.7 |         0.909 |             5.9 |        65.1 |          54.1 |             54.5 |
| C6-vote+hints    | 150 |   58.7 | 51–66    |          96.7 |        0 |          20733 |           8.3 |    47.9 |         0.909 |             5.9 |        67.4 |          56.8 |             51.5 |
| C7+hints         | 150 |   59.3 | 51–67    |          96.7 |        0 |          21032 |           8.7 |    49.2 |         0.909 |             5.9 |        67.4 |          56.8 |             54.5 |

## Voting diagnostics

`pass@k` = any candidate correct (perfect-selector ceiling). `unanimous` = all candidates executed and returned the same rows.

| config        |   EX % (voted) |   EX % candidate 0 (= parent) |   EX % candidate 1 |   EX % candidate 2 |   pass@3 % |   unanimous % |   winner ≠ candidate 0 % |   distinct SQL/q |
|:--------------|---------------:|------------------------------:|-------------------:|-------------------:|-----------:|--------------:|-------------------------:|-----------------:|
| C6-vote       |           40   |                          39.3 |               35.3 |               39.3 |       46.7 |          54   |                     10   |             2.42 |
| C7            |           41.3 |                          40.7 |               36.7 |               40.7 |       48   |          54   |                     10   |             2.42 |
| C6-vote+hints |           58.7 |                          56.7 |               52   |               55.3 |       62.7 |          63.3 |                      7.3 |             2.32 |
| C7+hints      |           59.3 |                          57.3 |               52   |               56   |       63.3 |          64   |                      7.3 |             2.31 |

## SQL-check diagnostics

Per check, on the questions where it fired in any candidate. `fixed` / `broke` are EX against the parent config on those questions.

| config           | parent          | check           |   questions fired |   SQL changed |   correction calls |   fixed |   broke |
|:-----------------|:----------------|:----------------|------------------:|--------------:|-------------------:|--------:|--------:|
| C4-checked       | C4-linked       | null_order      |                 3 |             3 |                  3 |       0 |       0 |
| C4-checked       | C4-linked       | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked       | C4-linked       | minmax_subquery |                 4 |             3 |                  6 |       0 |       0 |
| C4-checked       | C4-linked       | concat          |                 2 |             2 |                  2 |       2 |       0 |
| C4-checked       | C4-linked       | any             |                 9 |             8 |                 11 |       2 |       0 |
| C7               | C6-vote         | null_order      |                 4 |             4 |                 10 |       0 |       0 |
| C7               | C6-vote         | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C7               | C6-vote         | minmax_subquery |                 4 |             3 |                 16 |       0 |       0 |
| C7               | C6-vote         | concat          |                 4 |             4 |                  8 |       2 |       0 |
| C7               | C6-vote         | any             |                12 |            11 |                 34 |       2 |       0 |
| C4-checked+hints | C4-linked+hints | null_order      |                 4 |             4 |                  4 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | minmax_subquery |                 7 |             4 |                  9 |       0 |       0 |
| C4-checked+hints | C4-linked+hints | concat          |                 3 |             3 |                  3 |       1 |       0 |
| C4-checked+hints | C4-linked+hints | any             |                14 |            11 |                 16 |       1 |       0 |
| C7+hints         | C6-vote+hints   | null_order      |                 4 |             4 |                 11 |       0 |       0 |
| C7+hints         | C6-vote+hints   | null_min        |                 0 |             0 |                  0 |       0 |       0 |
| C7+hints         | C6-vote+hints   | minmax_subquery |                 9 |             8 |                 29 |       0 |       0 |
| C7+hints         | C6-vote+hints   | concat          |                 3 |             3 |                  7 |       1 |       0 |
| C7+hints         | C6-vote+hints   | any             |                16 |            15 |                 47 |       1 |       0 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from             | to               |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:-----------------|:-----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked        | C4-checked       |         1.3 | +0.0 to +3.3   |       2 |       0 |      0.5    | no         |
| C4-checked       | C6-vote          |        -0.7 | -3.3 to +2.0   |       2 |       3 |      1      | no         |
| C6-vote          | C7               |         1.3 | +0.0 to +3.3   |       2 |       0 |      0.5    | no         |
| C4-linked+hints  | C4-checked+hints |         0.7 | +0.0 to +2.0   |       1 |       0 |      1      | no         |
| C4-checked+hints | C6-vote+hints    |         1.3 | -2.0 to +4.7   |       4 |       2 |      0.6875 | no         |
| C6-vote+hints    | C7+hints         |         0.7 | +0.0 to +2.0   |       1 |       0 |      1      | no         |
| C4-linked        | C4-linked+hints  |        17.3 | +9.3 to +25.3  |      34 |       8 |      0.0001 | yes        |
| C4-checked       | C4-checked+hints |        16.7 | +8.7 to +24.7  |      34 |       9 |      0.0002 | yes        |
| C6-vote          | C6-vote+hints    |        18.7 | +11.3 to +26.7 |      34 |       6 |      0      | yes        |
| C7               | C7+hints         |        18   | +10.0 to +26.0 |      34 |       7 |      0      | yes        |
| C4-linked        | C6-vote          |         0.7 | -1.3 to +3.3   |       2 |       1 |      1      | no         |
| C4-linked+hints  | C6-vote+hints    |         2   | -0.7 to +4.7   |       4 |       1 |      0.375  | no         |
| C4-linked        | C7               |         2   | -0.7 to +5.3   |       4 |       1 |      0.375  | no         |
| C4-linked+hints  | C7+hints         |         2.7 | +0.0 to +6.0   |       5 |       1 |      0.2188 | no         |
