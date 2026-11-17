# 03_fewshot__dev: paired analysis (30 questions)

## Accuracy and cost per config

| config            |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:------------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked         |  30 |   40   | 25–58    |          90   |        0 |          18525 |           6.2 |    58   |         0.93  |             6.3 |        66.7 |          31.2 |               20 |
| C5-train          |  30 |   36.7 | 22–54    |          90   |        0 |          19155 |           6.2 |    58   |         0.93  |             6.3 |        33.3 |          43.8 |               20 |
| C5-querylog       |  30 |   43.3 | 27–61    |          93.3 |        0 |          19282 |           6.2 |    59.2 |         0.93  |             6.3 |        33.3 |          56.2 |               20 |
| C4-linked+hints   |  30 |   53.3 | 36–70    |          86.7 |        0 |          18200 |           6   |    54.2 |         0.927 |             5.4 |        77.8 |          50   |               20 |
| C5-train+hints    |  30 |   33.3 | 19–51    |          90   |        0 |          19090 |           6   |    56.8 |         0.927 |             5.4 |        33.3 |          43.8 |                0 |
| C5-querylog+hints |  30 |   30   | 17–48    |          96.7 |        0 |          19154 |           6   |    56.6 |         0.927 |             5.4 |        33.3 |          31.2 |               20 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from            | to                |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:----------------|:------------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked       | C5-train          |        -3.3 | -23.3 to +16.7 |       4 |       5 |      1      | no         |
| C5-train        | C5-querylog       |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
| C4-linked+hints | C5-train+hints    |       -20   | -40.0 to +0.0  |       2 |       8 |      0.1094 | no         |
| C5-train+hints  | C5-querylog+hints |        -3.3 | -16.7 to +10.0 |       2 |       3 |      1      | no         |
| C4-linked       | C4-linked+hints   |        13.3 | -6.7 to +33.3  |       7 |       3 |      0.3438 | no         |
| C5-train        | C5-train+hints    |        -3.3 | -16.7 to +10.0 |       2 |       3 |      1      | no         |
| C5-querylog     | C5-querylog+hints |       -13.3 | -30.0 to +0.0  |       1 |       5 |      0.2188 | no         |
| C4-linked+hints | C5-querylog+hints |       -23.3 | -46.7 to +0.0  |       3 |      10 |      0.0923 | no         |
