"""Deterministic tracked-source draft packaging. No final mode or code execution."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SKILLS = ("evidence_lookup", "need_extract", "product_compare", "concept_draft", "review_revision")
OFFICIAL_FILES = (
    "자료/공식/01_모집공고.hwp", "자료/공식/01_모집공고.txt",
    "자료/공식/02_참가신청서.hwp", "자료/공식/02_참가신청서.txt",
    "자료/공식/03_포스터.pdf", "자료/공식/04_LG키친솔루션_해커톤주제.pdf",
    "자료/공식/05_2차과제_제출및평가안내.pdf",
)
REQUIRED_FILES = (
    "README.md", "pyproject.toml", "uv.lock", "apps/web/package.json", "apps/web/package-lock.json",
    "packages/contracts/schemas/lgax.schema.json", "data/demo/dataset.json", "data/demo/manifest.json",
    "services/inference/server.py", "harness/phase2/requirements.json",
    *(f"skills/{skill}/SKILL.md" for skill in SKILLS),
    *(f"skills/{skill}/scripts/run.py" for skill in SKILLS), *OFFICIAL_FILES,
)
MANIFEST_PATH = "__submission__/manifest.json"
GUIDE_PATH = "__submission__/DRAFT_README.md"
MAX_FILES = 10000
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
DENIED_PARTS = {"private", ".git", "node_modules", ".venv", "credentials", ".aws", ".ssh",
                "서명", "접수증빙", "제출준비", "signatures", "__submission__"}
DENIED_NAMES = {"credentials.json", "credentials.yaml", "credentials.yml", "secrets.json", "secrets.yaml",
                "secrets.yml", "token.json", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "team.json",
                "editor-client.json", "viewer-client.json", "admin-client.json", "server-credentials.json",
                "server_credentials.json"}
SENSITIVE_FIELDS = {"token", "access_token", "refresh_token", "id_token", "bearer", "password", "api_key",
                    "client_secret", "private_key", "authorization", "secret", "lgax_workspace_token"}
SECRET_PATTERNS = (
    rb"(?m)^-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----\r?$",
    rb"\b(?:ghp_|gho_|ghu_|ghs_|github_pat_|hf_)[A-Za-z0-9_]{20,}\b",
    rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b",
    rb"\bAKIA[A-Z0-9]{16}\b",
)


class PackageError(ValueError):
    """Explicit packaging rejection; tracked files are never silently omitted."""


@dataclass(frozen=True)
class Blob:
    path: str
    mode: str
    oid: str
    data: bytes


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _git(repo: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    environment = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
                   "GIT_NO_REPLACE_OBJECTS": "1"}
    try:
        result = subprocess.run(["git", "--no-pager", "-C", str(repo), *arguments], input=input_bytes,
                                capture_output=True, check=False, env=environment, timeout=60)
    except subprocess.SubprocessError as error:
        raise PackageError("Local Git source inspection exceeded its execution limit") from error
    if result.returncode:
        raise PackageError("Local Git source inspection failed; no fetch or credential prompt is attempted")
    return result.stdout


def repository(path: Path) -> Path:
    repo = path.resolve()
    if not repo.is_dir():
        raise PackageError("Repository directory does not exist")
    top = Path(_git(repo, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if top != repo:
        raise PackageError("--repo must name the repository root")
    return repo


def _safe_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name)
    if normalized != name:
        _safe_name(normalized)
    if (not name or "\\" in name or ":" in name or any(ord(character) < 32 for character in name)
            or name.startswith("/") or any(part in ("", ".", "..") for part in name.split("/"))):
        raise PackageError(f"Unsafe archive path: {name!r}")
    for part in PurePosixPath(name).parts:
        if part.endswith((".", " ")) or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part):
            raise PackageError(f"Nonportable archive path: {name!r}")
    return normalized.casefold()


def _deny_source_path(name: str) -> None:
    _safe_name(name)
    parts = PurePosixPath(unicodedata.normalize("NFKC", name)).parts
    lower_parts = {part.casefold() for part in parts}
    basename = parts[-1].casefold()
    if lower_parts & DENIED_PARTS or basename in DENIED_NAMES:
        raise PackageError(f"Disallowed tracked path: {name}")
    if basename.startswith(".env") and basename != ".env.example":
        raise PackageError(f"Disallowed environment file: {name}")
    if basename.endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".sqlite-wal",
                          ".sqlite-shm", ".mdb", ".pem", ".key", ".p12", ".pfx", ".jks")):
        raise PackageError(f"Database or credential material is tracked: {name}")
    if basename.startswith(("service-account", "service_account")) and basename.endswith(".json"):
        raise PackageError(f"Credential file is tracked: {name}")
    # Known application/consent/signature categories, including copies outside private/.
    binary_document = basename.endswith((".pdf", ".hwp", ".hwpx", ".hml", ".docx", ".png", ".jpg", ".jpeg"))
    sensitive = (re.match(r"\d{8}[_ -]", basename) or any(word in basename for word in (
        "참가신청서", "작성신청서", "동의서", "서약서", "서명", "signature", "consent", "signed",
        "황대겸팀장", "4인최종본", "최종점검본", "재신청본", "도표보완본", "시각보완본")))
    if binary_document and sensitive and name not in OFFICIAL_FILES:
        raise PackageError(f"Personal application/signature artifact is tracked: {name}")


def _check_content(name: str, data: bytes) -> None:
    if data.startswith(b"SQLite format 3\0") or any(re.search(pattern, data) for pattern in SECRET_PATTERNS):
        raise PackageError(f"Credential/database content detected: {name}")
    if name.casefold().endswith(".json"):
        try:
            document = json.loads(data)
        except (ValueError, UnicodeError):
            document = None

        def placeholder(value):
            if value is None or value == "":
                return True
            if not isinstance(value, str):
                return False
            value = value.strip()
            return (value.upper() in {"REDACTED", "[REDACTED]", "MASKED", "***", "REPLACE_ME", "CHANGEME"}
                    or re.fullmatch(r"<[A-Za-z0-9_ -]+>|YOUR_[A-Z0-9_]+", value) is not None
                    or re.fullmatch(r"\$\{[A-Z_][A-Z0-9_]*\}|\$[A-Z_][A-Z0-9_]*|env:[A-Z_][A-Z0-9_]*", value) is not None)

        def inspect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    field = key.casefold()
                    if field in SENSITIVE_FIELDS and isinstance(child, (str, int, float)) and not placeholder(child):
                        raise PackageError(f"Literal credential field detected in JSON: {name}")
                    if field in {"student_id", "student_number", "학번"} and re.fullmatch(r"\d{8}", str(child)):
                        raise PackageError(f"Student identifier field detected in JSON: {name}")
                    if (field in {"phone", "phone_number", "mobile", "연락처"} and isinstance(child, str)
                            and re.fullmatch(r"010\d{7,8}", re.sub(r"[^0-9]", "", child))):
                        raise PackageError(f"Personal mobile number field detected in JSON: {name}")
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(document)
    if PurePosixPath(name).name.casefold() == ".env.example":
        try:
            lines = data.decode("utf-8-sig").splitlines()
        except UnicodeError as error:
            raise PackageError(".env.example must be UTF-8 placeholder text") from error
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"\s*[A-Z_][A-Z0-9_]*\s*=\s*(.*?)\s*", line)
            if not match:
                raise PackageError(".env.example accepts comments and NAME=placeholder only")
            value = match[1]
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value and not (re.fullmatch(r"<[A-Za-z0-9_ -]+>", value)
                              or re.fullmatch(r"(?:YOUR_[A-Z0-9_]+|REPLACE_ME|CHANGEME)", value)):
                raise PackageError(".env.example values must be empty or explicit placeholders")


def tracked_source(repo: Path, ref: str) -> tuple[str, str, list[Blob]]:
    commit = _git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise PackageError("Resolved Git commit is invalid")
    tree = _git(repo, "rev-parse", commit + "^{tree}").decode().strip()
    raw = _git(repo, "ls-tree", "-r", "-l", "-z", "--full-tree", commit)
    entries, names, size_total = [], set(), 0
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        try:
            name = raw_name.decode("utf-8")
        except UnicodeError as error:
            raise PackageError("Tracked filenames must be UTF-8") from error
        mode, kind, oid, size = metadata.decode("ascii").split()
        _deny_source_path(name)
        portable = _safe_name(name)
        if portable in names:
            raise PackageError("Tracked filenames collide after portable Unicode/case normalization")
        names.add(portable)
        if kind != "blob" or mode not in ("100644", "100755"):
            raise PackageError(f"Symlink, submodule or unsupported tracked mode: {name}")
        size_value = int(size)
        size_total += size_value
        if size_value > MAX_FILE_BYTES or size_total > MAX_TOTAL_BYTES or len(entries) >= MAX_FILES:
            raise PackageError("Source draft exceeds the explicit archive size/count limit")
        entries.append((name, mode, oid, size_value))
    missing = sorted(set(REQUIRED_FILES) - {entry[0] for entry in entries})
    if missing:
        raise PackageError("Required source files are missing: " + ", ".join(missing))
    stream = _git(repo, "cat-file", "--batch", input_bytes="".join(f"{entry[2]}\n" for entry in entries).encode())
    offset, blobs = 0, []
    for name, mode, oid, size in entries:
        end = stream.find(b"\n", offset)
        header = stream[offset:end].decode("ascii").split()
        if header != [oid, "blob", str(size)]:
            raise PackageError("Git blob stream identity/size mismatch")
        offset = end + 1
        data = stream[offset:offset + size]
        if len(data) != size or stream[offset + size:offset + size + 1] != b"\n":
            raise PackageError("Truncated Git blob stream")
        offset += size + 1
        _check_content(name, data)
        blobs.append(Blob(name, mode, oid, data))
    if offset != len(stream):
        raise PackageError("Unexpected trailing Git blob data")
    return commit, tree, sorted(blobs, key=lambda blob: blob.path)


def private_path(repo: Path, path: Path) -> Path:
    private = (repo / "private").resolve()
    candidate = (path if path.is_absolute() else repo / path).resolve()
    if not private.is_relative_to(repo) or private == repo or not candidate.is_relative_to(private) or candidate == private:
        raise PackageError("Output/archive/extract paths must stay inside this repository's private/ directory")
    return candidate


def manifest_for(commit: str, tree: str, blobs: list[Blob]) -> dict:
    requirements = next(blob.data for blob in blobs if blob.path == "harness/phase2/requirements.json")
    try:
        rows = json.loads(requirements)["requirements"]
        coverage = {"total": len(rows), "declared_verified": sum(row["status"] == "verified" for row in rows),
                    "independently_verified_by_packager": False}
    except (ValueError, KeyError, TypeError) as error:
        raise PackageError("The tracked requirement coverage snapshot is malformed") from error
    return {"schema_version": 1, "draft": True, "submission_ready": False, "source_commit": commit,
            "source_tree": tree, "source_snapshot": "all_tracked_git_blobs",
            "compression": "ZIP_STORED", "declared_application_coverage": coverage,
            "replay_executed_by_packager": False,
            "files": [{"path": blob.path, "git_mode": blob.mode, "git_blob": blob.oid,
                       "size": len(blob.data), "sha256": digest(blob.data)} for blob in blobs]}


def draft_guide(manifest: dict) -> bytes:
    coverage = manifest["declared_application_coverage"]
    return f"""# Source draft — 정식 제출본 아님

