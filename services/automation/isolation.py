"""Credential-separated Docker execution for the fixed host supervisor.

The host owns controller/GitHub credentials and NEVER executes repository code.
Containers receive only an exported workspace, bounded schema/result artifacts,
and (model role only) the owner's AI profile. The validator has no AI profile and
no network. This is a not-mounted filesystem boundary, not an ACL claim.
No unavailable Docker/native execution fallback is permitted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

if __package__:
    from .process import ProcessResult
else:
    from process import ProcessResult

IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
CONTAINER_ID = re.compile(r"[0-9a-f]{64}")
NETWORK_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}")
ARTIFACT_NAMES = {"result-schema.json", "result.json", "empty-mcp.json", "empty-settings.json",
                  "revision-reference.patch"} | {
                      f"product-{kind}-{sequence:02d}.{suffix}"
                      for kind in ("request", "response")
                      for sequence in range(1, 41) for suffix in ("json", "ready")}
COMMANDS = {"python", "python3", "uv", "npm", "node", "git", "codex", "claude"}
SAFE_ENV = {
    "LGAX_MODEL_ADAPTER", "LGAX_MODEL_ENDPOINT", "LGAX_MODEL_ID", "LGAX_MODEL_DIGEST",
    "LGAX_MODEL_MAX_OUTPUT_TOKENS", "LGAX_MODEL_CONTEXT_TOKENS", "LGAX_MODEL_TIMEOUT_SECONDS",
    "LGAX_MODEL_MAX_RESPONSE_BYTES", "LGAX_MODEL_THINK", "LGAX_MODEL_GATEWAY_URL", "LGAX_OLLAMA_URL",
}
OWNED_LABEL = "org.lgax.owned-executor"
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_LOG_BYTES = 64 * 1024 * 1024


def _plain_directory(value: Path, label: str) -> Path:
    """Reject links/reparse ancestors before resolving a deployment path."""
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} requires an explicit absolute directory")
    if "," in str(path) or "\x00" in str(path):
        raise ValueError(f"{label} cannot contain Docker mount separators")
    for candidate in (path, *path.parents):
        if not candidate.exists():
            raise ValueError(f"{label} directory/ancestor is missing")
        observed = candidate.lstat()
        if (stat.S_ISLNK(observed.st_mode) or
                getattr(observed, "st_file_attributes", 0) & 0x400):
            raise ValueError(f"{label} links/reparse directories are forbidden")
    if not path.is_dir():
        raise ValueError(f"{label} must be a directory")
    return path.resolve()


def regular_file(path: Path, *, maximum: int = MAX_ARTIFACT_BYTES) -> bytes:
    """Read a bounded no-link file with a stable identity; never follow guest links."""
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
            getattr(before, "st_file_attributes", 0) & 0x400 or before.st_size > maximum):
        raise ValueError("isolated output must be a bounded regular non-linked file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_ino, opened.st_dev, opened.st_size) != (before.st_ino, before.st_dev, before.st_size):
            raise ValueError("isolated file changed while opening")
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if len(data) > maximum or (opened.st_ino, opened.st_dev, opened.st_mtime_ns, opened.st_size) != (
            after.st_ino, after.st_dev, after.st_mtime_ns, after.st_size):
        raise ValueError("isolated file changed or exceeded bounds")
    return data


def _authentication_entries(root: Path, *, stopped_runtime=False):
    entries = 0
    for current, directories, files in os.walk(root, followlinks=False):
        if stopped_runtime and Path(current) == root:
            directories[:] = [name for name in directories if name != "tmp"]
        for name in directories:
            _plain_directory(Path(current) / name, "AI profile child")
        for name in files:
            observed = (Path(current) / name).lstat()
            if (not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1 or
                    getattr(observed, "st_file_attributes", 0) & 0x400):
                raise ValueError("dedicated AI profile cannot contain links/reparse files or sockets")
        entries += len(directories) + len(files)
        if entries > 10000:
            raise ValueError("dedicated AI profile exceeds bounded entry count")
    return root


def _authentication_directory(value: Path) -> Path:
    """A dedicated profile cannot contain junctions/sockets to host services."""
    return _authentication_entries(_plain_directory(value, "AI profile"))


def _canonical_host_source(value: str) -> str:
    path = value.replace("\\", "/").rstrip("/")
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if path.lower().startswith(prefix):
            remainder = path[len(prefix):]
            if re.match(r"^[A-Za-z]/", remainder):
                return (remainder[0] + ":/" + remainder[2:]).lower()
    return path.lower() if re.match(r"^[A-Za-z]:/", path) else path


def cleanup_auth_runtime(auth_root: Path, cache_root: Path, *, docker_executable: str = "docker",
                         docker_call: Callable | None = None) -> dict:
    """Quarantine only stopped Codex's generated tmp/arg0 launch shims.

    Codex 0.155 creates Linux launcher symlinks under its private tmp directory.
    Never relax the profile's general no-link rule. After no running container
    can access the profile, atomically move that exact recognized runtime tree
    to an unmounted host-only cache. Credentials stay in place and are not read,
    copied or moved. Unknown directories/link locations fail closed for review.
    The caller must serialize profile use (the Worker holds its profile lock).
    """
    auth = _plain_directory(auth_root, "AI profile")
    temporary = auth / "tmp"
    if not temporary.exists() and not temporary.is_symlink():
        return {"cleanup": "not_needed", "credentials_moved": False}
    temporary = _plain_directory(temporary, "exact Codex runtime tmp")
    if temporary.parent != auth:
        raise ValueError("runtime cache must be the exact own AI profile/tmp")
    original = temporary.lstat()
    known_links = {"apply_patch", "applypatch", "codex-execve-wrapper", "codex-linux-sandbox"}
    count = 0
    for current, directories, names in os.walk(temporary, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(temporary)
        if relative.parts and (relative.parts[0] != "arg0" or len(relative.parts) > 2 or
                (len(relative.parts) == 2 and not re.fullmatch(r"codex-arg0[A-Za-z0-9_-]{1,64}", relative.parts[1]))):
            raise ValueError("unrecognized Codex runtime cache layout; no automatic movement")
        for name in directories:
            _plain_directory(current_path / name, "Codex runtime cache child")
        for name in names:
            observed = (current_path / name).lstat()
            linked = stat.S_ISLNK(observed.st_mode) or getattr(observed, "st_file_attributes", 0) & 0x400
            if (len(relative.parts) != 2 or relative.parts[0] != "arg0" or
                    (linked and name not in known_links) or
                    (not linked and (name not in known_links | {".lock"} or
                                     not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1))):
                raise ValueError("unrecognized Codex runtime cache file/link; no automatic movement")
        count += len(directories) + len(names)
        if count > 1024:
            raise ValueError("Codex runtime cache exceeds bounded entry count")
    # Check every other profile entry BEFORE quarantine, so an unknown link
    # cannot cause even recognized cache movement. This metadata-only exception
    # never validates a mounted model profile; final full validation is strict.
    _authentication_entries(auth, stopped_runtime=True)

    if docker_call is None:
        executable = shutil.which(docker_executable)
        if not executable or (os.name == "nt" and not executable.lower().endswith(".exe")):
            raise ValueError("native Docker is required to prove profile containers stopped")
        environment = {key: value for key, value in os.environ.items() if key in {
            "PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "LOCALAPPDATA",
            "APPDATA", "TEMP", "TMP"}}

        def invoke(arguments):
            try:
                result = subprocess.run([executable, *arguments], env=environment, capture_output=True,
                    check=False, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except (OSError, subprocess.TimeoutExpired):
                raise RuntimeError("cannot prove containers stopped; runtime cache retained") from None
            if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
                raise RuntimeError("cannot prove containers stopped; runtime cache retained")
            return result.stdout.decode("utf-8")

        docker_call = invoke

    identifiers = docker_call(["ps", "--quiet"]).split()
    if len(identifiers) > 1024 or any(not re.fullmatch(r"[0-9a-f]{12,64}", value) for value in identifiers):
        raise ValueError("active Docker container inventory invalid")
    if identifiers:
        active = json.loads(docker_call(["inspect", *identifiers]))
        if not isinstance(active, list) or len(active) != len(identifiers):
            raise ValueError("active container proof incomplete")
        profile = _canonical_host_source(str(auth))
        for container in active:
            for mount in container.get("Mounts", []):
                source = _canonical_host_source(str(mount.get("Source", "")))
                if source and (profile == source or profile.startswith(source + "/") or
                               source.startswith(profile + "/")):
                    raise ValueError("AI profile is still accessible to a running container; cache retained")

    cache = Path(cache_root)
    if not cache.is_absolute():
        raise ValueError("private unmounted cache requires an absolute directory")
    cache.mkdir(parents=True, exist_ok=True)
    cache = _plain_directory(cache, "private CLI runtime cache")
    if cache.is_relative_to(auth) or auth.is_relative_to(cache) or cache == Path(cache.anchor):
        raise ValueError("CLI runtime cache must be separate from the mounted AI profile")
    if os.name != "nt":
        cache.chmod(0o700)
    confirmed = temporary.lstat()
    if (confirmed.st_ino, confirmed.st_dev) != (original.st_ino, original.st_dev):
        raise ValueError("runtime directory changed during stopped-container check")
    destination = cache / ("codex-tmp-" + uuid.uuid4().hex)
    # rename is same-filesystem atomic and never follows/copies the generated
    # Linux symlink targets. Cross-filesystem moves fail rather than copying.
    temporary.rename(destination)
    _authentication_directory(auth)
    return {"cleanup": "quarantined", "runtime_entries": count,
            "containers_stopped": True, "credentials_moved": False, "credentials_read": False,
            "cache_directory": str(destination)}


@dataclass(frozen=True)
class DockerConfig:
    image: str
    workspace_root: Path
    auth_root: Path | None = None
    engine: str = "codex"
    docker_executable: str = "docker"
    model_network: str = "bridge"
    memory_mb: int = 4096
    cpus: int = 2
    pids: int = 256

    def validate(self):
        if not IMAGE_ID.fullmatch(self.image):
            raise ValueError("executor image must be an immutable exact sha256 image ID")
        if self.engine not in {"codex", "claude"}:
            raise ValueError("isolated engine must be codex or claude")
        if (not NETWORK_NAME.fullmatch(self.model_network) or
                self.model_network.lower() in {"host", "container", "default"}):
            raise ValueError("host/shared-container networking is forbidden")
        if (type(self.memory_mb) is not int or not 256 <= self.memory_mb <= 16384 or
                type(self.cpus) is not int or not 1 <= self.cpus <= 8 or
                type(self.pids) is not int or not 16 <= self.pids <= 512):
            raise ValueError("executor resource bounds are required")
        root = _plain_directory(self.workspace_root, "workspace root")
        if root == Path(root.anchor):
            raise ValueError("an entire drive/root cannot be an execution workspace")
        if self.auth_root is not None:
            auth = _authentication_directory(self.auth_root)
            if auth.is_relative_to(root) or root.is_relative_to(auth) or auth == Path(auth.anchor):
                raise ValueError("AI authentication and execution workspace must be disjoint")
            if auth in {Path.home().resolve(), (Path.home() / ".codex").resolve(),
                        (Path.home() / ".claude").resolve()}:
                raise ValueError("personal desktop AI/home profiles cannot be mounted; use a dedicated worker login")
        return self


class IsolationProfileBusy(RuntimeError):
    """The owner's real profile mutex was busy before any authentication read."""


