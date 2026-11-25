# 08 promptfoo-native: C1 ± hints × qwen3.5:9b / qwen2.5-coder:7b, built-in assertions + LLM judge (09_judge) — split `test`

| prompt          | provider   |   n |   ex |   valid_sql |   is_sql_sqlite |   is_sql_mysql |   single_select |   judge |
|:----------------|:-----------|----:|-----:|------------:|----------------:|---------------:|----------------:|--------:|
| C1-native       | qwen3.5    | 468 | 31.6 |        88.9 |            98.1 |           95.1 |            99.1 |    35.3 |
| C1-native+hints | qwen3.5    | 468 | 45.3 |        88.5 |            98.5 |           92.7 |            99.8 |    54.1 |
| C1-native       | coder      | 468 | 34.6 |        89.1 |            98.7 |           88.9 |           100   |    37   |
| C1-native+hints | coder      | 468 | 46.6 |        85.7 |            99.6 |           86.8 |           100   |    56   |


**Provenance:** Ollama 0.40.17, promptfoo 0.125.1, Node v22.23.5, exported 2026-11-25T00:23Z.
- `qwen2.5-coder:7b`: digest `dae161e27b0e` (7.6B, Q4_K_M, gguf), pulled 2026-11-22T12:38
- `qwen3.5:9b`: digest `56671c2ab938` (9.0B, Q4_K_M, llamacpp), pulled 2026-11-22T12:35
