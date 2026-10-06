"""Lossless, local-only migration of member Markdown logs into navigable folders.

The tool reads immutable local Git blobs, retains all old session files, and never
infers a work status or evidence date. Verification reverses every link edit and
reconstructs each original byte stream. It does not execute project code, contact
GitHub, report a task, change automation, or invoke a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("정이량", "황대겸", "신진하", "최길웅")
KINDS = ("작업기록", "작업근거")
SOURCE_PATHS = tuple(f"docs/{kind}/{name}.md" for kind in KINDS for name in MEMBERS)
MANIFEST_PATH = "docs/작업기록/이관/20261006/manifest.json"
BODY_START = b"<!-- member-log:body:start -->\n"
BODY_END = b"\n<!-- member-log:body:end -->\n"
OWNER_UPDATE_START = b"<!-- member-log:owner-updates:start -->\n"
OWNER_UPDATE_END = b"<!-- member-log:owner-updates:end -->\n"
SCHEMA_VERSION = 1
HEADING = re.compile(rb"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE = re.compile(rb"^ {0,3}(`{3,}|~{3,})(.*)$")
LINK = re.compile(rb"!?\[[^\]\r\n]*\]\((?P<target>[^)\r\n]+)\)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class MigrationError(ValueError):
    """The proposed migration or saved proof is unsafe or inconsistent."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_repo_path(value: str) -> str:
    """Validate a normalized repository-relative output/manifest path."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise MigrationError(f"Invalid repository path: {value!r}")
    if SCHEME.match(value) or value.startswith("/"):
        raise MigrationError(f"Absolute repository path: {value!r}")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise MigrationError(f"Non-normalized repository path: {value!r}")
    if PurePosixPath(value).as_posix() != value:
        raise MigrationError(f"Non-normalized repository path: {value!r}")
    return value


def _local_path(root: Path, value: str) -> Path:
    value = safe_repo_path(value)
    resolved_root = root.resolve()
    path = root.joinpath(*value.split("/"))
    resolved = path.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise MigrationError(f"Path escapes root through a symlink: {value}")
    return path


def parse_headings(blob: bytes) -> list[dict]:
    """Read real ATX headings, retaining byte positions and original line bytes."""
    blob.decode("utf-8-sig")
    headings = []
    fence = None
    offset = 0
    for line_number, raw_line in enumerate(blob.splitlines(keepends=True), 1):
        line = raw_line.rstrip(b"\r\n")
        if offset == 0:
            line = line.removeprefix(b"\xef\xbb\xbf")
        match = FENCE.match(line)
        if match:
            marker = match[1]
            if fence is None:
                fence = (marker[:1], len(marker))
            elif marker[:1] == fence[0] and len(marker) >= fence[1] and not match[2].strip():
                fence = None
        elif fence is None:
            match = HEADING.match(line)
            if match:
                headings.append({
                    "offset": offset,
                    "end": offset + len(raw_line),
                    "line": line_number,
                    "level": len(match[1]),
                    "title": match[2].decode("utf-8"),
                })
        offset += len(raw_line)
    return headings


def _id_pattern(owner: str) -> re.Pattern:
    return re.compile(
        re.escape(owner) + r"-(?:20\d{6}-[\w-]+|E\d+[\w-]*|IDENTITY[\w-]+)"
    )


def _record_ids(title: str, owner: str) -> list[str]:
    ids = list(dict.fromkeys(_id_pattern(owner).findall(title)))
    bare = re.match(r"E\d+[\w-]*", title)
    if bare:
        ids.append(bare[0])
    return ids


def _heading_date(title: str, owner: str) -> tuple[str, dict | None]:
    match = re.search(re.escape(owner) + r"-(?:E)?(20\d{6})-", title)
    if not match:
        return "legacy", None
    try:
        date = datetime.strptime(match[1], "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return "legacy", None
    return date, {"kind": "heading_dated_record_id", "value": match[0].rstrip("-")}


def split_sections(blob: bytes, owner: str) -> list[dict]:
    """Partition every byte; H2 or a directly named H3 record begins a section."""
    if owner not in MEMBERS:
        raise MigrationError(f"Unknown member: {owner}")
    headings = parse_headings(blob)
    boundaries = {0: None}
    direct_id = _id_pattern(owner)
    for heading in headings:
        if heading["level"] == 2 or (
            heading["level"] == 3 and direct_id.match(heading["title"])
        ):
            boundaries[heading["offset"]] = heading
    starts = sorted(boundaries)
    result = []
    for ordinal, start in enumerate(starts, 1):
        end = starts[ordinal] if ordinal < len(starts) else len(blob)
        heading = boundaries[start]
        title = heading["title"] if heading else "소개·공통 참조"
        date, date_basis = _heading_date(title, owner)
        result.append({
            "ordinal": ordinal,
            "start": start,
            "end": end,
            "line_start": blob[:start].count(b"\n") + 1,
            "line_end": blob[:end].count(b"\n") + (0 if blob[:end].endswith(b"\n") else 1),
            "title": title,
            "level": heading["level"] if heading else 0,
            "record_ids": _record_ids(title, owner),
            "date": date,
            "date_basis": date_basis,
        })
    return result


def _relative_target(target: str, source_path: str) -> tuple[str, str, str] | None:
    """Resolve an inline Markdown target without following filesystem links."""
    token = target.strip()
    angled = token.startswith("<") and token.endswith(">")
    inner = token[1:-1] if angled else token
    if not inner or SCHEME.match(inner) or inner.startswith(("/", "#")):
        return None
    if "\\" in inner or "\x00" in inner:
        raise MigrationError(f"Unsupported relative Markdown target: {target!r}")
    # This corpus has no destination titles. Refuse ambiguity rather than guessing.
    if re.search(r'\s+[\"\']', inner):
        raise MigrationError(f"Markdown destination title requires review: {target!r}")
    parsed = urlsplit(inner)
    if parsed.netloc or parsed.scheme:
        return None
    decoded_path = unquote(parsed.path)
    if decoded_path.startswith("/") or "\\" in decoded_path or SCHEME.match(decoded_path):
        raise MigrationError(f"Unsafe encoded Markdown target: {target!r}")
    repo_path = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), decoded_path))
    safe_repo_path(repo_path)
    return repo_path, parsed.query, parsed.fragment


def _markdown_links(blob: bytes):
    """Ignore link-shaped data inside fenced or inline backtick code."""
    protected = []
    fence = None
    offset = 0
    for raw_line in blob.splitlines(keepends=True):
        line = raw_line.rstrip(b"\r\n")
        first_line = line.removeprefix(b"\xef\xbb\xbf") if offset == 0 else line
        match = FENCE.match(first_line)
        if match:
            marker = match[1]
            if fence is None:
                fence = (marker[:1], len(marker))
            elif marker[:1] == fence[0] and len(marker) >= fence[1] and not match[2].strip():
                fence = None
            protected.append((offset, offset + len(raw_line)))
        elif fence:
            protected.append((offset, offset + len(raw_line)))
        else:
            ticks = list(re.finditer(rb"`+", line))
            index = 0
            while index < len(ticks):
                opening = ticks[index]
                preceding = line[:opening.start()]
                escape_count = len(preceding) - len(preceding.rstrip(b"\\"))
                if escape_count % 2:
                    index += 1
                    continue
                closing_index = next((i for i in range(index + 1, len(ticks)) if len(ticks[i][0]) == len(opening[0])), None)
                if closing_index is None:
                    index += 1
                    continue
                protected.append((offset + opening.start(), offset + ticks[closing_index].end()))
                index = closing_index + 1
        offset += len(raw_line)
    for match in LINK.finditer(blob):
        if any(match.start() < end and match.end() > start for start, end in protected):
            continue
        preceding = blob[:match.start()]
        if (len(preceding) - len(preceding.rstrip(b"\\"))) % 2:
            continue
        yield match


def rewrite_links(blob: bytes, source_path: str, new_path: str) -> tuple[bytes, list[dict]]:
    """Rewrite only relative Markdown destination spans; record reversible edits."""
    safe_repo_path(source_path)
    safe_repo_path(new_path)
    edits = []
    pieces = []
    original_cursor = 0
    rendered_cursor = 0
    for match in _markdown_links(blob):
        target_bytes = match["target"]
        target = target_bytes.decode("utf-8")
        resolved = _relative_target(target, source_path)
        if resolved is None:
            continue
        repo_path, query, fragment = resolved
        relative = posixpath.relpath(repo_path, posixpath.dirname(new_path))
        replacement = urlunsplit(("", "", relative, query, fragment))
        stripped = target.strip()
        if stripped.startswith("<") and stripped.endswith(">"):
            replacement = "<" + replacement + ">"
        replacement = target[:len(target) - len(target.lstrip())] + replacement
        replacement += target[len(target.rstrip()):]
        replacement_bytes = replacement.encode("utf-8")
        start, end = match.span("target")
        unchanged = blob[original_cursor:start]
        pieces.extend((unchanged, replacement_bytes))
        rendered_start = rendered_cursor + len(unchanged)
        edits.append({
            "source_start": start,
            "source_end": end,
            "rendered_start": rendered_start,
            "rendered_end": rendered_start + len(replacement_bytes),
            "original": target,
            "replacement": replacement,
            "target_path": repo_path,
            "fragment": fragment,
        })
        original_cursor = end
        rendered_cursor = rendered_start + len(replacement_bytes)
    pieces.append(blob[original_cursor:])
    rendered = b"".join(pieces)
    if restore_body(rendered, edits) != blob:
        raise MigrationError("Internal link transformation is not reversible")
    return rendered, edits


def restore_body(rendered: bytes, edits: list[dict]) -> bytes:
    pieces = []
    cursor = 0
    source_cursor = 0
    for edit in edits:
        start, end = edit["rendered_start"], edit["rendered_end"]
        if not isinstance(start, int) or not isinstance(end, int) or start < cursor or end < start:
            raise MigrationError("Overlapping or invalid link edits")
        original = edit["original"].encode("utf-8")
        replacement = edit["replacement"].encode("utf-8")
        if end > len(rendered) or rendered[start:end] != replacement:
            raise MigrationError("Rendered destination differs from recorded link edit")
        unchanged = rendered[cursor:start]
        if edit["source_start"] != source_cursor + len(unchanged):
            raise MigrationError("Original link offset differs from recorded coverage")
        if edit["source_end"] != edit["source_start"] + len(original):
            raise MigrationError("Original destination length differs from recorded edit")
        pieces.extend((unchanged, original))
        cursor = end
        source_cursor = edit["source_end"]
    pieces.append(rendered[cursor:])
    return b"".join(pieces)


def _slug(value: str) -> str:
    slug = re.sub(r"[^\w.-]+", "-", value).strip(".-")[:72]
    return slug or "context"


def _md_link(label: str, target: str, base: str) -> str:
    return f"[{label}]({posixpath.relpath(target, posixpath.dirname(base))})"


def _native_references(blob: bytes) -> dict:
    tokens = re.findall(rb"`[^`\r\n]+`", blob)
    return {"count": len(tokens), "sha256": sha256(b"\x00".join(tokens))}


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_plan(source_commit: str, blobs: dict[str, bytes], sessions: dict[str, bytes]) -> tuple[dict, dict[str, bytes]]:
    """Construct deterministic metadata/documents entirely in memory."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise MigrationError("Source commit must be the full lowercase 40-character SHA")
    if set(blobs) != set(SOURCE_PATHS):
        raise MigrationError("Exactly the eight cumulative member sources are required")
    outputs = {}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "manifest_path": MANIFEST_PATH,
        "date_policy": "Only a valid dated record ID in the source heading; otherwise legacy",
        "split_policy": "Every H2 and directly member-ID-prefixed H3 outside fenced code",
        "sources": [],
        "sessions": [],
        "outputs": {},
    }
    for source_path in SOURCE_PATHS:
        blob = blobs[source_path]
        kind = source_path.split("/")[1]
        owner = PurePosixPath(source_path).stem
        headings = parse_headings(blob)
        base = f"docs/{kind}/{owner}"
        archive_path = f"{base}/archive/{source_commit[:8]}-original.md"
        readme_path = f"{base}/README.md"
        sections = split_sections(blob, owner)
        if BODY_START in blob or BODY_END in blob:
            raise MigrationError(f"Reserved wrapper marker already exists in {source_path}")
        source = {
            "path": source_path,
            "owner": owner,
            "kind": kind,
            "bytes": len(blob),
            "sha256": sha256(blob),
            "archive_path": archive_path,
            "readme_path": readme_path,
            "headings": headings,
            "native_references": _native_references(blob),
            "sections": [],
            "record_id_map": {},
        }
        outputs[archive_path] = blob
        for section in sections:
            title = section["title"]
            slug = _slug(section["record_ids"][0] if section["record_ids"] else title)
            entry_path = f"{base}/{section['date']}/{section['ordinal']:04d}-{slug}.md"
            original = blob[section["start"]:section["end"]]
            rendered, edits = rewrite_links(original, source_path, entry_path)
            prefix = (
                "<!-- member-log:entry v1; generated navigation, original content below -->\n"
                f"원본: `{source_path}` · source commit `{source_commit}`\n\n"
                f"원문 byte 구간: {section['start']}..{section['end']} · "
                f"원문 행: {section['line_start']}..{section['line_end']}\n\n"
                f"{_md_link('개인 목차', readme_path, entry_path)} · "
                f"{_md_link('원바이트 전체 원본', archive_path, entry_path)}\n\n"
            ).encode("utf-8") + BODY_START
            entry = prefix + rendered + BODY_END
            outputs[entry_path] = entry
            item = dict(section)
            item.update({
                "path": entry_path,
                "original_sha256": sha256(original),
                "rendered_sha256": sha256(rendered),
                "rendered_body_start": len(prefix),
                "rendered_body_end": len(prefix) + len(rendered),
                "file_sha256": sha256(entry),
                "link_edits": edits,
            })
            source["sections"].append(item)
            for heading in headings:
                if section["start"] <= heading["offset"] < section["end"]:
                    for record_id in _record_ids(heading["title"], owner):
                        paths = source["record_id_map"].setdefault(record_id, [])
                        if entry_path not in paths:
                            paths.append(entry_path)
        # Retain every original real heading in its original order/level/wording.
        index = (
            "<!-- member-log:compatibility-index v1 -->\n"
            f"원문 분할 목차: {_md_link('개인 README', readme_path, source_path)}. "
            f"보존 원본: {_md_link('전체 원바이트 snapshot', archive_path, source_path)}.\n\n"
            "이 파일은 기존 경로·제목 anchor를 위한 기계 생성 목차입니다. "
            "원문 내용과 과거 상태는 연결된 상세 파일에서 확인합니다.\n\n"
        ).encode("utf-8")
        for heading in headings:
            raw_line = blob[heading["offset"]:heading["end"]].removeprefix(b"\xef\xbb\xbf")
            index += raw_line
            if not raw_line.endswith(b"\n"):
                index += b"\n"
            item = next(s for s in source["sections"] if s["start"] <= heading["offset"] < s["end"])
            index += (f"\n{_md_link('해당 원문 구간', item['path'], source_path)}\n\n").encode("utf-8")
        if not headings:
            index += (_md_link("원문 구간", source["sections"][0]["path"], source_path) + "\n").encode("utf-8")
        index = index.rstrip(b"\n") + b"\n"
        outputs[source_path] = index
        opposite = "작업근거" if kind == "작업기록" else "작업기록"
        opposite_readme = f"docs/{opposite}/{owner}/README.md"
        readme = (
            f"# {owner} — {kind} 목차\n\n"
            "기존 원문의 기계적 분할·탐색 목차입니다. 새 수행·판정·완료 상태를 추가하지 않습니다.\n\n"
            f"{_md_link('연결된 개인 ' + opposite, opposite_readme, readme_path)} · "
            f"{_md_link('기존 경로·anchor 목차', source_path, readme_path)} · "
            f"{_md_link('전체 원바이트 snapshot', archive_path, readme_path)}\n\n"
        ).encode("utf-8")
        resume = next((s for s in sections if s["level"] == 2 and "재개" in s["title"] and "요약" in s["title"]), None)
        if resume:
            excerpt, _ = rewrite_links(blob[resume["start"]:resume["end"]], source_path, readme_path)
            readme += (
                "## 첫 재개 요약의 원문\n\n"
                f"{_md_link('전체 원문 구간', source['sections'][resume['ordinal'] - 1]['path'], readme_path)}\n\n"
            ).encode("utf-8") + excerpt + b"\n"
        readme += "## 원문 구간 — 원래 순서\n\n".encode("utf-8")
        for item in source["sections"]:
            readme += (
                f"- {item['ordinal']:04d} · `{item['date']}` · "
                f"{_md_link(item['title'].replace('[', '(').replace(']', ')'), item['path'], readme_path)}\n"
            ).encode("utf-8")
        readme += "\n## 기록 ID 조회\n\n".encode("utf-8")
        for record_id, paths in source["record_id_map"].items():
            links = " · ".join(_md_link(f"원문 {i}", path, readme_path) for i, path in enumerate(paths, 1))
            readme += f"- `{record_id}`: {links}\n".encode("utf-8")
        readme += "\n## 기존 불변 세션 — 원래 경로 유지\n\n".encode("utf-8")
        for session_path in sorted(sessions):
            if session_path.startswith(f"docs/{kind}/세션/{owner}/"):
                readme += (f"- {_md_link(PurePosixPath(session_path).name, session_path, readme_path)}\n").encode("utf-8")
        outputs[readme_path] = readme
        manifest["sources"].append(source)
    for path, blob in sorted(sessions.items()):
        safe_repo_path(path)
        if not any(path.startswith(f"docs/{kind}/세션/{member}/") for kind in KINDS for member in MEMBERS):
            raise MigrationError(f"Unexpected old session path: {path}")
        relative_links = []
        for match in _markdown_links(blob):
            token = match["target"].decode("utf-8")
            resolved = _relative_target(token, path)
            if resolved:
                relative_links.append({"original": token, "target_path": resolved[0], "fragment": resolved[2]})
        manifest["sessions"].append({
            "path": path, "bytes": len(blob), "sha256": sha256(blob), "relative_links": relative_links,
        })
    manifest["outputs"] = {path: {"bytes": len(blob), "sha256": sha256(blob)} for path, blob in sorted(outputs.items())}
    manifest["totals"] = {
        "source_files": len(blobs),
        "source_bytes": sum(len(blob) for blob in blobs.values()),
        "sections": sum(len(source["sections"]) for source in manifest["sources"]),
        "session_files": len(sessions),
        "session_bytes": sum(len(blob) for blob in sessions.values()),
        "relative_links": sum(len(item["link_edits"]) for source in manifest["sources"] for item in source["sections"])
        + sum(len(session["relative_links"]) for session in manifest["sessions"]),
    }
    outputs[MANIFEST_PATH] = _json_bytes(manifest)
    return manifest, outputs


