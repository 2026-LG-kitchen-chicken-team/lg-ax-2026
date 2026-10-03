#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
task_cache="/dev/shm/lg-ax-${USER}"
mkdir -p "$task_root/runtime/logs" "$task_cache/ollama"
ollama_bin="${LGAX_OLLAMA_BINARY:-$(command -v ollama || true)}"
if [[ -z "$ollama_bin" || ! -x "$ollama_bin" ]]; then
  echo 'BLOCKED: set LGAX_OLLAMA_BINARY to the verified local Ollama executable' >&2
  exit 2
fi
if ss -ltn | grep -q ':18864 '; then
  if [[ "${1:-}" != '--restart-own' || ! -f "$task_root/runtime/ollama.pid" ]]; then
    echo 'BLOCKED: port 18864 already occupied' >&2
    exit 2
  fi
  own_pid=$(cat "$task_root/runtime/ollama.pid")
  [[ "$own_pid" =~ ^[0-9]+$ ]]
  # Protect unrelated Ollama processes: match the LG-only endpoint in this exact process.
  tr '\0' '\n' <"/proc/$own_pid/environ" | grep -Fxq 'OLLAMA_HOST=127.0.0.1:18864'
  kill "$own_pid"
  for _ in {1..20}; do
    ss -ltn | grep -q ':18864 ' || break
    sleep 0.2
  done
fi
CUDA_VISIBLE_DEVICES=0 OLLAMA_VULKAN=false GGML_VK_VISIBLE_DEVICES=0 OLLAMA_NO_CLOUD=1 \
OLLAMA_HOST=127.0.0.1:18864 OLLAMA_MODELS="$task_cache/ollama" \
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_CONTEXT_LENGTH=4096 \
nohup "$ollama_bin" serve >"$task_root/runtime/logs/ollama.log" 2>&1 </dev/null &
echo $! >"$task_root/runtime/ollama.pid"
echo 'Started LG-only Ollama endpoint on loopback:18864, CUDA GPU 0, cloud disabled.'
