# 06 prompt trimming on C3: short profiles / masked values / no BIRD values / minimal system, hints on/off — split `dev`

| config                  |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   EX simple |   EX moderate |   EX challenging |
|:------------------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|------------:|--------------:|-----------------:|
| C3-fused                |  30 |   30   | 17–48    |          93.3 |        0 |           8579 |             1 |    18.6 |        44.4 |          31.2 |                0 |
| T1-short-profile        |  30 |   26.7 | 14–44    |          96.7 |        0 |           4840 |             1 |    12.8 |        33.3 |          25   |               20 |
| T2-masked-values        |  30 |   26.7 | 14–44    |          96.7 |        0 |           7731 |             1 |    15.4 |        33.3 |          31.2 |                0 |
| T3-no-bird-values       |  30 |   26.7 | 14–44    |          90   |        0 |           7906 |             1 |    15.8 |        44.4 |          25   |                0 |
| T4-minimal-system       |  30 |   33.3 | 19–51    |          93.3 |        0 |           8528 |             1 |    17.7 |        44.4 |          31.2 |               20 |
| C3-fused+hints          |  30 |   43.3 | 27–61    |          86.7 |        0 |           8620 |             1 |    18   |        44.4 |          50   |               20 |
| T1-short-profile+hints  |  30 |   40   | 25–58    |          90   |        0 |           4881 |             1 |    12.9 |        44.4 |          43.8 |               20 |
| T2-masked-values+hints  |  30 |   46.7 | 30–64    |          96.7 |        0 |           7772 |             1 |    15.3 |        44.4 |          50   |               40 |
| T3-no-bird-values+hints |  30 |   43.3 | 27–61    |          90   |        0 |           7947 |             1 |    15.6 |        44.4 |          50   |               20 |
| T4-minimal-system+hints |  30 |   40   | 25–58    |          83.3 |        0 |           8569 |             1 |    17.5 |        44.4 |          43.8 |               20 |

**Provenance:** Ollama 0.40.16, promptfoo 0.125.1, Node v22.23.5, exported 2026-11-17T17:01Z.
- `qwen3.5:9b`: digest `d63f830f28d5` (9.7B, nvfp4, mlx), pulled 2026-11-16T08:56
