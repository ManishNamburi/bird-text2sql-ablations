# 04_voting__dev: paired analysis (30 questions)

## Accuracy and cost per config

| config           |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:-----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked        |  30 |   40   | 25–58    |          90   |        0 |          18525 |           6.2 |    54.4 |         0.93  |             6.3 |        66.7 |          31.2 |               20 |
| C6-vote          |  30 |   46.7 | 30–64    |         100   |        0 |          20275 |           8.2 |    64.2 |         0.93  |             6.3 |        77.8 |          37.5 |               20 |
| C6-shuffle       |  30 |   40   | 25–58    |          93.3 |        0 |          20275 |           8.2 |    63.1 |         0.93  |             6.3 |        55.6 |          31.2 |               40 |
| C4-linked+hints  |  30 |   53.3 | 36–70    |          86.7 |        0 |          18200 |           6   |    54.2 |         0.927 |             5.4 |        77.8 |          50   |               20 |
| C6-vote+hints    |  30 |   60   | 42–75    |          96.7 |        0 |          19860 |           8   |    62.1 |         0.927 |             5.4 |        77.8 |          62.5 |               20 |
| C6-shuffle+hints |  30 |   53.3 | 36–70    |          90   |        0 |          19860 |           8   |    61.9 |         0.927 |             5.4 |        66.7 |          56.2 |               20 |

## Voting diagnostics

`pass@k` = any candidate correct (perfect-selector ceiling). `unanimous` = all candidates executed and returned the same rows.

| config           |   EX % (voted) |   EX % candidate 0 (= parent) |   EX % candidate 1 |   EX % candidate 2 |   pass@3 % |   unanimous % |   winner ≠ candidate 0 % |   distinct SQL/q |
|:-----------------|---------------:|------------------------------:|-------------------:|-------------------:|-----------:|--------------:|-------------------------:|-----------------:|
| C6-vote          |           46.7 |                          40   |               53.3 |               43.3 |       66.7 |          43.3 |                       20 |             2.47 |
| C6-shuffle       |           40   |                          40   |               40   |               40   |       53.3 |          63.3 |                       10 |             1.67 |
| C6-vote+hints    |           60   |                          53.3 |               50   |               46.7 |       63.3 |          43.3 |                       20 |             2.23 |
| C6-shuffle+hints |           53.3 |                          53.3 |               53.3 |               50   |       60   |          66.7 |                       10 |             1.57 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from            | to               |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:----------------|:-----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked       | C6-vote          |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
| C6-vote         | C6-shuffle       |        -6.7 | -23.3 to +10.0 |       2 |       4 |      0.6875 | no         |
| C4-linked+hints | C6-vote+hints    |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
| C6-vote+hints   | C6-shuffle+hints |        -6.7 | -20.0 to +6.7  |       1 |       3 |      0.625  | no         |
| C4-linked       | C4-linked+hints  |        13.3 | -6.7 to +33.3  |       7 |       3 |      0.3438 | no         |
| C6-vote         | C6-vote+hints    |        13.3 | -10.0 to +36.7 |       8 |       4 |      0.3877 | no         |
| C6-shuffle      | C6-shuffle+hints |        13.3 | -10.0 to +36.7 |       8 |       4 |      0.3877 | no         |
