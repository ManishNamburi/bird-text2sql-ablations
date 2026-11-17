# 03_fewshot__eval: paired analysis (150 questions)

## Accuracy and cost per config

| config                |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:----------------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked             | 150 |   39.3 | 32–47    |          94.7 |        0 |          18387 |           6.3 |    40.8 |         0.85  |             6.5 |        55.8 |          36.5 |             24.2 |
| C5-train-sep          | 150 |   38   | 31–46    |          86   |        0 |          19037 |           6.3 |    42.9 |         0.85  |             6.5 |        58.1 |          33.8 |             21.2 |
| C5-querylog-sep       | 150 |   39.3 | 32–47    |          88   |        0 |          19356 |           6.3 |    44.1 |         0.85  |             6.5 |        48.8 |          37.8 |             30.3 |
| C5-querylog           | 150 |   34   | 27–42    |          88.7 |        0 |          19314 |           6.3 |    43.9 |         0.85  |             6.5 |        53.5 |          28.4 |             21.2 |
| C4-linked+hints       | 150 |   56.7 | 49–64    |          94.7 |        0 |          18942 |           6.3 |    39.2 |         0.909 |             5.9 |        65.1 |          54.1 |             51.5 |
| C5-train-sep+hints    | 150 |   48.7 | 41–57    |          84   |        0 |          19842 |           6.3 |    42.4 |         0.909 |             5.9 |        58.1 |          51.4 |             30.3 |
| C5-querylog-sep+hints | 150 |   56   | 48–64    |          92   |        0 |          20115 |           6.3 |    43.4 |         0.909 |             5.9 |        62.8 |          55.4 |             48.5 |
| C5-querylog+hints     | 150 |   39.3 | 32–47    |          90   |        0 |          20073 |           6.3 |    43.2 |         0.909 |             5.9 |        51.2 |          36.5 |             30.3 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from                  | to                    |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:----------------------|:----------------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked             | C5-train-sep          |        -1.3 | -8.0 to +5.3   |      11 |      13 |      0.8388 | no         |
| C5-train-sep          | C5-querylog-sep       |         1.3 | -6.0 to +9.3   |      18 |      16 |      0.8642 | no         |
| C5-querylog-sep       | C5-querylog           |        -5.3 | -12.7 to +2.7  |      13 |      21 |      0.2295 | no         |
| C4-linked+hints       | C5-train-sep+hints    |        -8   | -14.7 to -1.3  |       8 |      20 |      0.0357 | yes        |
| C5-train-sep+hints    | C5-querylog-sep+hints |         7.3 | -0.7 to +15.3  |      24 |      13 |      0.0989 | no         |
| C5-querylog-sep+hints | C5-querylog+hints     |       -16.7 | -24.0 to -9.3  |       6 |      31 |      0      | yes        |
| C4-linked             | C4-linked+hints       |        17.3 | +9.3 to +25.3  |      34 |       8 |      0.0001 | yes        |
| C5-train-sep          | C5-train-sep+hints    |        10.7 | +4.0 to +17.3  |      23 |       7 |      0.0052 | yes        |
| C5-querylog-sep       | C5-querylog-sep+hints |        16.7 | +10.0 to +24.0 |      30 |       5 |      0      | yes        |
| C5-querylog           | C5-querylog+hints     |         5.3 | -2.0 to +12.7  |      21 |      13 |      0.2295 | no         |
| C4-linked             | C5-querylog-sep       |         0   | -7.3 to +7.3   |      15 |      15 |      1      | no         |
| C4-linked+hints       | C5-querylog-sep+hints |        -0.7 | -7.3 to +6.0   |      13 |      14 |      1      | no         |
| C4-linked             | C5-querylog           |        -5.3 | -13.3 to +2.7  |      15 |      23 |      0.2559 | no         |
| C4-linked+hints       | C5-querylog+hints     |       -17.3 | -26.0 to -9.3  |      10 |      36 |      0.0002 | yes        |
