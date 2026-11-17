# 02_linking__dev: paired analysis (30 questions)

## Accuracy and cost per config

| config          |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   EX simple |   EX moderate |   EX challenging |   link recall |   linked cols/q |
|:----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|------------:|--------------:|-----------------:|--------------:|----------------:|
| C3-fused        |  30 |   30   | 17–48    |          93.3 |        0 |           8579 |           1   |    18.6 |        44.4 |          31.2 |                0 |       nan     |           nan   |
| C4-linked       |  30 |   40   | 25–58    |          90   |        0 |          18527 |           6.2 |    56.4 |        66.7 |          31.2 |               20 |         0.93  |             6.3 |
| C4-oracle       |  30 |   56.7 | 39–73    |          93.3 |        0 |            725 |           1   |     3.9 |        88.9 |          50   |               20 |         1     |             4.8 |
| C3-fused+hints  |  30 |   43.3 | 27–61    |          86.7 |        0 |           8620 |           1   |    18   |        44.4 |          50   |               20 |       nan     |           nan   |
| C4-linked+hints |  30 |   53.3 | 36–70    |          86.7 |        0 |          18200 |           6   |    54.2 |        77.8 |          50   |               20 |         0.927 |             5.4 |
| C4-oracle+hints |  30 |   56.7 | 39–73    |          90   |        0 |            766 |           1   |     3.9 |        66.7 |          62.5 |               20 |         1     |             4.8 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from            | to              |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:----------------|:----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C3-fused        | C4-linked       |        10   | -3.3 to +23.3  |       4 |       1 |      0.375  | no         |
| C4-linked       | C4-oracle       |        16.7 | +3.3 to +30.0  |       5 |       0 |      0.0625 | no         |
| C3-fused+hints  | C4-linked+hints |        10   | -3.3 to +23.3  |       4 |       1 |      0.375  | no         |
| C4-linked+hints | C4-oracle+hints |         3.3 | -6.7 to +13.3  |       2 |       1 |      1      | no         |
| C3-fused        | C3-fused+hints  |        13.3 | -6.7 to +33.3  |       7 |       3 |      0.3438 | no         |
| C4-linked       | C4-linked+hints |        13.3 | -6.7 to +33.3  |       7 |       3 |      0.3438 | no         |
| C4-oracle       | C4-oracle+hints |         0   | -20.0 to +20.0 |       5 |       5 |      1      | no         |
