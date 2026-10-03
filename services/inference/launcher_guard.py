"""Fail-closed identity, GPU, bind and health checks for the two dedicated LG services."""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class Blocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Service:
    name: str
    root: Path
    cache: Path
    executable: Path
    port: int

    @property
    def pid_file(self):
        return self.root / "runtime" / f"{self.name}.pid"


def inspect_process(pid):
    process = Path(f"/proc/{pid}")
    try:
        entries = process.joinpath("environ").read_bytes().split(b"\0")
        environment = dict(entry.decode().split("=", 1) for entry in entries if b"=" in entry)
        return {"uid": process.stat().st_uid, "executable": Path(os.readlink(process / "exe")),
                "cwd": Path(os.readlink(process / "cwd")), "environment": environment,
                "arguments": [part.decode() for part in (process / "cmdline").read_bytes().split(b"\0") if part]}
    except (OSError, UnicodeError) as error:
        raise Blocked(f"Cannot inspect process {pid}") from error


def assert_identity(service, state):
    if state["uid"] != os.getuid():
        raise Blocked("Process UID differs from the current user")
    if state["executable"].resolve() != service.executable.resolve():
        raise Blocked("Process executable differs from the dedicated launcher")
    if state["cwd"].resolve() != service.root.resolve():
        raise Blocked("Process cwd differs from the dedicated LG workspace")
    if service.name == "ollama":
        expected = {"OLLAMA_HOST": f"127.0.0.1:{service.port}", "OLLAMA_MODELS": str(service.cache / "ollama"),
                    "OLLAMA_NO_CLOUD": "1", "OLLAMA_VULKAN": "false", "CUDA_VISIBLE_DEVICES": "0"}
        if any(state["environment"].get(key) != value for key, value in expected.items()):
            raise Blocked("Ollama endpoint/cache/GPU environment differs from the LG configuration")
        if len(state["arguments"]) != 2 or state["arguments"][1] != "serve":
            raise Blocked("Process is not the dedicated Ollama serve command")
    else:
        if state["environment"].get("HF_HOME") != str(service.cache / "huggingface"):
            raise Blocked("API model cache differs from the LG configuration")
        expected = ["services/inference/server.py", "--port", str(service.port)]
        if state["arguments"][1:] != expected:
            raise Blocked("Process is not the dedicated LG API command")


def parse_listeners(output, port):
    owners = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[3] != f"127.0.0.1:{port}":
            raise Blocked("Port is bound outside the exact loopback endpoint")
        matches = re.findall(r"pid=(\d+)", line)
        if not matches:
            raise Blocked("Port owner is hidden or unknown")
        owners.update(map(int, matches))
    return owners


def listeners(service):
    result = subprocess.run(["ss", "-H", "-ltnp", "sport", "=", f":{service.port}"], capture_output=True, text=True, check=True)
    return parse_listeners(result.stdout, service.port)


