#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
task_cache="/dev/shm/lg-ax-${USER}"
export HF_HOME="$task_cache/huggingface" HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
cd "$task_root"
exec "$task_cache/venv/bin/python" "$@"