def _read_required(root: Path, path: str) -> bytes:
    file = _local_path(root, path)
    if not file.is_file():
        raise MigrationError(f"Missing required file: {path}")
    return file.read_bytes()


def _canonical_output(path: str, blob: bytes) -> bytes:
    """Permit one explicitly delimited owner-written README update, preserving the index."""
    if path not in {f"docs/{kind}/{owner}/README.md" for kind in KINDS for owner in MEMBERS}:
        return blob
    count_start, count_end = blob.count(OWNER_UPDATE_START), blob.count(OWNER_UPDATE_END)
    if count_start == count_end == 0:
        return blob
    if count_start != 1 or count_end != 1:
        raise MigrationError(f"Ambiguous owner update markers: {path}")
    start = blob.index(OWNER_UPDATE_START)
    end = blob.index(OWNER_UPDATE_END)
    if end < start:
        raise MigrationError(f"Out-of-order owner update markers: {path}")
    return blob[:start] + blob[end + len(OWNER_UPDATE_END):]


def apply_plan(root: Path, manifest: dict, outputs: dict[str, bytes]) -> None:
    """Preflight all paths/bytes before writing; never delete or replace old sessions."""
    expected_keys = set(manifest["outputs"]) | {MANIFEST_PATH}
    if set(outputs) != expected_keys or outputs[MANIFEST_PATH] != _json_bytes(manifest):
        raise MigrationError("Output keys/manifest bytes differ from the declared plan")
    for path, receipt in manifest["outputs"].items():
        if len(outputs[path]) != receipt["bytes"] or sha256(outputs[path]) != receipt["sha256"]:
            raise MigrationError(f"Output differs from the declared plan: {path}")
    session_blobs = {}
    for session in manifest["sessions"]:
        blob = _read_required(root, session["path"])
        if sha256(blob) != session["sha256"]:
            raise MigrationError(f"Old session changed since source snapshot: {session['path']}")
        session_blobs[session["path"]] = blob
    try:
        source_blobs = {source["path"]: outputs[source["archive_path"]] for source in manifest["sources"]}
    except KeyError as error:
        raise MigrationError("Missing source archive in planned outputs") from error
    rebuilt, declared_outputs = build_plan(manifest["source_commit"], source_blobs, session_blobs)
    if rebuilt != manifest or declared_outputs != outputs:
        raise MigrationError("Plan differs from deterministic source-derived reconstruction")
    sources = {source["path"]: source for source in manifest["sources"]}
    for path, blob in outputs.items():
        file = _local_path(root, path)
        if file.exists():
            if not file.is_file():
                raise MigrationError(f"Output is not a regular file: {path}")
            existing = file.read_bytes()
            allowed = _canonical_output(path, existing) == blob
            if path in sources:
                allowed = allowed or sha256(existing) == sources[path]["sha256"]
            if not allowed:
                raise MigrationError(f"Refusing to overwrite different existing content: {path}")
        elif path in sources:
            raise MigrationError(f"Original cumulative file is missing: {path}")
    for source in manifest["sources"]:
        for section in source["sections"]:
            for edit in section["link_edits"]:
                target = edit["target_path"]
                if target not in outputs and not _local_path(root, target).exists():
                    raise MigrationError(f"Relative link target is missing before apply: {target}")
    for session in manifest["sessions"]:
        for link in session["relative_links"]:
            target = link["target_path"]
            if target not in outputs and not _local_path(root, target).exists():
                raise MigrationError(f"Old session link target is missing before apply: {target}")
    for path, blob in outputs.items():
        file = _local_path(root, path)
        if file.exists() and _canonical_output(path, file.read_bytes()) == blob:
            continue
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(blob)