def create_docker_executor(config: DockerConfig, *, docker_call: Callable | None = None):
    """Construct a PM executor only while holding the Worker's exact OS lock.

    A busy owner is a free startup wait. Recognized runtime quarantine still
    requires an actual no-active-mount Docker proof. No authentication file is
    read, copied or moved, and no unknown link is accepted by the constructor.
    """
    if config.auth_root is None:
        return DockerExecutor(config)
    replace(config, auth_root=None).validate()
    auth = _plain_directory(config.auth_root, "AI profile")
    root = _plain_directory(config.workspace_root, "workspace root")
    if (auth.is_relative_to(root) or root.is_relative_to(auth) or auth == Path(auth.anchor) or
            auth in {Path.home().resolve(), (Path.home() / ".codex").resolve(), (Path.home() / ".claude").resolve()}):
        raise ValueError("a disjoint dedicated AI profile is required before startup")
    lock_path = auth / "lgax-worker.lock"
    if lock_path.exists() or lock_path.is_symlink():
        metadata = lock_path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or
                getattr(metadata, "st_file_attributes", 0) & 0x400):
            raise ValueError("own AI profile lock must be an ordinary single-link file")
    if __package__:
        from .worker import exclusive_lock
    else:
        from worker import exclusive_lock
    reservation = exclusive_lock(lock_path)
    try:
        reservation.__enter__()
    except OSError:
        raise IsolationProfileBusy("own AI profile is busy before startup validation") from None
    try:
        cleanup_auth_runtime(auth, auth.parent / ".lgax-cli-runtime-cache",
                             docker_executable=config.docker_executable, docker_call=docker_call)
        return DockerExecutor(config)
    finally:
        reservation.__exit__(None, None, None)


