"""Claude Code subscription driver for the fixed worker, with no API fallback.

Only native CLI metadata is probed before claiming work. No secret token is
read/copied by this module. File tools are confined by --restricted; repository
tests and publishing remain the trusted worker's bounded responsibilities.
This does not replace the deployment's separate execution user/VM and broker.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

REQUIRED_FLAGS = ("--restricted", "--safe-mode", "--json-schema", "--tools", "--allowedTools",
                  "--disallowedTools", "--strict-mcp-config", "--mcp-config", "--settings",
                  "--permission-mode", "--no-session-persistence",
                  "--output-format", "--verbose", "--no-chrome")
SETTINGS = {"forceLoginMethod": "claudeai", "disableAllHooks": True}


def validate_options(config):
    if (not re.fullmatch(r"2\.\d+\.\d+", config.claude_version) or
            tuple(map(int, config.claude_version.split("."))) < (2, 1, 268)):
        raise ValueError("Claude requires a pinned supported version (at least 2.1.268)")
    if config.claude_model not in {"sonnet", "opus", "haiku"}:
        raise ValueError("Claude model must be an explicit official model alias")
    if type(config.claude_max_turns) is not int or not 1 <= config.claude_max_turns <= 100:
        raise ValueError("Claude turn limit must be between 1 and 100")


def executable(config):
    value = shutil.which(config.claude_executable)
    if not value:
        raise ValueError("installed native Claude Code executable is unavailable")
    if os.name == "nt" and not value.lower().endswith(".exe"):
        raise ValueError("configure native claude.exe; shell wrappers are not used")
    return value


def _probe(argv, environment, cwd):
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30, check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        # Auth output may contain account email or credentials. Never print it.
        raise ValueError("Claude metadata/authentication check failed; log in directly in its dedicated profile")
    if len(result.stdout.encode("utf-8")) > 128 * 1024:
        raise ValueError("Claude metadata response exceeded bounds")
    return result.stdout


def validate_auth(config, environment, cwd):
    validate_options(config)
    exe = executable(config)
    version_text = _probe([exe, "--version"], environment, cwd)
    match = re.fullmatch(r"(\d+\.\d+\.\d+) \(Claude Code\)\s*", version_text)
    if not match or match[1] != config.claude_version:
        raise ValueError("Claude version differs from the pinned worker version; PM must revalidate an upgrade")
    help_text = _probe([exe, "--help"], environment, cwd)
    if any(flag not in help_text for flag in REQUIRED_FLAGS):
        raise ValueError("Claude CLI lacks required restricted/authenticated non-interactive capabilities")
    status = json.loads(_probe([exe, "--safe-mode", "--restricted", "--settings",
                              json.dumps(SETTINGS), "auth", "status"], environment, cwd))
    if (not isinstance(status, dict) or status.get("loggedIn") is not True or
            status.get("authMethod") != "claude.ai" or
            status.get("apiProvider") != "firstParty" or
            not isinstance(status.get("configDirectory"), str) or
            Path(status["configDirectory"]).resolve() != config.agent_home.resolve()):
        raise ValueError("Claude worker requires its own claude.ai login; API/provider/token fallback is forbidden")
    # Deliberately exclude email, organization, raw tokens and account metadata.
    return {"engine": "claude", "version": match[1], "auth_method": "claude.ai",
            "configuration_directory_verified": True, "model_executed": False}


def argv(config, job, run_dir, schema, *, executable_name=None):
    validate_options(config)
    mcp = run_dir / "empty-mcp.json"
    mcp.write_text('{"mcpServers": {}}\n', encoding="utf-8")
    tools = "Read,Glob,Grep" + (",Edit,Write" if job["kind"] == "implementation" else "")
    return [executable_name or executable(config), "--print", "--output-format", "stream-json", "--verbose",
            "--json-schema", json.dumps(schema, separators=(",", ":")),
            "--restricted", "--safe-mode", "--no-chrome", "--no-session-persistence",
            "--strict-mcp-config", "--mcp-config", str(mcp), "--settings", json.dumps(SETTINGS),
            "--tools", tools, "--allowedTools", tools, "--disallowedTools", "mcp__*",
            "--permission-mode", "default", "--permission-prompts", "none",
            "--model", config.claude_model, "--max-turns", str(config.claude_max_turns)]


def extract_result(log: Path, destination: Path):
    """Require exactly one successful final stream event; never mine assistant prose.

    Combined stderr/stdout can include ordinary diagnostic lines. Other JSON
    events are ignored; a duplicate result or subsequent JSON event is refused.
    The worker then applies its existing strict result/secret/field-size checks.
    """
    if not log.is_file() or log.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("missing or oversized Claude event log")
    final = None
    actual_model = None
    with log.open(encoding="utf-8") as stream:
        for line in stream:
            if len(line.encode("utf-8")) > 2 * 1024 * 1024:
                raise ValueError("Claude event exceeded bounds")
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # Plain native CLI diagnostic, not a successful result.
            if not isinstance(event, dict):
                continue
            if final is not None:
                raise ValueError("Claude stream contains events after its final result")
            if (event.get("type") == "system" and event.get("subtype") == "init" and
                    isinstance(event.get("model"), str) and
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", event["model"])):
                actual_model = event["model"]
            if event.get("type") == "result":
                final = event
    if (not final or final.get("subtype") != "success" or final.get("is_error") is not False or
            not isinstance(final.get("structured_output"), dict)):
        raise ValueError("Claude did not produce a successful structured result")
    # Fail closed when file/tool permissions made the approved operation partial.
    if final.get("permission_denials"):
        raise ValueError("Claude encountered denied tools; PM must inspect the retained run")
    payload = json.dumps(final["structured_output"], ensure_ascii=False, indent=2) + "\n"
    if len(payload.encode("utf-8")) > 128 * 1024:
        raise ValueError("Claude structured result exceeded bounds")
    destination.write_text(payload, encoding="utf-8")
    metadata = {"engine": "claude", "billing_basis": "claude.ai account usage; not an invoice"}
    if actual_model:
        metadata["observed_model"] = actual_model
    for key in ("num_turns", "duration_ms", "total_cost_usd"):
        value = final.get(key)
        if type(value) in {int, float} and math.isfinite(value) and value >= 0:
            metadata["estimated_cost_usd" if key == "total_cost_usd" else key] = value
    usage = final.get("usage", {})
    if isinstance(usage, dict):
        metadata["usage"] = {key: value for key, value in usage.items()
                             if key in {"input_tokens", "output_tokens", "cache_creation_input_tokens",
                                        "cache_read_input_tokens"} and type(value) is int and value >= 0}
    return metadata
