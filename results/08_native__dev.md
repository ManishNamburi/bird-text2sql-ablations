# 08 promptfoo-native: C1 ± hints × qwen3.5:9b / qwen2.5-coder:7b, built-in assertions + LLM judge — split `dev`

| prompt          | provider   |   n |   ex |   valid_sql |   is_sql_sqlite |   is_sql_mysql |   single_select |   judge |
|:----------------|:-----------|----:|-----:|------------:|----------------:|---------------:|----------------:|--------:|
| C1-native       | qwen3.5    |  30 | 26.7 |        96.7 |           100   |          100   |             100 |    36.7 |
| C1-native+hints | qwen3.5    |  30 | 33.3 |        93.3 |            96.7 |           96.7 |             100 |    40   |
| C1-native       | coder      |  30 | 26.7 |        83.3 |           100   |           76.7 |             100 |    33.3 |
| C1-native+hints | coder      |  30 | 50   |        83.3 |           100   |           76.7 |             100 |    46.7 |


**Provenance:** Ollama 0.40.16, promptfoo 0.125.1, Node v22.23.5, exported 2026-11-19T08:53Z.
- `qwen2.5-coder:7b`: digest `dae161e27b0e` (7.6B, Q4_K_M, gguf), pulled 2026-11-16T08:59
- `qwen3.5:9b`: digest `d63f830f28d5` (9.7B, nvfp4, mlx), pulled 2026-11-16T08:56