def redact_output(value: bytes) -> bytes:
    """Defense in depth for private logs; arbitrary model disclosure is not trusted."""
    text = value.decode("utf-8", errors="replace")
    text = re.sub(r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                  r"github_pat_[A-Za-z0-9_]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,}|"
                  r"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,})",
                  "[REDACTED_CREDENTIAL]", text, flags=re.IGNORECASE)
    text = re.sub(r'("(?:access_token|refresh_token|id_token|api_key|oauthToken|token)"\s*:\s*")[^"]+(\")',
                  r'\1[REDACTED_CREDENTIAL]\2', text, flags=re.IGNORECASE)
    return text.encode("utf-8")


class DockerExecutor:
    """Bound only our containers; Docker daemon errors always fail closed."""

    def __init__(self, config: DockerConfig):
        self.config = config.validate()
        self.executable = shutil.which(config.docker_executable)
        if not self.executable:
            raise ValueError("Docker is unavailable; native execution fallback is forbidden")
        if os.name == "nt" and not self.executable.lower().endswith(".exe"):
            raise ValueError("native Docker executable is required")
        # Only explicitly selected Docker client environment passes through.
        # Arbitrary inherited DOCKER_HOST/context endpoints are refused.
        self.docker_env = {key: value for key, value in os.environ.items()
                           if key in {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "HOME",
                                      "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP"}}
        self.last_boundary: dict = {}

    def _docker(self, arguments, *, timeout=30):
        try:
            response = subprocess.run([self.executable, *arguments], env=self.docker_env,
                capture_output=True, timeout=timeout, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("Docker unavailable/timed out; no native fallback") from None
        if response.returncode:
            # Daemon messages can contain account-specific paths. Do not echo.
            raise RuntimeError("Docker operation failed; inspect its local daemon")
        if len(response.stdout) > 2 * 1024 * 1024:
            raise ValueError("Docker metadata exceeded bounds")
        return response.stdout.decode("utf-8", errors="strict")

    def preflight(self):
        info = json.loads(self._docker(["info", "--format", "{{json .}}"], timeout=15))
        image = json.loads(self._docker(["image", "inspect", self.config.image]))
        if info.get("OSType") != "linux" or not isinstance(image, list) or len(image) != 1:
            raise ValueError("a Linux Docker engine and exact reviewed executor image are required")
        metadata = image[0]
        if (metadata.get("Id") != self.config.image or
                metadata.get("Config", {}).get("User") != "1000:1000"):
            raise ValueError("executor image ID/user differs from the reviewed image")
        return {"backend": "docker", "image_id": self.config.image, "linux_engine": True,
                "native_fallback": False, "model_network": self.config.model_network,
                "validator_network": "none", "model_executed": False}

    def _paths(self, cwd: Path, artifacts: Path):
        root = _plain_directory(self.config.workspace_root, "workspace root")
        work = _plain_directory(cwd, "exported job workspace")
        files = _plain_directory(artifacts, "isolated artifacts")
        if (not work.is_relative_to(root) or not files.is_relative_to(root) or
                work == root or files == root or work.is_relative_to(files) or files.is_relative_to(work)):
            raise ValueError("job work and artifact directories must be disjoint children of the execution root")
        if (work / ".git").exists() or (work / ".git").is_symlink():
            raise ValueError("the exported container workspace must not contain host Git metadata")
        # Only schema/result files are mounted, never controller checkpoints.
        for entry in files.iterdir():
            if entry.name not in ARTIFACT_NAMES:
                raise ValueError("unexpected artifact; controller/private runtime directories cannot be mounted")
            regular_file(entry)
        return work, files

    def _environment(self, supplied: Mapping[str, str], role: str):
        environment = {
            "HOME": "/home/executor", "PATH": "/opt/lgax-venv/bin:/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "", "SSH_ASKPASS": "", "GH_CONFIG_DIR": "/home/executor/empty-gh",
            # Even --no-sync uv touches cache metadata such as sdists-v9/.git.
            # Keep installed dependencies fixed/read-only, but cache writes in
            # this container's empty private tmpfs, never the image seed cache.
            "UV_CACHE_DIR": "/home/executor/uv-cache", "UV_PROJECT_ENVIRONMENT": "/opt/lgax-venv",
            "UV_OFFLINE": "1", "npm_config_cache": "/home/executor/npm-cache",
            "npm_config_offline": "true", "npm_config_audit": "false", "npm_config_fund": "false",
            "PYTHONPATH": ":".join("/workspace/" + path for path in (
                "packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src")),
        }
        # Unknown inherited variables are dropped, including all API/login/PM
        # secrets and host profile/cache paths. The AI profile enters by mount.
        for key in SAFE_ENV:
            value = supplied.get(key)
            if value is not None:
                if (not isinstance(value, str) or len(value) > 1024 or "\x00" in value or
                        re.search(r"Bearer\s|(?:sk-|ghp_|github_pat_)", value, re.IGNORECASE)):
                    raise ValueError("unsafe credential-like executor environment value")
                if key.endswith(("_URL", "_ENDPOINT")):
                    from urllib.parse import urlsplit
                    parsed = urlsplit(value)
                    if parsed.username or parsed.password or parsed.query or parsed.fragment:
                        raise ValueError("credential-bearing service URL is forbidden")
                environment[key] = value
        if role == "model":
            environment.update({"CODEX_HOME": "/agent-auth"} if self.config.engine == "codex" else
                               {"CLAUDE_CONFIG_DIR": "/agent-auth", "CLAUDE_CODE_SAFE_MODE": "1",
                                "DISABLE_AUTOUPDATER": "1"})
        return environment

    def _translate(self, argv: list[str], cwd: Path, artifacts: Path):
        if not argv or not isinstance(argv, list) or any(not isinstance(row, str) or "\x00" in row for row in argv):
            raise ValueError("explicit bounded execution argv required")
        executable = Path(argv[0]).name.lower().removesuffix(".exe")
        if executable not in COMMANDS:
            raise ValueError("command is not installed in the fixed reviewed executor image")
        translated = [executable]
        for value in argv[1:]:
            # Arguments containing a path suffix (such as --option=/host/file)
            # are never automatically interpreted as mounts.
            if value == str(cwd):
                value = "/workspace"
            elif value == str(artifacts):
                value = "/artifacts"
            elif Path(value).is_absolute():
                path = Path(value)
                if path.is_relative_to(artifacts):
                    relative = path.relative_to(artifacts)
                    if len(relative.parts) != 1 or relative.name not in ARTIFACT_NAMES:
                        raise ValueError("arbitrary host file arguments are forbidden")
                    value = "/artifacts/" + relative.as_posix()
                elif path.is_relative_to(cwd):
                    value = "/workspace/" + path.relative_to(cwd).as_posix()
                else:
                    raise ValueError("unmounted absolute host command argument is forbidden")
            translated.append(value)
        return translated

    def _create_arguments(self, name: str, token: str, argv: list[str], *, cwd: Path,
                          artifacts: Path, env: Mapping[str, str], role: str,
                          timeout_seconds: float, readonly_workspace: bool):
        if role not in {"model", "validator"}:
            raise ValueError("execution role must be model or validator")
        if role == "model" and self.config.auth_root is None:
            raise ValueError("model execution requires its owner's separate authentication profile")
        work, files = self._paths(cwd, artifacts)
        options = ["create", "--name", name, "--label", f"{OWNED_LABEL}={token}",
                   "--interactive", "--init", "--read-only", "--user", "1000:1000",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
                   "--pids-limit", str(self.config.pids), "--memory", f"{self.config.memory_mb}m",
                   "--cpus", str(self.config.cpus), "--ulimit", "nofile=1024:1024", "--stop-timeout", "1",
                   "--network", "none" if role == "validator" else self.config.model_network,
                   "--workdir", "/workspace", "--entrypoint", "/usr/bin/timeout",
                   "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=1777",
                   "--tmpfs", "/home/executor:rw,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=0700",
                   "--mount", f"type=bind,source={work},destination=/workspace" +
                   (",readonly" if readonly_workspace else ""),
                   "--mount", f"type=bind,source={files},destination=/artifacts"]
        if role == "model":
            auth = _authentication_directory(self.config.auth_root)
            options.extend(["--mount", f"type=bind,source={auth},destination=/agent-auth"])
        for key, value in sorted(self._environment(env, role).items()):
            options.extend(["--env", f"{key}={value}"])
        # Daemon-side timeout survives a killed supervisor. No guest process may
        # keep running indefinitely after the host CLI/heartbeat disappears.
        return [*options, self.config.image, "--signal=TERM", "--kill-after=5s",
                f"{min(timeout_seconds, 7200):.3f}s", "/usr/local/bin/lgax-exec",
                *self._translate(argv, work, files)]

    def _inspect_boundary(self, container_id: str, token: str, *, role: str,
                          cwd: Path, artifacts: Path, readonly_workspace: bool):
        entries = json.loads(self._docker(["inspect", container_id]))
        if not isinstance(entries, list) or len(entries) != 1:
            raise ValueError("owned container metadata invalid")
        row = entries[0]
        host = row.get("HostConfig", {})
        expected = {"/workspace": (cwd, not readonly_workspace), "/artifacts": (artifacts, True)}
        if role == "model":
            expected["/agent-auth"] = (self.config.auth_root, True)
        mounts = row.get("Mounts", [])
        if (row.get("Id") != container_id or row.get("Image") != self.config.image or
                row.get("Config", {}).get("User") != "1000:1000" or
                row.get("Config", {}).get("Labels", {}).get(OWNED_LABEL) != token or
                host.get("Privileged") is not False or host.get("ReadonlyRootfs") is not True or
                host.get("NetworkMode") != ("none" if role == "validator" else self.config.model_network) or
                host.get("PidMode") not in {"", None} or host.get("IpcMode") not in {"private", ""} or
                "ALL" not in [str(value).upper() for value in host.get("CapDrop", [])] or
                not any(str(value).split(":", 1)[0].split("=", 1)[0] == "no-new-privileges" for value in
                        host.get("SecurityOpt", [])) or len(mounts) != len(expected)):
            raise ValueError("Docker container failed the fixed privilege/isolation boundary")
        for mount in mounts:
            destination = mount.get("Destination")
            if destination not in expected or mount.get("Type") != "bind":
                raise ValueError("unexpected host mount/socket/volume in execution container")
            source, writable = expected.pop(destination)
            # Docker Desktop uses /run/desktop/mnt/host/c/... for Windows bind
            # sources. Compare canonical drive suffix without loosening the
            # reviewed destination or accepting other filesystem roots.
            given = str(mount.get("Source", "")).replace("\\", "/")
            wanted = str(source.resolve()).replace("\\", "/")
            if re.match(r"^[A-Za-z]:/", wanted):
                drive_path = wanted[0].lower() + wanted[2:]
                candidates = {wanted.lower(), "/run/desktop/mnt/host/" + drive_path.lower(),
                              "/host_mnt/" + drive_path.lower()}
                valid_source = given.lower() in candidates
            else:
                valid_source = given == wanted
            if not valid_source or mount.get("RW") is not writable:
                raise ValueError("mount source/access differs from the approved deployment")
        if expected:
            raise ValueError("reviewed container mounts missing")
        self.last_boundary = {"backend": "docker", "image_id": self.config.image,
            "role": role, "uid": 1000, "readonly_root": True, "caps_dropped": True,
            "no_new_privileges": True, "network": host.get("NetworkMode"),
            "mount_targets": sorted(mount.get("Destination") for mount in mounts),
            "publisher_credentials_mounted": False, "ai_profile_mounted": role == "model"}

    def _remove_owned(self, container_id: str, token: str):
        # Never enumerate/kill unrelated user's containers. Ownership is proved
        # by our random deployment label, not a caller-supplied container name.
        rows = json.loads(self._docker(["inspect", container_id]))
        if (len(rows) != 1 or rows[0].get("Id") != container_id or
                rows[0].get("Config", {}).get("Labels", {}).get(OWNED_LABEL) != token):
            raise ValueError("refuse to terminate a container not owned by this execution")
        self._docker(["rm", "--force", container_id], timeout=15)

    def run(self, argv: list[str], *, cwd: Path, env: Mapping[str, str], output: Path,
            artifacts: Path, timeout_seconds: float, heartbeat: Callable[[], bool],
            role: str = "validator", input_text: str | None = None,
            readonly_workspace: bool = False, heartbeat_interval: float = 15,
            poll_interval: float = 0.1, max_output_bytes: int = MAX_LOG_BYTES) -> ProcessResult:
        if (not 0 < timeout_seconds <= 7200 or not 0 < heartbeat_interval <= 60 or
                not 0 < poll_interval <= 5 or not 1024 <= max_output_bytes <= MAX_LOG_BYTES):
            raise ValueError("bounded isolated execution limits required")
        if input_text is not None and len(input_text.encode("utf-8")) > 1024 * 1024:
            raise ValueError("isolated prompt exceeds bounds")
        if not heartbeat():
            return ProcessResult(1, 0, "controller stopped execution before start")
        self.preflight()
        output = Path(output)
        if output.resolve().is_relative_to(cwd.resolve()) or output.resolve().is_relative_to(artifacts.resolve()):
            raise ValueError("private supervisor logs must remain outside guest writable mounts")
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and (output.is_symlink() or output.stat().st_nlink != 1):
            raise ValueError("private log path is linked")
        token = uuid.uuid4().hex
        name = "lgax-executor-" + token
        started = time.monotonic()
        container_id = self._docker(self._create_arguments(name, token, argv,
            cwd=cwd, artifacts=artifacts, env=env, role=role, timeout_seconds=timeout_seconds,
            readonly_workspace=readonly_workspace)).strip()
        if not CONTAINER_ID.fullmatch(container_id):
            raise ValueError("Docker returned an invalid container ID")
        process = None
        pump = None
        input_pump = None
        failure = threading.Event()
        reason = None
        try:
            self._inspect_boundary(container_id, token, role=role, cwd=cwd.resolve(),
                                   artifacts=artifacts.resolve(), readonly_workspace=readonly_workspace)
            with output.open("wb") as log:
                if os.name != "nt":
                    output.chmod(0o600)
                process = subprocess.Popen([self.executable, "start", "--attach", "--interactive", container_id],
                    env=self.docker_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

                def copy_output():
                    buffered = bytearray()
                    try:
                        # read(4096) can block until a full buffer/EOF, hiding a
                        # live device login URL/code while authentication waits.
                        read_available = getattr(process.stdout, "read1", process.stdout.read)
                        while chunk := read_available(4096):
                            buffered.extend(chunk)
                            while b"\n" in buffered:
                                line, _, rest = buffered.partition(b"\n")
                                buffered = bytearray(rest)
                                log.write(redact_output(line + b"\n"))
                                log.flush()
                            if len(buffered) > 512 * 1024:
                                buffered.clear()
                                log.write(b"[oversized container output suppressed]\n")
                                failure.set()
                                break
                            if log.tell() > max_output_bytes:
                                failure.set()
                                break
                            log.flush()
                        if buffered and not failure.is_set():
                            log.write(redact_output(bytes(buffered)))
                        log.flush()
                    except (OSError, ValueError):
                        failure.set()

                pump = threading.Thread(target=copy_output, daemon=True)
                pump.start()
                def copy_input():
                    try:
                        if input_text is not None:
                            process.stdin.write(input_text.encode("utf-8"))
                        process.stdin.close()
                    except (BrokenPipeError, OSError):
                        pass

                # A guest command that never reads stdin must not block the
                # supervisor's timeout/OFF monitor on a full prompt pipe.
                input_pump = threading.Thread(target=copy_input, daemon=True)
                input_pump.start()
                next_heartbeat = started + heartbeat_interval
                while process.poll() is None:
                    current = time.monotonic()
                    if current - started >= timeout_seconds:
                        reason = "bounded isolated execution timeout"
                        break
                    if failure.is_set():
                        reason = "bounded isolated output failed/exceeded storage"
                        break
                    if current >= next_heartbeat:
                        try:
                            keep_running = heartbeat()
                        except Exception:  # noqa: BLE001 - every controller failure stops only our container.
                            keep_running = False
                        if not keep_running:
                            reason = "controller OFF/STOP, revoked lease, or connection unavailable"
                            break
                        next_heartbeat = current + heartbeat_interval
                    time.sleep(poll_interval)
                if reason:
                    self._remove_owned(container_id, token)
                    container_id = None
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    reason = reason or "Docker attachment failed to terminate"
                pump.join(timeout=5)
                input_pump.join(timeout=2)
                if pump.is_alive():
                    reason = reason or "isolated output stream did not terminate"
                if failure.is_set():
                    reason = reason or "bounded isolated output failed/exceeded storage"
                # docker start may return zero after external termination. Read
                # actual container exit status instead of trusting attachment.
                exit_code = process.returncode
                if container_id:
                    state = json.loads(self._docker(["inspect", container_id]))[0].get("State", {})
                    if state.get("Running") is not False or type(state.get("ExitCode")) is not int:
                        raise ValueError("container did not reach an observed terminated state")
                    exit_code = state["ExitCode"]
                    if state.get("OOMKilled"):
                        reason = reason or "isolated execution exceeded memory limit"
                if exit_code == 124:
                    reason = reason or "daemon-side isolated execution timeout"
                return ProcessResult(exit_code if not reason else (exit_code or 1),
                                     time.monotonic() - started, reason)
        finally:
            if container_id:
                self._remove_owned(container_id, token)
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout:
                    process.stdout.close()
                if process.stdin:
                    process.stdin.close()
            if role == "model" and self.config.engine == "codex" and self.config.auth_root is not None:
                cleanup_auth_runtime(self.config.auth_root,
                    self.config.auth_root.parent / ".lgax-cli-runtime-cache", docker_call=self._docker)


def export_workspace(source: Path, destination: Path, *, max_total_bytes: int = 256 * 1024 * 1024):
    """Export only ordinary tracked working files. Never mount the host .git.

    Caller chooses a fixed reviewed source commit. This helper does not infer
    commit identity or approved changes. It rejects all link/reparse/hardlink
    files, including output tricks. Ignore existing local dependency caches.
    """
    source = _plain_directory(source, "source workspace")
    destination = Path(destination)
    if destination.exists() or destination.resolve().is_relative_to(source):
        raise ValueError("fresh external execution copy required")
    destination.mkdir(parents=True, exist_ok=False)
    excluded = {".git", "private", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
    total = 0
    copied = 0
    # Preserve partial files on failure for trusted private recovery. Do not
    # recursively delete a caller-computed path after a failed export.
    for current, directories, files in os.walk(source, followlinks=False):
        base = Path(current)
        for directory in directories[:]:
            if directory in excluded:
                directories.remove(directory)
                continue
            _plain_directory(base / directory, "source child")
        relative = base.relative_to(source)
        (destination / relative).mkdir(parents=True, exist_ok=True)
        for name in files:
            if name in excluded:
                continue
            data = regular_file(base / name, maximum=max_total_bytes)
            total += len(data)
            if total > max_total_bytes:
                raise ValueError("workspace export exceeds total byte limit")
            target = destination / relative / name
            target.write_bytes(data)
            copied += 1
    return {"exported_files": copied, "exported_bytes": total, "host_git_mounted": False}


def prepare_build_context(source: Path, destination: Path) -> dict:
    """Whitelist a small Docker build context; never send private/auth/.git."""
    source = _plain_directory(source, "reviewed source checkout")
    destination = Path(destination)
    if destination.exists() or destination.resolve().is_relative_to(source):
        raise ValueError("fresh external minimal build context required")
    mapping = {"services/automation/Dockerfile.executor": "Dockerfile",
               "pyproject.toml": "pyproject.toml", "uv.lock": "uv.lock",
               "apps/web/package.json": "apps/web/package.json",
               "apps/web/package-lock.json": "apps/web/package-lock.json"}
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for original, relative in mapping.items():
        data = regular_file(source / original, maximum=4 * 1024 * 1024)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    return {"whitelisted_files": hashes, "private_files_included": False, "git_included": False}


def snapshot_files(workspace: Path, *, maximum: int = 256 * 1024 * 1024) -> dict[str, str]:
    """Freeze an untrusted workspace after all containers have stopped."""
    workspace = _plain_directory(workspace, "frozen execution copy")
    result = {}
    total = 0
    for current, directories, files in os.walk(workspace, followlinks=False):
        for name in directories:
            _plain_directory(Path(current) / name, "frozen child")
        for name in files:
            path = Path(current) / name
            data = regular_file(path, maximum=maximum)
            total += len(data)
            if total > maximum:
                raise ValueError("frozen execution copy exceeds total bytes")
            relative = path.relative_to(workspace).as_posix()
            if relative == ".git" or relative.startswith((".git/", "private/")):
                raise ValueError("execution copy contains forbidden Git/private metadata")
            result[relative] = hashlib.sha256(data).hexdigest()
    return result


def verify_canary_boundary(executor: DockerExecutor, *, cwd: Path, artifacts: Path,
                           protected_canary: Path, output_dir: Path) -> dict:
    """Actual harmless not-mounted proof; never reads a real credential.

    Host publisher can read the harmless canary. Model-style and validator
    processes cannot open that same host file, and observed bind targets exclude
    its parent. Positive workspace and own-AI-profile reads distinguish boundary
    denial from a broken process. Validator also proves network/AI-profile absence.
    """
    canary = regular_file(protected_canary, maximum=4096)
    if not canary or protected_canary.resolve().is_relative_to(executor.config.workspace_root.resolve()):
        raise ValueError("harmless protected canary must be outside all execution mounts")
    if executor.config.auth_root is None or protected_canary.resolve().is_relative_to(executor.config.auth_root.resolve()):
        raise ValueError("publisher canary cannot be inside the mounted AI profile")
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace_canary = cwd / "lgax-workspace-canary.txt"
    if workspace_canary.exists():
        raise ValueError("existing workspace canary must not be overwritten")
    auth_canary = executor.config.auth_root / "lgax-ai-profile-canary.txt"
    if auth_canary.exists():
        raise ValueError("existing AI-profile canary must not be overwritten")
    workspace_canary.write_text("harmless workspace probe", encoding="utf-8")
    auth_canary.write_text("harmless own-AI-profile probe", encoding="utf-8")
    canary_locations = [str(protected_canary.resolve()), "/publisher/lgax-canary.txt"]
    host_path = str(protected_canary.resolve()).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", host_path):
        suffix = host_path[0].lower() + host_path[2:]
        canary_locations.extend(["/host_mnt/" + suffix, "/run/desktop/mnt/host/" + suffix])
    script = '''import json,pathlib,socket
def readable(p):
 try:
  with open(p,'rb') as f:f.read(1)
  return True
 except OSError:return False
try:
 s=socket.create_connection(('1.1.1.1',53),timeout=0.2);s.close();network=True
except OSError:network=False
print(json.dumps({'workspace_readable':readable('/workspace/lgax-workspace-canary.txt'),
 'publisher_canary_readable':any(readable(path) for path in PROTECTED),
 'protected_path_attempts':len(PROTECTED),
 'ai_profile_readable':readable('/agent-auth/lgax-ai-profile-canary.txt'),
 'docker_socket_readable':readable('/var/run/docker.sock'),
 'external_network_reachable':network}))
'''.replace("PROTECTED", repr(canary_locations))
    rows = {}
    try:
        for role in ("model", "validator"):
            output = output_dir / f"{role}-canary.json"
            observed = executor.run(["python", "-c", script], cwd=cwd, artifacts=artifacts,
                env={}, output=output, timeout_seconds=30, heartbeat=lambda: True, role=role)
            if observed.returncode or observed.stopped_reason:
                raise ValueError("actual harmless boundary process failed")
            result = json.loads(output.read_text(encoding="utf-8"))
            if (result.get("workspace_readable") is not True or
                    result.get("publisher_canary_readable") is not False or
                    result.get("protected_path_attempts") != len(canary_locations) or
                    result.get("docker_socket_readable") is not False or
                    result.get("ai_profile_readable") is not (role == "model") or
                    (role == "validator" and result.get("external_network_reachable") is not False)):
                raise ValueError("actual canary/network boundary did not meet policy")
            rows[role] = {**result, "observed_boundary": executor.last_boundary}
        return {"proof_kind": "actual_harmless_container_not_mounted_boundary", "publisher_readable": True,
                "canary_sha256": hashlib.sha256(canary).hexdigest(), "containers": rows,
                "real_secret_used": False, "ai_login_validated": False, "model_generation_executed": False}
    finally:
        workspace_canary.unlink(missing_ok=True)
        auth_canary.unlink(missing_ok=True)
