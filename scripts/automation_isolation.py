"""Owner-only Docker setup/proof. Never enables automation or copies a login."""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.automation.isolation import (
    DockerConfig,
    DockerExecutor,
    _plain_directory,
    prepare_build_context,
    verify_canary_boundary,
)
from services.automation.pm import protected_path
from services.automation.worker import (
    WorkerConfig,
    exclusive_lock,
    github_identity,
    validate_container_auth,
    write_json,
)


def setup(config_path):
    config = WorkerConfig.load(config_path)
    github_identity(config)
    for directory in (config.state_dir, config.execution_root, config.agent_home):
        directory.mkdir(parents=True, exist_ok=True)
    run = config.execution_root / ("setup-" + uuid.uuid4().hex)
    source, stage = run / "source", run / "artifacts"
    source.mkdir(parents=True)
    stage.mkdir()
    private = config.state_dir / run.name
    private.mkdir()
    executor = DockerExecutor(DockerConfig(image=config.executor_image, workspace_root=config.execution_root,
        auth_root=config.agent_home, engine=config.engine, model_network=config.executor_network))
    executor.preflight()
    return config, executor, source, stage, private


def verify(config_path, output):
    output = protected_path(output)
    if output.exists():
        raise ValueError("readiness proof output must be a fresh external private file")
    output.parent.mkdir(parents=True, exist_ok=True)
    _plain_directory(output.parent, "private proof output parent")
    config, executor, source, stage, private = setup(config_path)
    for restricted in (config.repository, config.execution_root, config.agent_home):
        if output.is_relative_to(restricted):
            raise ValueError("readiness proof cannot be stored in source, execution or AI profile mounts")
    with exclusive_lock(config.agent_home / "lgax-worker.lock"):
        canary = private / "publisher-canary.txt"
        canary.write_text("harmless publisher canary " + uuid.uuid4().hex, encoding="utf-8")
        boundary = verify_canary_boundary(executor, cwd=source, artifacts=stage,
                                          protected_canary=canary, output_dir=private)
        authentication = validate_container_auth(config, executor, source, stage, private, lambda: True)
        proof = {"collector": "trusted_pm", "account": config.account, "verified_at": time.time(),
                 "execution_isolation_verified": True, "publisher_separation_verified": True,
                 "login_verified": True, "authentication": authentication, "boundary": boundary,
                 "image_id": config.executor_image, "github_publication_verified": False,
                 "automation_enabled": False}
        write_json(output, proof)
        print(json.dumps({"account": config.account, "boundary_verified": True, "login_verified": True,
                          "automation_enabled": False, "proof_path": str(output)}, ensure_ascii=False))


def login(config_path):
    config, executor, source, stage, private = setup(config_path)
    if config.engine != "codex":
        raise ValueError("Claude requires its owner's login in the selected container; use the Claude setup guide")
    output = private / "device-login.log"
    finished = threading.Event()
    def show_code():
        displayed = False
        while not finished.wait(0.5):
            if output.exists() and not displayed:
                text = re.sub(r"\x1b\[[0-9;]*m", "", output.read_text(encoding="utf-8", errors="replace"))
                match = re.search(r"\b[A-Z0-9]{4}-[A-Z0-9]{5}\b", text)
                if match and "https://auth.openai.com/codex/device" in text:
                    print("https://auth.openai.com/codex/device · " + match.group(), flush=True)
                    displayed = True
    with exclusive_lock(config.agent_home / "lgax-worker.lock"):
        thread = threading.Thread(target=show_code, daemon=True)
        thread.start()
        try:
            response = executor.run(["codex", "login", "--device-auth"], cwd=source, artifacts=stage, env={},
                output=output, timeout_seconds=600, heartbeat=lambda: True, role="model", readonly_workspace=True)
            if response.returncode or response.stopped_reason:
                raise ValueError("device login incomplete; no readiness or API fallback recorded")
            print(json.dumps({"account": config.account, "login_completed": True,
                              "next_action": "run verify; automation remains OFF"}))
        finally:
            finished.set()
            thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-context")
    build.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--config", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    auth = commands.add_parser("login")
    auth.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build-context":
        print(json.dumps(prepare_build_context(ROOT, args.output)))
    elif args.command == "verify":
        verify(args.config, args.output)
    else:
        login(args.config)


if __name__ == "__main__":
    main()
