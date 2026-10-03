#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
task_cache="/dev/shm/lg-ax-${USER}"
mkdir -p "$task_root/runtime/bin" "$task_root/runtime/logs" "$task_cache"
chmod 700 "$task_cache"
available_bytes=$(df -B1 --output=avail "$task_root" | tail -1 | tr -d ' ')
if (( available_bytes < 5368709120 )); then
  echo 'BLOCKED: root disk reserve under 5 GiB' >&2
  exit 2
fi
export UV_INSTALL_DIR="$task_root/runtime/bin" UV_NO_MODIFY_PATH=1
export UV_CACHE_DIR="$task_cache/uv-cache" UV_PYTHON_INSTALL_DIR="$task_cache/python"
export TMPDIR="$task_cache/tmp" HF_HOME="$task_cache/huggingface"
mkdir -p "$TMPDIR" "$HF_HOME"
if [[ ! -x "$UV_INSTALL_DIR/uv" ]]; then
  curl --fail --silent --show-error --location https://astral.sh/uv/0.12.23/install.sh | sh
fi
"$UV_INSTALL_DIR/uv" python install 3.11.17
if [[ ! -x "$task_cache/venv/bin/python" ]]; then
  "$UV_INSTALL_DIR/uv" venv --python 3.11.17 "$task_cache/venv"
fi
"$UV_INSTALL_DIR/uv" pip install --python "$task_cache/venv/bin/python" torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
"$UV_INSTALL_DIR/uv" pip install --python "$task_cache/venv/bin/python" -r "$task_root/services/inference/requirements-cpu.txt"
printf 'Runtime created in %s; no global Python or existing services changed.\n' "$task_cache"
