#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
task_cache="/dev/shm/lg-ax-${USER}"
guard_python="$task_cache/venv/bin/python"
mkdir -p "$task_root/runtime/logs" "$task_cache/ollama"
ollama_bin="${LGAX_OLLAMA_BINARY:-$(command -v ollama || true)}"
if [[ -z "$ollama_bin" || ! -x "$ollama_bin" || ! -x "$guard_python" ]]; then
  echo 'BLOCKED: verified Ollama executable and dedicated Python runtime are required' >&2
  exit 2
fi
restart_args=()
if [[ "${1:-}" == '--restart-own' ]]; then
  restart_args=(--restart-own)
elif [[ $# != 0 ]]; then
  echo 'BLOCKED: only --restart-own is accepted' >&2
  exit 2
fi
"$guard_python" "$task_root/services/inference/launcher_guard.py" prepare ollama \
  --ollama-binary "$ollama_bin" "${restart_args[@]}"
cd "$task_root"
CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 OLLAMA_VULKAN=false GGML_VK_VISIBLE_DEVICES=0 OLLAMA_NO_CLOUD=1 \
OLLAMA_HOST=127.0.0.1:18864 OLLAMA_MODELS="$task_cache/ollama" \
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_CONTEXT_LENGTH=4096 \
nohup "$ollama_bin" serve >runtime/logs/ollama.log 2>&1 </dev/null &
started_pid=$!
if ! "$guard_python" services/inference/launcher_guard.py ready ollama --pid "$started_pid" --ollama-binary "$ollama_bin"; then
  echo 'Ollama startup failed; inspect the LG-only runtime/logs/ollama.log.' >&2
  tail -c 1200 runtime/logs/ollama.log >&2
  exit 2
fi
echo 'Started and verified LG-only Ollama on loopback:18864, CUDA GPU 0.'
