# 03b_fewshot_framing__dev: paired analysis (30 questions)

## Accuracy and cost per config

| config                          |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   link recall |   linked cols/q |   EX simple |   EX moderate |   EX challenging |
|:--------------------------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|--------------:|----------------:|------------:|--------------:|-----------------:|
| C4-linked                       |  30 |   40   | 25–58    |          90   |        0 |          18525 |           6.2 |    54.4 |         0.93  |             6.3 |        66.7 |          31.2 |               20 |
| C5-querylog                     |  30 |   43.3 | 27–61    |          93.3 |        0 |          19282 |           6.2 |    57.3 |         0.93  |             6.3 |        33.3 |          56.2 |               20 |
| C5-querylog-sep                 |  30 |   53.3 | 36–70    |          93.3 |        0 |          19324 |           6.2 |    57.3 |         0.93  |             6.3 |        44.4 |          62.5 |               40 |
| C5-train                        |  30 |   36.7 | 22–54    |          90   |        0 |          19155 |           6.2 |    57.4 |         0.93  |             6.3 |        33.3 |          43.8 |               20 |
| C5-train-sep                    |  30 |   43.3 | 27–61    |          86.7 |        0 |          19197 |           6.2 |    56.8 |         0.93  |             6.3 |        44.4 |          50   |               20 |
| C4-linked+hints                 |  30 |   53.3 | 36–70    |          86.7 |        0 |          18200 |           6   |    54.2 |         0.927 |             5.4 |        77.8 |          50   |               20 |
| C5-querylog+hints               |  30 |   30   | 17–48    |          96.7 |        0 |          19154 |           6   |    56.6 |         0.927 |             5.4 |        33.3 |          31.2 |               20 |
| C5-querylog-sep+hints           |  30 |   56.7 | 39–73    |          93.3 |        0 |          19196 |           6   |    57.2 |         0.927 |             5.4 |        44.4 |          68.8 |               40 |
| C5-querylog-sep-noexhints+hints |  30 |   63.3 | 46–78    |          86.7 |        0 |          18999 |           6   |    56.2 |         0.927 |             5.4 |        44.4 |          75   |               60 |
| C5-train+hints                  |  30 |   33.3 | 19–51    |          90   |        0 |          19090 |           6   |    56.8 |         0.927 |             5.4 |        33.3 |          43.8 |                0 |
| C5-train-sep+hints              |  30 |   60   | 42–75    |          96.7 |        0 |          19132 |           6   |    57.7 |         0.927 |             5.4 |        66.7 |          62.5 |               40 |
| C5-train-sep-noexhints+hints    |  30 |   50   | 33–67    |          86.7 |        0 |          18873 |           6   |    54.8 |         0.927 |             5.4 |        44.4 |          56.2 |               40 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from                            | to                              |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:--------------------------------|:--------------------------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C4-linked                       | C5-querylog                     |         3.3 | -16.7 to +23.3 |       6 |       5 |      1      | no         |
| C5-querylog                     | C5-querylog-sep                 |        10   | -3.3 to +23.3  |       4 |       1 |      0.375  | no         |
| C5-querylog-sep                 | C5-train                        |       -16.7 | -33.3 to +0.0  |       1 |       6 |      0.125  | no         |
| C5-train                        | C5-train-sep                    |         6.7 | -6.7 to +20.0  |       3 |       1 |      0.625  | no         |
| C4-linked+hints                 | C5-querylog+hints               |       -23.3 | -46.7 to +0.0  |       3 |      10 |      0.0923 | no         |
| C5-querylog+hints               | C5-querylog-sep+hints           |        26.7 | +13.3 to +43.3 |       8 |       0 |      0.0078 | yes        |
| C5-querylog-sep+hints           | C5-querylog-sep-noexhints+hints |         6.7 | +0.0 to +16.7  |       2 |       0 |      0.5    | no         |
| C5-querylog-sep-noexhints+hints | C5-train+hints                  |       -30   | -46.7 to -13.3 |       0 |       9 |      0.0039 | yes        |
| C5-train+hints                  | C5-train-sep+hints              |        26.7 | +10.0 to +46.7 |       9 |       1 |      0.0215 | yes        |
| C5-train-sep+hints              | C5-train-sep-noexhints+hints    |       -10   | -23.3 to +0.0  |       0 |       3 |      0.25   | no         |
| C4-linked                       | C4-linked+hints                 |        13.3 | -6.7 to +33.3  |       7 |       3 |      0.3438 | no         |
| C5-querylog                     | C5-querylog+hints               |       -13.3 | -30.0 to +0.0  |       1 |       5 |      0.2188 | no         |
| C5-querylog-sep                 | C5-querylog-sep+hints           |         3.3 | +0.0 to +10.0  |       1 |       0 |      1      | no         |
| C5-train                        | C5-train+hints                  |        -3.3 | -16.7 to +10.0 |       2 |       3 |      1      | no         |
| C5-train-sep                    | C5-train-sep+hints              |        16.7 | -3.3 to +36.7  |       8 |       3 |      0.2266 | no         |
| C5-querylog+hints               | C5-querylog-sep+hints           |        26.7 | +13.3 to +43.3 |       8 |       0 |      0.0078 | yes        |
| C5-train+hints                  | C5-train-sep+hints              |        26.7 | +10.0 to +46.7 |       9 |       1 |      0.0215 | yes        |
| C4-linked                       | C5-querylog-sep                 |        13.3 | -10.0 to +36.7 |       8 |       4 |      0.3877 | no         |
| C4-linked+hints                 | C5-querylog-sep+hints           |         3.3 | -20.0 to +23.3 |       6 |       5 |      1      | no         |
| C4-linked+hints                 | C5-train-sep+hints              |         6.7 | -10.0 to +26.7 |       5 |       3 |      0.7266 | no         |
