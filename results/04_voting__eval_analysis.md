# 04_voting__eval: paired analysis (150 questions)

## Accuracy and cost per config

| config           |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:-----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked        | 150 |   39.3 | 32–47    |          94.7 |        0 |          18387 |           6.3 |    40.8 |         0.85  |             6.5 |        55.8 |          36.5 |             24.2 |
| C6-vote          | 150 |   40   | 33–48    |          99.3 |        0 |          20252 |           8.3 |    49.7 |         0.85  |             6.5 |        58.1 |          35.1 |             27.3 |
| C6-shuffle       | 150 |   39.3 | 32–47    |          97.3 |        0 |          20252 |           8.3 |    49.6 |         0.85  |             6.5 |        55.8 |          36.5 |             24.2 |
| C4-linked+hints  | 150 |   56.7 | 49–64    |          94.7 |        0 |          18942 |           6.3 |    39.2 |         0.909 |             5.9 |        65.1 |          54.1 |             51.5 |
| C6-vote+hints    | 150 |   58.7 | 51–66    |          96.7 |        0 |          20733 |           8.3 |    47.9 |         0.909 |             5.9 |        67.4 |          56.8 |             51.5 |
| C6-shuffle+hints | 150 |   60.7 | 53–68    |          97.3 |        0 |          20733 |           8.3 |    48   |         0.909 |             5.9 |        67.4 |          60.8 |             51.5 |

## Voting diagnostics

`pass@k` = any candidate correct (perfect-selector ceiling). `unanimous` = all candidates executed and returned the same rows.

| config           |   EX % (voted) |   EX % candidate 0 (= parent) |   EX % candidate 1 |   EX % candidate 2 |   pass@3 % |   unanimous % |   winner ≠ candidate 0 % |   distinct SQL/q |
|:-----------------|---------------:|------------------------------:|-------------------:|-------------------:|-----------:|--------------:|-------------------------:|-----------------:|
| C6-vote          |           40   |                          39.3 |               35.3 |               39.3 |       46.7 |          54   |                     10   |             2.42 |
| C6-shuffle       |           39.3 |                          39.3 |               36   |               38   |       42   |          64.7 |                     11.3 |             1.95 |
| C6-vote+hints    |           58.7 |                          56.7 |               52   |               55.3 |       62.7 |          63.3 |                      7.3 |             2.32 |
| C6-shuffle+hints |           60.7 |                          56.7 |               58.7 |               60   |       62   |          76.7 |                     10.7 |             1.7  |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from            | to               |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:----------------|:-----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked       | C6-vote          |         0.7 | -1.3 to +3.3   |       2 |       1 |      1      | no         |
| C6-vote         | C6-shuffle       |        -0.7 | -3.3 to +1.3   |       1 |       2 |      1      | no         |
| C4-linked+hints | C6-vote+hints    |         2   | -0.7 to +4.7   |       4 |       1 |      0.375  | no         |
| C6-vote+hints   | C6-shuffle+hints |         2   | +0.0 to +4.7   |       3 |       0 |      0.25   | no         |
| C4-linked       | C4-linked+hints  |        17.3 | +9.3 to +25.3  |      34 |       8 |      0.0001 | yes        |
| C6-vote         | C6-vote+hints    |        18.7 | +11.3 to +26.7 |      34 |       6 |      0      | yes        |
| C6-shuffle      | C6-shuffle+hints |        21.3 | +13.3 to +29.3 |      37 |       5 |      0      | yes        |
| C4-linked       | C6-shuffle       |         0   | -2.0 to +2.0   |       1 |       1 |      1      | no         |
| C4-linked+hints | C6-shuffle+hints |         4   | +1.3 to +7.3   |       6 |       0 |      0.0312 | yes        |
