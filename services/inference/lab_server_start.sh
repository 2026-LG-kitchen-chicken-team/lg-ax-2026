#!/usr/bin/env bash
set -euo pipefail
task_root="$HOME/lg-ax-2026"
task_cache="/dev/shm/lg-ax-${USER}"
guard_python="$task_cache/venv/bin/python"
mkdir -p "$task_root/runtime/logs"
restart_args=()
if [[ "${1:-}" == '--restart-own' ]]; then
  restart_args=(--restart-own)
elif [[ $# != 0 ]]; then
  echo 'BLOCKED: only --restart-own is accepted' >&2
  exit 2
fi
"$guard_python" "$task_root/services/inference/launcher_guard.py" prepare lab "${restart_args[@]}"
cd "$task_root"
nohup bash services/inference/run_lab.sh services/inference/server.py --port 18865 \
  >runtime/logs/lab.log 2>&1 </dev/null &
started_pid=$!
if ! "$guard_python" services/inference/launcher_guard.py ready lab --pid "$started_pid"; then
  echo 'API startup failed; inspect the LG-only runtime/logs/lab.log.' >&2
  tail -c 1200 runtime/logs/lab.log >&2
  exit 2
fi
echo 'Started and verified LG-only API on loopback:18865.'
