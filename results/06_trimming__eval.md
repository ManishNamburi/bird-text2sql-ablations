# 06 prompt trimming on C3: short profiles / masked values / no BIRD values / minimal system, hints on/off — split `eval`

| config                  |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   EX simple |   EX moderate |   EX challenging |
|:------------------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|------------:|--------------:|-----------------:|
| C3-fused                | 150 |   34.7 | 28–43    |          88.7 |        0 |           8112 |             1 |     5.4 |        37.2 |          36.5 |             27.3 |
| T1-short-profile        | 150 |   35.3 | 28–43    |          92.7 |        0 |           4546 |             1 |     4.5 |        51.2 |          31.1 |             24.2 |
| T2-masked-values        | 150 |   28   | 21–36    |          91.3 |        0 |           7258 |             1 |     5   |        39.5 |          21.6 |             27.3 |
| T3-no-bird-values       | 150 |   33.3 | 26–41    |          87.3 |        0 |           7483 |             1 |     5.1 |        41.9 |          31.1 |             27.3 |
| T4-minimal-system       | 150 |   38.7 | 31–47    |          90   |        0 |           8061 |             1 |     5.7 |        53.5 |          35.1 |             27.3 |
| C3-fused+hints          | 150 |   53.3 | 45–61    |          87.3 |        0 |           8149 |             1 |     5.5 |        51.2 |          55.4 |             51.5 |
| T1-short-profile+hints  | 150 |   51.3 | 43–59    |          91.3 |        0 |           4583 |             1 |     4.6 |        55.8 |          54.1 |             39.4 |
| T2-masked-values+hints  | 150 |   42.7 | 35–51    |          86   |        0 |           7295 |             1 |     5   |        41.9 |          45.9 |             36.4 |
| T3-no-bird-values+hints | 150 |   50   | 42–58    |          86.7 |        0 |           7520 |             1 |     5.1 |        46.5 |          51.4 |             51.5 |
| T4-minimal-system+hints | 150 |   52   | 44–60    |          86.7 |        0 |           8098 |             1 |     5.5 |        55.8 |          54.1 |             42.4 |

**Provenance:** Ollama 0.40.16, promptfoo 0.125.1, Node v22.23.5, exported 2026-11-17T18:51Z.
- `qwen3.5:9b`: digest `d63f830f28d5` (9.7B, nvfp4, mlx), pulled 2026-11-16T08:56
