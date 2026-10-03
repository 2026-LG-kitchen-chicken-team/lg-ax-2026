#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
mkdir -p "$task_root/runtime/logs"
if ss -ltn | grep -q ':18865 '; then
  if [[ "${1:-}" != '--restart-own' || ! -f "$task_root/runtime/lab.pid" ]]; then
    echo 'BLOCKED: port 18865 already occupied' >&2
    exit 2
  fi
  own_pid=$(cat "$task_root/runtime/lab.pid")
  [[ "$own_pid" =~ ^[0-9]+$ ]]
  [[ "$(readlink "/proc/$own_pid/cwd")" == "$task_root" ]]
  tr '\0' ' ' <"/proc/$own_pid/cmdline" | grep -Fq 'services/inference/server.py --port 18865'
  kill "$own_pid"
  for _ in {1..20}; do
    ss -ltn | grep -q ':18865 ' || break
    sleep 0.2
  done
fi
cd "$task_root"
nohup bash services/inference/run_lab.sh services/inference/server.py --port 18865 \
  >runtime/logs/lab.log 2>&1 </dev/null &
echo $! >runtime/lab.pid
echo 'Started LG-only private health/generation API on loopback:18865.'