Git commit: {manifest['source_commit']}
추적된 전체 원본 바이트를 포함한 초안이다. source manifest의 파일 SHA256을 확인한다.
신청서 요구의 기록상 verified: {coverage['declared_verified']}/{coverage['total']}.
이 도구는 Agent/네 Skill 판단의 구현 완료, 실제 평가, 발표·영상·촬영 코드 일치, 제출을 판정하지 않는다.
최종 제출 모드는 없다. 설치/검사/네트워크/모델 호출도 실행하지 않았다.

## PM이 깨끗한 압축 해제 환경에서 실행할 검사

README.md를 먼저 읽고 Python3.11·uv·Node22 환경에서 실행한다.

```powershell
uv sync --locked --dev
uv run python scripts/check_contracts.py
uv run python -m unittest discover -s tests -p test_skill_runner.py -v
uv run python scripts/smoke_mcp.py --transport stdio
npm ci --prefix apps/web
npm run test --prefix apps/web
npm run build --prefix apps/web
```

설치는 네트워크를 사용할 수 있으므로 PM이 별도 실행한다. 실제 모델/호스트 검사는 해당 실행 조건과 증빙을 별도 연결한다.
.git·비밀키·개인 DB는 포함하지 않는다. Git history를 요구하는 과거 하네스 증거 감사에는 원격 저장소의 해당 history가 필요할 수 있다.
검사 성공을 상품기획 판단·31요구 완주·정식 제출 성공으로 바꾸지 않는다.
""".encode()


def _zip_info(name: str, mode: str = "100644") -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | (0o755 if mode == "100755" else 0o644)) << 16
    return info


def build(repo_path: Path, ref: str, output_path: Path) -> dict:
    repo = repository(repo_path)
    output = private_path(repo, output_path)
    sidecar = output.with_name(output.name + ".provenance.json")
    if output.suffix.casefold() != ".zip" or output.exists() or sidecar.exists():
        raise PackageError("A new .zip and provenance filename are required; existing outputs are never overwritten")
    commit, tree, blobs = tracked_source(repo, ref)
    manifest = manifest_for(commit, tree, blobs)
    manifest_data = json_bytes(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for blob in blobs:
            archive.writestr(_zip_info(blob.path, blob.mode), blob.data)
        archive.writestr(_zip_info(MANIFEST_PATH), manifest_data)
        archive.writestr(_zip_info(GUIDE_PATH), draft_guide(manifest))
    archive_data = buffer.getvalue()
    provenance = {"schema_version": 1, "draft": True, "submission_ready": False,
                  "source_commit": commit, "archive_name": output.name,
                  "archive_sha256": digest(archive_data), "manifest_sha256": digest(manifest_data),
                  "source_file_count": len(blobs)}
    output.parent.mkdir(parents=True, exist_ok=True)
    private_path(repo, output)
    with output.open("xb") as stream:
        stream.write(archive_data)
    with sidecar.open("xb") as stream:
        stream.write(json_bytes(provenance))
    return {**provenance, "archive_path": str(output), "provenance_path": str(sidecar)}


def verified_contents(repo_path: Path, archive_path: Path) -> tuple[dict, dict[str, bytes]]:
    repo = repository(repo_path)
    path = private_path(repo, archive_path)
    if path.stat().st_size > MAX_TOTAL_BYTES + 16 * 1024 * 1024:
        raise PackageError("Archive byte size exceeds the explicit limit")
    data = path.read_bytes()
    provenance = json.loads(path.with_name(path.name + ".provenance.json").read_text(encoding="utf-8"))
    if not isinstance(provenance, dict) or provenance.get("archive_sha256") != digest(data):
        raise PackageError("ZIP SHA256 differs from its recorded provenance")
    contents, portable_names, metadata, total = {}, set(), {}, 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > MAX_FILES + 2:
                raise PackageError("Archive entry count exceeds the explicit limit")
            for info in archive.infolist():
                portable = _safe_name(info.filename)
                total += info.file_size
                mode = info.external_attr >> 16
                if (portable in portable_names or info.is_dir() or info.flag_bits & 1
                        or stat.S_IFMT(mode) != stat.S_IFREG or info.compress_type != zipfile.ZIP_STORED
                        or info.file_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES):
                    raise PackageError("Duplicate, encrypted, nonregular or oversized archive entry")
                portable_names.add(portable)
                metadata[info.filename] = info
                contents[info.filename] = archive.read(info)
    except zipfile.BadZipFile as error:
        raise PackageError("Invalid ZIP or CRC mismatch") from error
    if MANIFEST_PATH not in contents or GUIDE_PATH not in contents:
        raise PackageError("Draft manifest/guide missing")
    manifest = json.loads(contents[MANIFEST_PATH])
    commit, tree, blobs = tracked_source(repo, manifest["source_commit"])
    expected = manifest_for(commit, tree, blobs)
    if contents[MANIFEST_PATH] != json_bytes(expected) or contents[GUIDE_PATH] != draft_guide(expected):
        raise PackageError("Manifest/guide differs from the actual tracked commit")
    if set(contents) != {blob.path for blob in blobs} | {MANIFEST_PATH, GUIDE_PATH}:
        raise PackageError("ZIP filenames do not match the complete tracked source set")
    for blob in blobs:
        if contents[blob.path] != blob.data:
            raise PackageError(f"ZIP source bytes differ from the fixed commit: {blob.path}")
        expected_info = _zip_info(blob.path, blob.mode)
        actual_info = metadata[blob.path]
        if (actual_info.external_attr != expected_info.external_attr
                or actual_info.create_system != expected_info.create_system
                or actual_info.date_time != expected_info.date_time):
            raise PackageError(f"ZIP file mode/platform/time differs from its deterministic format: {blob.path}")
    expected_provenance = {"schema_version": 1, "draft": True, "submission_ready": False,
                           "source_commit": commit, "archive_name": path.name, "archive_sha256": digest(data),
                           "manifest_sha256": digest(contents[MANIFEST_PATH]), "source_file_count": len(blobs)}
    if provenance != expected_provenance:
        raise PackageError("Provenance fields do not match the verified source draft")
    return {**provenance, "verified": True, "archive_path": str(path)}, contents


def verify(repo_path: Path, archive_path: Path) -> dict:
    return verified_contents(repo_path, archive_path)[0]


def unpack(repo_path: Path, archive_path: Path, destination_path: Path) -> dict:
    repo = repository(repo_path)
    destination = private_path(repo, destination_path)
    if destination.exists():
        raise PackageError("Extraction requires a new destination; existing files are preserved")
    result, contents = verified_contents(repo, archive_path)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(contents[MANIFEST_PATH])
    modes = {item["path"]: item["git_mode"] for item in manifest["files"]}
    for name, data in contents.items():
        output = destination.joinpath(*PurePosixPath(name).parts)
        if not output.resolve().is_relative_to(destination):
            raise PackageError("Extraction path escaped the new destination")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(data)
        if os.name != "nt":
            output.chmod(0o755 if modes.get(name) == "100755" else 0o644)
    return {**result, "extract_path": str(destination), "extracted_files": len(contents),
            "replay_executed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "unpack"):
        sub = commands.add_parser(command)
        sub.add_argument("--repo", type=Path, default=Path.cwd())
        if command == "build":
            sub.add_argument("--commit", required=True)
            sub.add_argument("--output", type=Path, required=True)
        else:
            sub.add_argument("--archive", type=Path, required=True)
            if command == "unpack":
                sub.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build(args.repo, args.commit, args.output)
        elif args.command == "verify":
            result = verify(args.repo, args.archive)
        else:
            result = unpack(args.repo, args.archive, args.destination)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=True))
        return 0
    except (PackageError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
