# 06 prompt trimming on C3: short profiles / masked values / no BIRD values / minimal system, hints on/off — split `test`

| config                 |   n |   EX % | 95% CI   |   valid SQL % |   errors |   prompt tok/q |   LLM calls/q |   sec/q |   EX simple |   EX moderate |   EX challenging |
|:-----------------------|----:|-------:|:---------|--------------:|---------:|---------------:|--------------:|--------:|------------:|--------------:|-----------------:|
| C3-fused               | 468 |   41.5 | 37–46    |          90.4 |        0 |           8074 |             1 |     4.3 |        54.7 |          38.8 |             28.9 |
| T1-short-profile       | 468 |   37   | 33–41    |          90.6 |        0 |           4525 |             1 |     3.6 |        56.8 |          30.6 |             23.7 |
| C3-fused+hints         | 468 |   51.7 | 47–56    |          88.9 |        0 |           8110 |             1 |     4.3 |        63.3 |          47   |             46.4 |
| T1-short-profile+hints | 468 |   50.4 | 46–55    |          91   |        0 |           4561 |             1 |     3.7 |        63.3 |          47.4 |             39.2 |

**Provenance:** Ollama 0.40.16, promptfoo 0.125.1, Node v22.23.5, exported 2026-11-18T00:24Z.
- `qwen3.5:9b`: digest `d63f830f28d5` (9.7B, nvfp4, mlx), pulled 2026-11-16T08:56
