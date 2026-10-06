"""Static, standard-library-only checks for the 2026-10-06 document migration.

This command does not import repository application code, run tests/models,
contact services, or change files. --check-protected is a one-time migration
audit; omit it after legitimate new member records or owner summaries change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


MANIFEST = "docs/history/project/20261006/manifest.json"
START = "<!-- document-navigation:legacy-anchors:start -->"
END = "<!-- document-navigation:legacy-anchors:end -->"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def headings(text: str) -> list[str]:
    found: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)[0]
            fence = None if fence == marker else (marker if fence is None else fence)
            continue
        if fence is None and re.match(r"^#{1,6} ", line):
            found.append(line)
    return found


def inside(root: Path, relative: str) -> Path:
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path escapes repository: {relative}")
    return resolved


def check(root: Path, check_protected: bool = False, check_source_git: bool = False) -> dict[str, object]:
    manifest = json.loads(inside(root, MANIFEST).read_text(encoding="utf-8"))
    errors: list[str] = []
    archives = manifest["sources"]
    checked_links = 0
    for source in archives:
        original = source["original_path"]
        archive = inside(root, source["archive_path"])
        if not archive.is_file():
            errors.append(f"Missing original-byte archive: {original}")
            continue
        raw = archive.read_bytes()
        if len(raw) != source["body_bytes"] or sha256(raw) != source["sha256"]:
            errors.append(f"Original bytes/hash changed: {original}")
            continue
        git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if git_blob != source["source_git_blob"]:
            errors.append(f"Archive cannot reproduce source Git blob: {original}")
        if check_source_git:
            original_blob = subprocess.run(
                ["git", "-C", str(root), "show", f"{manifest['source_commit']}:{original}"],
                check=True, capture_output=True,
            ).stdout
            if original_blob != raw:
                errors.append(f"Archive differs from pinned original commit: {original}")
        source_headings = headings(raw.decode("utf-8-sig"))
        if source_headings != source["headings"]:
            errors.append(f"Original heading order changed: {original}")
        entry = inside(root, original).read_text(encoding="utf-8-sig")
        if entry.count(START) != 1 or entry.count(END) != 1:
            errors.append(f"Missing/duplicated compatibility markers: {original}")
            continue
        compatibility = entry.split(START, 1)[1].split(END, 1)[0]
        if headings(compatibility) != source_headings:
            errors.append(f"Original headings/duplicate-anchor order lost: {original}")
        for section in source["sections"]:
            target = section["compatibility_link"]
            if f"]({target})" not in compatibility:
                errors.append(f"Missing source-section backlink: {original}:{section['line']}")
            if section["current_entry_link"] not in inside(root, manifest["link_index"]).read_text(encoding="utf-8"):
                errors.append(f"Missing reverse link to compatibility anchor: {original}:{section['line']}")
        if any(heading in headings(entry.split(START, 1)[0]) for heading in source_headings):
            errors.append(f"Current entrance collides with an old heading: {original}")
        for link in source["local_markdown_links"]:
            # Resolve immutable-source links against the original source directory,
            # never against the physical archive directory. Historical absence is
            # recorded, not repaired by inventing a source.
            target = inside(root, link["resolved_path"])
            expected_exists = link["existed_at_source"]
            if expected_exists and not target.exists():
                errors.append(f"Source target became unavailable: {original}:{link['line']}")
            if link["navigation_link"] not in inside(root, manifest["link_index"]).read_text(encoding="utf-8"):
                errors.append(f"Missing source-relative navigation entry: {original}:{link['line']}")
            checked_links += 1

    # Check the small set of new live entrances, including fragments. Original
    # source snapshots have their own source-base map and are not rewritten.
    for entry_path in manifest["current_entries"]:
        entry = inside(root, entry_path)
        text = entry.read_text(encoding="utf-8-sig")
        for match in re.finditer(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)", text):
            target = match.group(1).strip().strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            path_part, _, fragment = target.partition("#")
            resolved = (entry.parent / unquote(path_part)).resolve() if path_part else entry
            if not resolved.is_relative_to(root) or not resolved.is_file():
                errors.append(f"Missing live navigation target: {entry_path}: {target}")
                continue
            if fragment and resolved.suffix == ".md":
                target_text = resolved.read_text(encoding="utf-8-sig")
                explicit = f'<a id="{unquote(fragment)}"></a>'
                # Migration sections have explicit IDs; unrelated existing docs
                # are linked without fragments from these new entrances.
                if explicit not in target_text and target not in manifest["source_section_targets"]:
                    errors.append(f"Unresolved migration fragment: {entry_path}: {target}")

    protected_checked = 0
    if check_protected:
        for item in manifest["protected_at_migration"]:
            path = inside(root, item["path"])
            if not path.is_file() or sha256(path.read_bytes()) != item["sha256"]:
                errors.append(f"Protected source changed during migration: {item['path']}")
            protected_checked += 1
    if errors:
        raise ValueError("\n".join(errors))
    return {
        "source_commit": manifest["source_commit"],
        "original_byte_archives": len(archives),
        "original_bytes_preserved": sum(item["body_bytes"] for item in archives),
        "original_headings_preserved": sum(len(item["headings"]) for item in archives),
        "source_relative_links_checked": checked_links,
        "current_entries_checked": len(manifest["current_entries"]),
        "protected_files_checked": protected_checked,
        "pinned_git_source_checked": check_source_git,
        "product_execution": False,
        "network_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-protected", action="store_true")
    parser.add_argument("--check-source-git", action="store_true", help="Read pinned local Git blobs; no network or working-tree mutation")
    args = parser.parse_args()
    try:
        result = check(args.root.resolve(), args.check_protected, args.check_source_git)
    except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
