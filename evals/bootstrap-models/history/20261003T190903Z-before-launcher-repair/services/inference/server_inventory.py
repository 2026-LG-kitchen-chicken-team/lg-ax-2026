"""Capture non-secret lab runtime evidence; only enumerate LG's recorded processes."""

import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path


def safe_path(value):
    verified_binary = str(Path.home() / "wave-naru/runtime/bin/ollama")
    verified_lib = str(Path.home() / "wave-naru/runtime/lib/ollama")
    return value.replace(verified_binary, "${VERIFIED_OLLAMA_BINARY}").replace(verified_lib, "${VERIFIED_OLLAMA_LIB}").replace(str(Path.home()), "${HOME}").replace(os.environ["USER"], "${USER}")


def main():
    root = Path.cwd()
    process_table = {}
    for line in subprocess.check_output(["ps", "-eo", "pid=,ppid=,comm=,args="], text=True).splitlines():
        fields = line.strip().split(maxsplit=3)
        if len(fields) == 4:
            pid, parent, name, args = fields
            process_table[int(pid)] = {"pid": int(pid), "parent_pid": int(parent), "name": name, "args": safe_path(args)}
    roots = []
    for service in ["ollama", "lab"]:
        pid_file = root / "runtime" / f"{service}.pid"
        if pid_file.is_file():
            roots.append(int(pid_file.read_text().strip()))
    own = set(roots)
    while True:
        found = {pid for pid, row in process_table.items() if row["parent_pid"] in own}
        if found.issubset(own):
            break
        own.update(found)
    disks = {}
    for path in ["/", "/dev/shm"]:
        values = os.statvfs(path)
        disks[path] = {"total_bytes": values.f_blocks * values.f_frsize, "available_bytes": values.f_bavail * values.f_frsize}
    lines = subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used", "--format=csv,noheader,nounits"], text=True)
    gpus = []
    for line in lines.splitlines():
        index, name, total, used = [part.strip() for part in line.split(",")]
        gpus.append({"index": int(index), "name": name, "memory_total_mib": int(total), "memory_used_mib": int(used),
                     "allocation": "lg_bootstrap" if index == "0" else "protected_existing_service" if index == "1" else "not_allocated"})
    output = {"status": "observed", "timestamp_utc": datetime.now(UTC).isoformat(), "os": platform.platform(), "python": platform.python_version(),
              "distribution": {key: value for key, value in platform.freedesktop_os_release().items() if key in ["ID", "VERSION_ID", "PRETTY_NAME"]},
              "inventory_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "uv_version": subprocess.check_output([str(root / "runtime/bin/uv"), "--version"], text=True).strip(),
              "packages": {name: importlib.metadata.version(name) for name in ["torch", "transformers", "huggingface-hub", "fastapi", "uvicorn"]},
              "gpus": gpus, "disks": disks, "storage": "Dedicated tmpfs cache/environment; lost on reboot", "persistent_workspace": "${HOME}/lg-ax-2026",
              "lg_processes": [process_table[pid] for pid in sorted(own) if pid in process_table],
              "ports": {"ollama": {"host": "127.0.0.1", "port": 18864}, "lab_api": {"host": "127.0.0.1", "port": 18865}},
              "public_mcp_connected": False, "agent_implemented": False, "other_services_changed": False}
    Path("evals/bootstrap-models/server-inventory.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "observed", "lg_process_count": len(output["lg_processes"]), "root_available_bytes": disks["/"]["available_bytes"]}))


if __name__ == "__main__":
    main()
