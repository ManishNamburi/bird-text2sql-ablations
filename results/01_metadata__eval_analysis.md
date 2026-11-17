# 01_metadata__eval: paired analysis (150 questions)

## Accuracy and cost per config

| config           |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   EX simple |   EX moderate |   EX challenging |
|:-----------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|------------:|--------------:|-----------------:|
| C0-ddl           | 150 |   24   | 18–31    |          90   |        0 |            824 |             1 |     2.9 |        37.2 |          16.2 |             24.2 |
| C1-bird          | 150 |   32.7 | 26–41    |          94   |        0 |           1910 |             1 |     3.1 |        44.2 |          27   |             30.3 |
| C2-profile       | 150 |   34   | 27–42    |          84.7 |        0 |           7027 |             1 |     5.1 |        37.2 |          33.8 |             30.3 |
| C3-fused         | 150 |   34.7 | 28–43    |          88.7 |        0 |           8112 |             1 |     5.4 |        37.2 |          36.5 |             27.3 |
| C0-ddl+hints     | 150 |   50.7 | 43–59    |          90   |        0 |            861 |             1 |     2.7 |        55.8 |          51.4 |             42.4 |
| C1-bird+hints    | 150 |   51.3 | 43–59    |          92.7 |        0 |           1946 |             1 |     3.1 |        55.8 |          50   |             48.5 |
| C2-profile+hints | 150 |   51.3 | 43–59    |          86.7 |        0 |           7064 |             1 |     5   |        53.5 |          51.4 |             48.5 |
| C3-fused+hints   | 150 |   53.3 | 45–61    |          87.3 |        0 |           8149 |             1 |     5.5 |        51.2 |          55.4 |             51.5 |

## Paired comparisons

`fixed` = questions only the second config gets right; `broke` = only the first. McNemar exact test on those discordant questions; bootstrap CI resamples questions (10,000×).

| from             | to               |   Δ EX (pp) | 95% CI (pp)    |   fixed |   broke |   McNemar p | sig@0.05   |
|:-----------------|:-----------------|------------:|:---------------|--------:|--------:|------------:|:-----------|
| C0-ddl           | C1-bird          |         8.7 | +2.7 to +15.3  |      19 |       6 |      0.0146 | yes        |
| C1-bird          | C2-profile       |         1.3 | -6.7 to +8.7   |      19 |      17 |      0.8679 | no         |
| C2-profile       | C3-fused         |         0.7 | -4.7 to +6.7   |      10 |       9 |      1      | no         |
| C0-ddl+hints     | C1-bird+hints    |         0.7 | -5.3 to +6.7   |      11 |      10 |      1      | no         |
| C1-bird+hints    | C2-profile+hints |         0   | -7.3 to +7.3   |      16 |      16 |      1      | no         |
| C2-profile+hints | C3-fused+hints   |         2   | -4.0 to +8.0   |      12 |       9 |      0.6636 | no         |
| C0-ddl           | C0-ddl+hints     |        26.7 | +19.3 to +34.7 |      43 |       3 |      0      | yes        |
| C1-bird          | C1-bird+hints    |        18.7 | +12.0 to +25.3 |      30 |       2 |      0      | yes        |
| C2-profile       | C2-profile+hints |        17.3 | +9.3 to +25.3  |      35 |       9 |      0.0001 | yes        |
| C3-fused         | C3-fused+hints   |        18.7 | +11.3 to +26.0 |      33 |       5 |      0      | yes        |
| C0-ddl           | C2-profile       |        10   | +2.7 to +17.3  |      25 |      10 |      0.0167 | yes        |
| C0-ddl           | C3-fused         |        10.7 | +2.7 to +18.7  |      28 |      12 |      0.0166 | yes        |
| C1-bird          | C3-fused         |         2   | -6.0 to +10.0  |      20 |      17 |      0.7428 | no         |
| C0-ddl+hints     | C3-fused+hints   |         2.7 | -4.7 to +10.0  |      18 |      14 |      0.5966 | no         |
