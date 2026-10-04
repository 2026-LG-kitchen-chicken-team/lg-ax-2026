"""Freeze guest files and import only checked regular bytes into a host checkout.

No Git metadata ever crosses the execution boundary. Containers must already be
stopped before calling these functions. Source code is data for the publisher;
the publisher never imports or executes it.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

if __package__:
    from .isolation import _plain_directory, regular_file
else:
    from isolation import _plain_directory, regular_file

MAX_BYTES = 256 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_FILES = 15000
CACHES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}
SECRET = re.compile(rb"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                    rb"github_pat_[A-Za-z0-9_]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,}|"
                    rb"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}|"
                    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def safe_name(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or "\\" in value or ":" in value or
            any(p in {".", "..", ".git", "private"} or p.casefold().startswith(".env")
                for p in path.parts) or str(path) != value):
        raise ValueError("invalid or private execution artifact path")
    return value


def secret_check(data: bytes, forbidden_values=()):
    if SECRET.search(data) or any(value and len(value) >= 16 and value in data for value in forbidden_values):
        raise ValueError("output resembles a private credential; publishing refused without disclosing it")


def files(root: Path) -> dict[str, bytes]:
    root = _plain_directory(root, "execution snapshot")
    result: dict[str, bytes] = {}
    total = 0
    folded = set()
    for current, directories, names in os.walk(root, followlinks=False):
        base = Path(current)
        for name in directories[:]:
            # Dependencies produced by validators remain only in their private
            # copy. They cannot be imported or published as source changes.
            if name in CACHES:
                directories.remove(name)
                continue
            safe_name((base / name).relative_to(root).as_posix())
            _plain_directory(base / name, "snapshot child")
        for name in names:
            relative = safe_name((base / name).relative_to(root).as_posix())
            key = relative.casefold()
            if key in folded:
                raise ValueError("case-colliding output paths are forbidden")
            folded.add(key)
            data = regular_file(base / name, maximum=MAX_FILE)
            total += len(data)
            if total > MAX_BYTES or len(result) >= MAX_FILES:
                raise ValueError("execution snapshot exceeds bounded file count/bytes")
            result[relative] = data
    return result


def digest(snapshot: dict[str, bytes]) -> str:
    return hashlib.sha256(b"".join(name.encode() + b"\0" + hashlib.sha256(data).digest()
                                 for name, data in sorted(snapshot.items()))).hexdigest()


def write_copy(snapshot: dict[str, bytes], destination: Path):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("execution copy must be a fresh directory")
    destination.mkdir(parents=True)
    for name, data in snapshot.items():
        target = destination / safe_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return digest(snapshot)


def export_tracked(source: Path, destination: Path) -> dict[str, bytes]:
    source = _plain_directory(source, "publisher source")
    entries = subprocess.run(["git", "-c", "core.fsmonitor=false", "ls-files", "--stage", "-z"],
                             cwd=source, capture_output=True, check=True, timeout=30).stdout.decode("utf-8")
    result = {}
    total = 0
    for row in entries.split("\0"):
        if not row:
            continue
        metadata, name = row.split("\t", 1)
        if metadata.split()[0] not in {"100644", "100755"}:
            raise ValueError("tracked links/submodules cannot enter the execution copy")
        safe_name(name)
        target = source / name
        for parent in target.parents:
            if parent == source:
                break
            _plain_directory(parent, "tracked source child")
        data = regular_file(target, maximum=MAX_FILE)
        total += len(data)
        if total > MAX_BYTES or len(result) >= MAX_FILES:
            raise ValueError("tracked export exceeds bounded bytes/files")
        result[name] = data
    write_copy(result, destination)
    return result


def changes(before, after) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


def import_checked(workspace: Path, before, after, *, allow, forbidden_values=()) -> list[str]:
    workspace = _plain_directory(workspace, "trusted publisher checkout")
    modified = changes(before, after)
    if len(modified) > 500:
        raise ValueError("change set exceeds approved bounded publish scope")
    # Validate every path/byte before performing the first write.
    for name in modified:
        safe_name(name)
        if not allow(name):
            raise ValueError(f"change outside approved scope: {name}")
        if name in after:
            secret_check(after[name], forbidden_values)
        target = workspace / name
        if target.exists() and (not target.is_file() or target.lstat().st_nlink != 1):
            raise ValueError("publisher target must be a regular non-hardlinked file")
        for parent in (target, *target.parents):
            if parent == workspace:
                break
            if parent.exists() and (parent.is_symlink() or
                    getattr(parent.lstat(), "st_file_attributes", 0) & 0x400):
                raise ValueError("publisher path contains a link/reparse point")
        if not target.resolve().is_relative_to(workspace):
            raise ValueError("publisher path escapes checkout")
    for name in modified:
        target = workspace / name
        if name in after:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(after[name])
        else:
            target.unlink()
    return modified
