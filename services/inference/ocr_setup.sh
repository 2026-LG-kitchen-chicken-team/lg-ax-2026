#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
task_cache="/dev/shm/lg-ax-${USER}"
export UV_CACHE_DIR="$task_cache/uv-cache" UV_PYTHON_INSTALL_DIR="$task_cache/python" TMPDIR="$task_cache/tmp"
export HF_HOME="$task_cache/huggingface" PADDLE_PDX_CACHE_HOME="$task_cache/paddlex"
export PADDLE_HOME="$task_cache/paddle" XDG_CACHE_HOME="$task_cache/xdg-cache"
mkdir -p "$TMPDIR" "$PADDLE_HOME" "$XDG_CACHE_HOME" "$PADDLE_PDX_CACHE_HOME"
if [[ ! -x "$task_cache/ocr-venv/bin/python" ]]; then
  "$task_root/runtime/bin/uv" venv --python 3.11.17 "$task_cache/ocr-venv"
fi
"$task_root/runtime/bin/uv" pip install --python "$task_cache/ocr-venv/bin/python" paddlepaddle==3.0.0 \
  --index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/
"$task_root/runtime/bin/uv" pip install --python "$task_cache/ocr-venv/bin/python" \
  paddleocr==3.2.0 'paddlex[ocr]==3.2.0' huggingface-hub==0.36.0 pillow==11.3.0 \
  numpy==1.26.4 opencv-contrib-python==4.10.0.84
cd "$task_root"
exec "$task_cache/ocr-venv/bin/python" services/inference/ocr_benchmark.py