def gpu_pids():
    result = subprocess.run(["nvidia-smi", "-i", "0", "--query-compute-apps=pid", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True)
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if any(not row.isdecimal() for row in rows):
        raise Blocked("Cannot identify GPU 0 compute process ownership")
    return {int(row) for row in rows}


def descendant(pid, ancestor):
    for _ in range(128):
        if pid == ancestor:
            return True
        try:
            status = Path(f"/proc/{pid}/status").read_text()
            pid = int(next(line.split()[1] for line in status.splitlines() if line.startswith("PPid:")))
        except (OSError, StopIteration, ValueError):
            return False
        if pid <= 1:
            return False
    return False


def assert_gpu_available(own_pid=None):
    foreign = {pid for pid in gpu_pids() if own_pid is None or not descendant(pid, own_pid)}
    if foreign:
        raise Blocked(f"GPU 0 is occupied by other compute process IDs: {sorted(foreign)}")


def process_alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def wait_released(service, pid, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_alive(pid) and not listeners(service):
            if service.name == "ollama":
                assert_gpu_available()
            return
        time.sleep(0.2)
    raise Blocked(f"PID {pid} or port {service.port} did not terminate/release within {timeout}s")


def prepare(service, restart, timeout):
    owners = listeners(service)
    if owners:
        if not restart or not service.pid_file.is_file():
            raise Blocked(f"Port {service.port} is occupied; no verified --restart-own request")
        try:
            pid = int(service.pid_file.read_text().strip())
        except ValueError as error:
            raise Blocked("Recorded service PID is invalid") from error
        assert_identity(service, inspect_process(pid))
        if owners != {pid}:
            raise Blocked("Recorded PID is not the exact port owner")
        if service.name == "ollama":
            assert_gpu_available(pid)
        os.kill(pid, signal.SIGTERM)
        wait_released(service, pid, timeout)
    elif service.pid_file.is_file():
        try:
            old_pid = int(service.pid_file.read_text().strip())
        except ValueError as error:
            raise Blocked("Recorded service PID is invalid") from error
        if process_alive(old_pid):
            raise Blocked("Recorded process is alive without the service port; inspect it before starting")
    if service.name == "ollama":
        assert_gpu_available()


def read_health(service):
    route = "/api/version" if service.name == "ollama" else "/health"
    with urllib.request.urlopen(f"http://127.0.0.1:{service.port}{route}", timeout=2) as response:
        output = json.load(response)
    if service.name == "ollama":
        if not isinstance(output.get("version"), str):
            raise Blocked("Ollama health/version response is invalid")
    elif not (output.get("service") == "lgax-private-lab" and output.get("generation_status") == "ready"
              and output.get("access_boundary") == "loopback-only" and output.get("agent_implemented") is False
              and output.get("source_sha256") == sha256((service.root / "services/inference/server.py").read_bytes()).hexdigest()):
        raise Blocked("Dedicated API health, verified model or running source is not ready")
    return output


def ready(service, pid, timeout):
    deadline = time.monotonic() + timeout
    reason = "service did not become ready"
    while time.monotonic() < deadline:
        if not process_alive(pid):
            raise Blocked("Started process exited before bind/health success")
        try:
            assert_identity(service, inspect_process(pid))
            if listeners(service) != {pid}:
                raise Blocked("Started process does not own the exact port")
            if service.name == "ollama":
                assert_gpu_available(pid)
            health = read_health(service)
            temporary = service.pid_file.with_suffix(".pid.pending")
            temporary.write_text(str(pid) + "\n", encoding="utf-8", newline="\n")
            temporary.replace(service.pid_file)
            return health
        except (Blocked, OSError, ValueError) as error:
            reason = str(error)
        time.sleep(0.2)
    raise Blocked(f"Bind/health did not succeed within {timeout}s: {reason}")


def stop_failed_candidate(service, pid):
    if process_alive(pid):
        assert_identity(service, inspect_process(pid))
        os.kill(pid, signal.SIGTERM)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "ready"])
    parser.add_argument("service", choices=["ollama", "lab"])
    parser.add_argument("--restart-own", action="store_true")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--timeout", type=int, default=20, choices=range(1, 61))
    parser.add_argument("--ollama-binary")
    args = parser.parse_args()
    root = Path.home() / "lg-ax-2026"
    cache = Path("/dev/shm") / f"lg-ax-{os.environ['USER']}"
    if args.service == "ollama" and not args.ollama_binary:
        parser.error("Ollama requires its verified executable path")
    executable = Path(args.ollama_binary) if args.service == "ollama" else cache / "venv/bin/python"
    service = Service(args.service, root, cache, executable, 18864 if args.service == "ollama" else 18865)
    try:
        if args.action == "prepare":
            prepare(service, args.restart_own, args.timeout)
            print(json.dumps({"status": "prepared", "service": service.name, "port": service.port}))
        else:
            if args.pid is None or args.pid <= 1:
                parser.error("Ready check requires the newly created PID")
            try:
                health = ready(service, args.pid, args.timeout)
            except (Blocked, subprocess.SubprocessError):
                stop_failed_candidate(service, args.pid)
                raise
            print(json.dumps({"status": "started_and_verified", "service": service.name, "pid": args.pid, "port": service.port,
                              "identity": "uid+executable+cwd+environment+port_owner", "health": health}))
    except (Blocked, OSError, subprocess.SubprocessError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
