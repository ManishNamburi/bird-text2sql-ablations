#!/bin/zsh
# GPU job queue: wait for the running experiment-01 eval run, then build few-shot pools and
# verify experiments 02/03 on the dev slice. Sequential on purpose: concurrent LLM jobs
# thrash Ollama's prefix cache and distort timings (D8). Stops on the first failure.
set -e
cd "$(dirname "$0")/.."
while pgrep -f "run_ablation.py promptfoo/configs/01_metadata.yaml --split eval" >/dev/null; do sleep 30; done
echo "[$(date +%H:%M)] eval run finished; building few-shot pools"
uv run python scripts/build_fewshot.py
echo "[$(date +%H:%M)] experiment 02 (linking) on dev"
uv run python -u scripts/run_ablation.py promptfoo/configs/02_linking.yaml --split dev
echo "[$(date +%H:%M)] experiment 03 (few-shot) on dev"
uv run python -u scripts/run_ablation.py promptfoo/configs/03_fewshot.yaml --split dev
echo "[$(date +%H:%M)] queue done"