def verify_plan(root: Path, manifest: dict) -> dict:
    """Check saved outputs, inverse transformation, complete coverage and old sessions."""
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("manifest_path") != MANIFEST_PATH:
        raise MigrationError("Unsupported migration manifest")
    archives = {}
    sessions = {}
    body_bytes = 0
    links_checked = 0
    for source in manifest["sources"]:
        path = safe_repo_path(source["path"])
        archive = _read_required(root, source["archive_path"])
        if sha256(archive) != source["sha256"] or len(archive) != source["bytes"]:
            raise MigrationError(f"Archive snapshot differs: {path}")
        if parse_headings(archive) != source["headings"]:
            raise MigrationError(f"Archive heading metadata differs: {path}")
        archives[path] = archive
        restored_parts = []
        cursor = 0
        for item in source["sections"]:
            if item["start"] != cursor or item["end"] < cursor or item["end"] > len(archive):
                raise MigrationError(f"Missing, overlapping or out-of-order byte coverage: {path}")
            entry = _read_required(root, item["path"])
            start, end = item["rendered_body_start"], item["rendered_body_end"]
            if not isinstance(start, int) or not isinstance(end, int) or start < len(BODY_START) or end < start:
                raise MigrationError("Invalid rendered body span")
            if entry[start - len(BODY_START):start] != BODY_START or entry[end:] != BODY_END:
                raise MigrationError(f"Entry wrapper/body boundary differs: {item['path']}")
            rendered = entry[start:end]
            if sha256(entry) != item["file_sha256"] or sha256(rendered) != item["rendered_sha256"]:
                raise MigrationError(f"Rendered entry differs: {item['path']}")
            original = restore_body(rendered, item["link_edits"])
            if sha256(original) != item["original_sha256"] or original != archive[item["start"]:item["end"]]:
                raise MigrationError(f"Entry inverse transform differs: {item['path']}")
            restored_parts.append(original)
            body_bytes += len(original)
            cursor = item["end"]
            for edit in item["link_edits"]:
                safe_repo_path(edit["target_path"])
                if not _local_path(root, edit["target_path"]).exists():
                    raise MigrationError(f"Relative link target is missing: {edit['target_path']}")
                resolved = _relative_target(edit["replacement"], item["path"])
                if not resolved or resolved[0] != edit["target_path"] or resolved[2] != edit["fragment"]:
                    raise MigrationError(f"Relative link target changed: {item['path']}")
                links_checked += 1
        restored = b"".join(restored_parts)
        if cursor != len(archive) or restored != archive or _native_references(restored) != source["native_references"]:
            raise MigrationError(f"Original byte stream/native references not fully preserved: {path}")
        root_headings = [(h["level"], h["title"]) for h in parse_headings(_read_required(root, path))]
        original_headings = [(h["level"], h["title"]) for h in source["headings"]]
        if root_headings != original_headings:
            raise MigrationError(f"Compatibility heading/anchor sequence differs: {path}")
    for session in manifest["sessions"]:
        blob = _read_required(root, session["path"])
        if len(blob) != session["bytes"] or sha256(blob) != session["sha256"]:
            raise MigrationError(f"Immutable old session differs: {session['path']}")
        sessions[session["path"]] = blob
        for link in session["relative_links"]:
            if not _local_path(root, link["target_path"]).exists():
                raise MigrationError(f"Old session relative link target is missing: {link['target_path']}")
            links_checked += 1
    rebuilt, expected_outputs = build_plan(manifest["source_commit"], archives, sessions)
    if rebuilt != manifest:
        raise MigrationError("Manifest differs from deterministic source-derived reconstruction")
    for path, expected in expected_outputs.items():
        if _canonical_output(path, _read_required(root, path)) != expected:
            raise MigrationError(f"Generated source-derived output differs: {path}")
    return {
        "source_files": len(archives),
        "sections": manifest["totals"]["sections"],
        "session_files": len(sessions),
        "body_bytes": body_bytes,
        "relative_links": links_checked,
    }


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise MigrationError(f"Local Git read failed ({result.returncode}): {result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout


def _git_sources(root: Path, commit: str) -> tuple[str, dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{8,40}", commit):
        raise MigrationError("Source Git reference must be a lowercase commit SHA (8 to 40 characters)")
    resolved = _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise MigrationError("Git did not resolve a full commit SHA")
    blobs = {path: _git(root, "show", f"{resolved}:{path}") for path in SOURCE_PATHS}
    tree_paths = _git(root, "ls-tree", "-r", "--name-only", "-z", resolved, "--", "docs/작업기록/세션", "docs/작업근거/세션")
    paths = [path.decode("utf-8") for path in tree_paths.split(b"\x00") if path]
    sessions = {path: _git(root, "show", f"{resolved}:{path}") for path in paths if path.endswith(".md")}
    return resolved, blobs, sessions


def verify_git_source(root: Path, manifest: dict) -> None:
    """Bind saved snapshots/session proofs to the actual immutable local Git commit."""
    commit, blobs, sessions = _git_sources(root, manifest["source_commit"])
    if commit != manifest["source_commit"]:
        raise MigrationError("Saved source commit is not the full resolved Git commit")
    source_receipts = {source["path"]: source for source in manifest["sources"]}
    if len(source_receipts) != len(manifest["sources"]) or set(source_receipts) != set(blobs):
        raise MigrationError("Cumulative source list differs from the fixed Git snapshot")
    for path, blob in blobs.items():
        receipt = source_receipts[path]
        if sha256(blob) != receipt["sha256"] or _read_required(root, receipt["archive_path"]) != blob:
            raise MigrationError(f"Archive does not match source Git blob: {path}")
    session_receipts = {session["path"]: session for session in manifest["sessions"]}
    if len(session_receipts) != len(manifest["sessions"]) or set(session_receipts) != set(sessions):
        raise MigrationError("Old session list differs from the fixed Git snapshot")
    for path, blob in sessions.items():
        if sha256(blob) != session_receipts[path]["sha256"] or _read_required(root, path) != blob:
            raise MigrationError(f"Old session does not match source Git blob: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="migrate", choices=("migrate",))
    parser.add_argument("--source-commit", help="Existing local immutable Git source commit")
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write after full byte/path preflight")
    mode.add_argument("--verify", action="store_true", help="Verify the existing saved migration")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            manifest = json.loads(_read_required(args.root, MANIFEST_PATH).decode("utf-8"))
            if args.source_commit and manifest["source_commit"] != _git(args.root, "rev-parse", "--verify", f"{args.source_commit}^{{commit}}").decode("ascii").strip():
                raise MigrationError("Requested source commit differs from saved manifest")
            result = verify_plan(args.root, manifest)
            verify_git_source(args.root, manifest)
            print(json.dumps({"status": "verified", "source_git_verified": True, **result}, ensure_ascii=False))
        else:
            if not args.source_commit:
                parser.error("--source-commit is required for planning/apply")
            commit, blobs, sessions = _git_sources(args.root, args.source_commit)
            manifest, outputs = build_plan(commit, blobs, sessions)
            if args.apply:
                apply_plan(args.root, manifest, outputs)
                result = verify_plan(args.root, manifest)
                verify_git_source(args.root, manifest)
                print(json.dumps({"status": "applied_and_verified", "source_git_verified": True, **result}, ensure_ascii=False))
            else:
                print(json.dumps({"status": "read_only_plan", "source_commit": commit, **manifest["totals"]}, ensure_ascii=False))
    except (MigrationError, OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
