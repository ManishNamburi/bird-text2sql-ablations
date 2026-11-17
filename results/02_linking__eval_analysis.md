# 02_linking__eval: paired analysis (150 questions)

## Accuracy and cost per config

| config          |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   EX simple |   EX moderate |   EX challenging |   link recall |   linked cols/q |
|:----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|------------:|--------------:|-----------------:|--------------:|----------------:|
| C3-fused        | 150 |   34.7 | 28–43    |          88.7 |        0 |           8112 |           1   |     5.4 |        37.2 |          36.5 |             27.3 |       nan     |           nan   |
| C4-linked       | 150 |   39.3 | 32–47    |          94.7 |        0 |          18387 |           6.3 |    40.8 |        55.8 |          36.5 |             24.2 |         0.85  |             6.5 |
| C4-oracle       | 150 |   53.3 | 45–61    |          94.7 |        0 |            748 |           1   |     4   |        69.8 |          50   |             39.4 |         1     |             5.1 |
| C3-fused+hints  | 150 |   53.3 | 45–61    |          87.3 |        0 |           8149 |           1   |     5.5 |        51.2 |          55.4 |             51.5 |       nan     |           nan   |
| C4-linked+hints | 150 |   56.7 | 49–64    |          94.7 |        0 |          18942 |           6.3 |    39.2 |        65.1 |          54.1 |             51.5 |         0.909 |             5.9 |
| C4-oracle+hints | 150 |   61.3 | 53–69    |          95.3 |        0 |            785 |           1   |     4   |        67.4 |          64.9 |             45.5 |         1     |             5.1 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from            | to              |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:----------------|:----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C3-fused        | C4-linked       |         4.7 | -1.3 to +11.3  |      15 |       8 |      0.21   | no         |
| C4-linked       | C4-oracle       |        14   | +8.0 to +20.7  |      23 |       2 |      0      | yes        |
| C3-fused+hints  | C4-linked+hints |         3.3 | -3.3 to +10.0  |      16 |      11 |      0.4421 | no         |
| C4-linked+hints | C4-oracle+hints |         4.7 | -0.7 to +10.0  |      12 |       5 |      0.1435 | no         |
| C3-fused        | C3-fused+hints  |        18.7 | +11.3 to +26.0 |      33 |       5 |      0      | yes        |
| C4-linked       | C4-linked+hints |        17.3 | +9.3 to +25.3  |      34 |       8 |      0.0001 | yes        |
| C4-oracle       | C4-oracle+hints |         8   | +2.0 to +14.0  |      17 |       5 |      0.0169 | yes        |
| C3-fused        | C4-oracle       |        18.7 | +10.7 to +26.7 |      35 |       7 |      0      | yes        |
| C3-fused+hints  | C4-oracle+hints |         8   | +0.7 to +15.3  |      22 |      10 |      0.0501 | no         |
