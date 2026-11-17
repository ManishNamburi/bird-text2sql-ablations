# One-word entry points. promptfoo needs Node >= 22.22; Homebrew's keg-only node@22 is used
# without touching the system Node.
NODE22 := /opt/homebrew/opt/node@22/bin
export PATH := $(NODE22):$(PATH)
export PROMPTFOO_PYTHON := $(CURDIR)/.venv/bin/python
export PROMPTFOO_CONFIG_DIR := $(CURDIR)/.promptfoo
export PROMPTFOO_DISABLE_TELEMETRY := 1

SPLIT ?= dev

.PHONY: setup data test splits metadata fewshot run-01 run-02 run-03 run-04 run-05 run-06 csv summary view

setup:            ## install Python + Node deps and pull models
	uv sync
	npm ci
	ollama pull qwen3.5:9b
	ollama pull qwen2.5-coder:7b
	ollama pull nomic-embed-text

data:             ## download MiniDev (801 MB) and cache gold results
	mkdir -p data/raw
	test -f data/raw/minidev.zip || curl -L --fail -o data/raw/minidev.zip https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip
	unzip -q -o data/raw/minidev.zip 'minidev/MINIDEV/*' -x '*mysql*' '*postgresql*' -d data/raw/
	uv run python scripts/cache_gold.py

splits:           ## (re)build frozen splits and promptfoo test files
	uv run python scripts/make_subset.py
	uv run python scripts/build_tests.py

metadata:         ## profile DBs (~1 min), LLM-summarize columns (~70 min), build indexes
	uv run python scripts/profile_db.py
	uv run python scripts/summarize_profiles.py
	uv run python scripts/build_indexes.py
	uv run python scripts/audit_summaries.py

fewshot:          ## download few-shot pools (3.6 MB) and mask + embed them (~1.5 h of LLM time)
	mkdir -p data/raw/bird_train data/raw/bird_dev
	test -f data/raw/bird_train/train.jsonl || curl -sL --fail -o data/raw/bird_train/train.jsonl https://huggingface.co/datasets/birdsql/bird23-train-filtered/resolve/main/data/train-00000-of-00001.jsonl
	test -f data/raw/bird_dev/dev_20251106.json || curl -sL --fail -o data/raw/bird_dev/dev_20251106.json https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/main/data/dev_20251106-00000-of-00001.json
	uv run python scripts/build_fewshot.py

test:             ## evaluator + schema unit tests
	uv run pytest -q

run-01:           ## metadata ladder; make run-01 SPLIT=eval
	uv run python scripts/run_ablation.py promptfoo/configs/01_metadata.yaml --split $(SPLIT)

run-02:           ## schema linking; make run-02 SPLIT=eval
	uv run python scripts/run_ablation.py promptfoo/configs/02_linking.yaml --split $(SPLIT)

run-03:           ## few-shot; make run-03 SPLIT=eval
	uv run python scripts/run_ablation.py promptfoo/configs/03_fewshot.yaml --split $(SPLIT)

run-04:           ## 3 candidates + majority vote (C6); make run-04 SPLIT=eval
	uv run python scripts/run_ablation.py promptfoo/configs/04_voting.yaml --split $(SPLIT)

run-05:           ## SQL sanity checks + correction (C7); make run-05 SPLIT=eval
	uv run python scripts/run_ablation.py promptfoo/configs/05_checks.yaml --split $(SPLIT)

run-06:           ## prompt trimming T1-T4 on C3; make run-06 SPLIT=eval
	uv run python scripts/run_ablation.py promptfoo/configs/06_trimming.yaml --split $(SPLIT)

csv:              ## merge the local eval runs into results/per_question.csv (needs results/raw/)
	uv run python analysis/export_csv.py

summary:          ## results/summary.md + docs/figures/ from the committed per_question.csv
	uv run python analysis/summary.py

view:             ## open promptfoo's web UI on this project's evals
	npx promptfoo view -y
