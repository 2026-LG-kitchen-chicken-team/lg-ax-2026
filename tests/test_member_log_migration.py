"""Byte-preserving member-log migration checks using only synthetic fixtures.

These tests never read or apply the repository's real member records.  Every
filesystem operation is confined to a TemporaryDirectory.
"""

from __future__ import annotations

import copy
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import migrate_member_logs as migration


OWNERS = ("정이량", "황대겸", "신진하", "최길웅")
SOURCE_PATHS = tuple(
    f"docs/{kind}/{owner}.md"
    for kind in ("작업기록", "작업근거")
    for owner in OWNERS
)
COMMIT = "0123456789abcdef0123456789abcdef01234567"
SESSION_PATH = "docs/작업기록/세션/정이량/auto-fixture.md"


def fixture_sources() -> dict[str, bytes]:
    """All eight required sources, with linked evidence and duplicate IDs."""
    result = {}
    for kind in ("작업기록", "작업근거"):
        for owner in OWNERS:
            other_kind = "작업근거" if kind == "작업기록" else "작업기록"
            identifier = (
                f"{owner}-20261006-FIXTURE"
                if kind == "작업기록"
                else f"{owner}-E20261006-FIXTURE"
            )
            text = (
                f"# {owner} {kind}\r\n\r\n"
                "## 현재 재개 위치\r\n"
                "본문 날짜 2026-10-06은 이 구역의 날짜 근거가 아니다.\r\n"
                "### 일반 설명\r\n"
                "이 설명은 재개 구역 안에 유지한다.\r\n"
                f"[관련 기록](../{other_kind}/{owner}.md#현재-재개-위치)\r\n"
                f"### {identifier} — 같은 제목과 ID\r\n"
                f"첫 번째 고유 본문 {owner} {kind}\r\n"
                f"[대조](../{other_kind}/{owner}.md)\r\n"
                f"### {identifier} — 같은 제목과 ID\r\n"
                f"두 번째 고유 본문 {owner} {kind}\r\n"
                "```markdown\r\n"
                f"### {owner}-20260101-CODE-ONLY\r\n"
                "```\r\n"
                "## 날짜 없는 과거 묶음\r\n"
                "### 일반 소제목\r\n"
                "완료 여부를 새로 판단하지 않는다.\r\n"
            )
            result[f"docs/{kind}/{owner}.md"] = text.encode("utf-8")
    return result


def write_files(root: Path, files: dict[str, bytes]) -> None:
    for relative_path, blob in files.items():
        path = root.joinpath(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def nested_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nested_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_dicts(child)


class HeadingAndSectionTests(unittest.TestCase):
    def test_heading_offsets_count_utf8_bytes_bom_and_crlf_lines(self):
        blob = (
            "\ufeff# 한글 제목\r\n"
            "한글 본문\r\n"
            "## 현재 재개 위치\r\n"
            "### 정이량-20261006-OFFSET — 한글\r\n"
            "#### 내부 소제목\r\n"
        ).encode("utf-8")
        headings = migration.parse_headings(blob)
        expected = [
            ("# 한글 제목", 1, 1, "한글 제목"),
            ("## 현재 재개 위치", 3, 2, "현재 재개 위치"),
            ("### 정이량-20261006-OFFSET — 한글", 4, 3,
             "정이량-20261006-OFFSET — 한글"),
            ("#### 내부 소제목", 5, 4, "내부 소제목"),
        ]
        self.assertEqual(len(headings), len(expected))
        for heading, (text, line, level, title) in zip(headings, expected):
            # Offsets identify physical line starts; the first line includes BOM.
            expected_offset = 0 if line == 1 else blob.index(text.encode("utf-8"))
            self.assertEqual(heading["offset"], expected_offset)
            self.assertEqual(heading["line"], line)
            self.assertEqual(heading["level"], level)
            self.assertEqual(heading["title"], title)

    def test_backtick_and_tilde_fences_hide_apparent_headings(self):
        blob = (
            "## 실제 시작\n"
            "```markdown\n"
            "## 가짜 H2\n"
            "### 정이량-20260101-FAKE\n"
            "```\n"
            "~~~text\n"
            "## 또 다른 가짜\n"
            "~~~\n"
            "## 실제 끝\n"
        ).encode("utf-8")
        self.assertEqual(
            [heading["title"] for heading in migration.parse_headings(blob)],
            ["실제 시작", "실제 끝"],
        )

    def test_every_byte_is_partitioned_without_splitting_generic_h3(self):
        blob = fixture_sources()["docs/작업기록/정이량.md"]
        sections = migration.split_sections(blob, "정이량")
        self.assertEqual(sections[0]["start"], 0)
        self.assertEqual(sections[-1]["end"], len(blob))
        for left, right in zip(sections, sections[1:]):
            self.assertEqual(left["end"], right["start"])
        self.assertTrue(all(part["start"] < part["end"] for part in sections))
        self.assertEqual(
            b"".join(blob[part["start"]:part["end"]] for part in sections), blob
        )
        titles = [part["title"] for part in sections]
        self.assertIn("현재 재개 위치", titles)
        self.assertNotIn("일반 설명", titles)
        self.assertNotIn("일반 소제목", titles)
        self.assertFalse(any("CODE-ONLY" in title for title in titles))
        resume = next(part for part in sections if part["title"] == "현재 재개 위치")
        self.assertIn("### 일반 설명".encode(), blob[resume["start"]:resume["end"]])

    def test_duplicate_record_ids_remain_separate_and_in_order(self):
        blob = fixture_sources()["docs/작업기록/정이량.md"]
        sections = migration.split_sections(blob, "정이량")
        duplicates = [
            part for part in sections
            if "정이량-20261006-FIXTURE" in part["record_ids"]
        ]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(duplicates[0]["title"], duplicates[1]["title"])
        self.assertLess(duplicates[0]["ordinal"], duplicates[1]["ordinal"])
        self.assertLess(duplicates[0]["start"], duplicates[1]["start"])
        self.assertIn("첫 번째 고유 본문".encode(),
                      blob[duplicates[0]["start"]:duplicates[0]["end"]])
        self.assertIn("두 번째 고유 본문".encode(),
                      blob[duplicates[1]["start"]:duplicates[1]["end"]])

    def test_only_explicit_owner_h3_records_start_sections(self):
        blob = (
            "## 묶음\n"
            "### 황대겸-20261006-OTHER\n"
            "다른 담당 기록\n"
            "### P2-PM003 일반 작업 ID\n"
            "### 설명 정이량-20261006-NOT-PREFIX\n"
            "### 정이량-IDENTITY-FIXTURE\n"
            "신원 확인 기록\n"
            "### 정이량-E20261005-EVIDENCE\n"
            "근거 본문\n"
        ).encode("utf-8")
        sections = migration.split_sections(blob, "정이량")
        actual = [part["title"] for part in sections if part["level"] == 3]
        self.assertEqual(actual, ["정이량-IDENTITY-FIXTURE",
                                  "정이량-E20261005-EVIDENCE"])

    def test_dates_come_only_from_dated_heading_ids(self):
        blob = (
            "## 2026-10-06 재개 요약\n"
            "본문 정이량-20261004-BODY 날짜를 사용하지 않는다.\n"
            "### 정이량-IDENTITY-FIXTURE\n"
            "확인일: 2026-10-06\n"
            "### 정이량-20261005-DATED\n"
            "본문의 2026-10-07과 구분한다.\n"
            "### 정이량-E20261004-DATED\n"
            "근거 기록\n"
        ).encode("utf-8")
        sections = migration.split_sections(blob, "정이량")
        by_title = {part["title"]: part for part in sections}
        for title in ("2026-10-06 재개 요약", "정이량-IDENTITY-FIXTURE"):
            self.assertEqual(by_title[title]["date"], "legacy")
            self.assertNotIn("body", str(by_title[title]["date_basis"]).lower())
        self.assertEqual(by_title["정이량-20261005-DATED"]["date"].replace("-", ""),
                         "20261005")
        self.assertEqual(by_title["정이량-E20261004-DATED"]["date"].replace("-", ""),
                         "20261004")


class LinkAndPathTests(unittest.TestCase):
    def test_unicode_relative_link_offsets_and_exact_inverse(self):
        blob = (
            "\ufeff한글 앞문단\r\n"
            "[근거](../작업근거/정이량.md#확인)\r\n"
            "![이미지](../../기획/시각자료/개요.png)\r\n"
        ).encode("utf-8")
        rendered, edits = migration.rewrite_links(
            blob, "docs/작업기록/정이량.md",
            "docs/작업기록/정이량/2026-10-06/record.md",
        )
        self.assertIn("../../../작업근거/정이량.md#확인".encode(), rendered)
        self.assertIn("../../../../기획/시각자료/개요.png".encode(), rendered)
        self.assertEqual(len(edits), 2)
        for edit in edits:
            self.assertEqual(blob[edit["source_start"]:edit["source_end"]],
                             edit["original"].encode("utf-8"))
            self.assertEqual(rendered[edit["rendered_start"]:edit["rendered_end"]],
                             edit["replacement"].encode("utf-8"))
        self.assertEqual(migration.restore_body(rendered, edits), blob)

    def test_external_urls_and_code_references_are_unchanged(self):
        blob = (
            "[웹](https://example.invalid/a?q=한글#끝)\n"
            "[메일](mailto:test@example.invalid)\n"
            "[앱](codex://review?pr=fixture)\n"
            "[루트](/absolute/reference.md)\n"
            "[앵커](#현재-요약)\n"
            "`[코드](../작업근거/정이량.md)`\n"
            "경로 `C:\\Users\\fixture\\기록.md`\n"
            "```markdown\n"
            "[예시](../작업근거/정이량.md)\n"
            "```\n"
        ).encode("utf-8")
        rendered, edits = migration.rewrite_links(
            blob, "docs/작업기록/정이량.md", "docs/작업기록/정이량/legacy/one.md"
        )
        self.assertEqual(rendered, blob)
        self.assertEqual(edits, [])

    def test_link_target_internal_dot_segments_normalize_without_escaping(self):
        blob = "[정상](./../작업근거/정이량.md)\n".encode()
        rendered, edits = migration.rewrite_links(
            blob, "docs/작업기록/정이량.md", "docs/작업기록/정이량/legacy/one.md"
        )
        self.assertIn("../../../작업근거/정이량.md".encode(), rendered)
        self.assertEqual(migration.restore_body(rendered, edits), blob)

    def test_escaped_markdown_link_literal_is_unchanged(self):
        blob = "한글 \\[문법 예시](../작업근거/정이량.md)\r\n".encode()
        rendered, edits = migration.rewrite_links(
            blob, "docs/작업기록/정이량.md", "docs/작업기록/정이량/legacy/one.md"
        )
        self.assertEqual(rendered, blob)
        self.assertEqual(edits, [])

    def test_manifest_paths_reject_traversal_and_absolute_forms(self):
        invalid = (
            "/absolute.md", "\\absolute.md", "C:/fixture.md", "C:\\fixture.md",
            "../escape.md", "docs/../escape.md", "./docs/file.md", "docs/./file.md",
            "docs//file.md", "", "docs\\..\\escape.md",
        )
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises(migration.MigrationError):
                    migration.safe_repo_path(path)
        self.assertEqual(migration.safe_repo_path("docs/작업기록/정이량.md"),
                         "docs/작업기록/정이량.md")

    def test_restore_rejects_tampered_replacement_bytes(self):
        blob = "[근거](../작업근거/정이량.md)\n".encode()
        rendered, edits = migration.rewrite_links(
            blob, "docs/작업기록/정이량.md", "docs/작업기록/정이량/legacy/one.md"
        )
        tampered = rendered.replace("정이량.md".encode(), "황대겸.md".encode())
        with self.assertRaises(migration.MigrationError):
            migration.restore_body(tampered, edits)


class PlanAndVerificationTests(unittest.TestCase):
    def setUp(self):
        self.sources = fixture_sources()
        self.sessions = {SESSION_PATH: "# 기존 세션\n원문 세션 보존\n".encode()}
        self.manifest, self.outputs = migration.build_plan(
            COMMIT, self.sources, self.sessions
        )

    def make_root(self, root: Path) -> None:
        write_files(root, self.sources)
        write_files(root, self.sessions)

    def test_plan_is_deterministic_and_preserves_all_duplicate_payloads(self):
        self.assertEqual(tuple(migration.SOURCE_PATHS), SOURCE_PATHS)
        manifest, outputs = migration.build_plan(COMMIT, self.sources, self.sessions)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(outputs, self.outputs)
        self.assertIn(COMMIT, str(manifest))
        self.assertEqual(len(outputs), len(set(outputs)))
        for source, blob in self.sources.items():
            self.assertIn(source, outputs)
            self.assertNotEqual(outputs[source], blob)
            owner = Path(source).stem
            kind = source.split("/")[1]
            for marker in (f"첫 번째 고유 본문 {owner} {kind}",
                           f"두 번째 고유 본문 {owner} {kind}"):
                self.assertTrue(any(marker.encode() in data for data in outputs.values()))

    def test_compatibility_indexes_have_one_final_lf(self):
        for source_path in SOURCE_PATHS:
            with self.subTest(source=source_path):
                index = self.outputs[source_path]
                self.assertTrue(index.endswith(b"\n"))
                self.assertFalse(index.endswith(b"\n\n"))
                source_headings = migration.parse_headings(self.sources[source_path])
                index_headings = migration.parse_headings(index)
                self.assertEqual(
                    [(heading["level"], heading["title"]) for heading in source_headings],
                    [(heading["level"], heading["title"]) for heading in index_headings],
                )

    def test_missing_standard_source_is_rejected(self):
        incomplete = dict(self.sources)
        incomplete.pop(SOURCE_PATHS[-1])
        with self.assertRaises(migration.MigrationError):
            migration.build_plan(COMMIT, incomplete, {})

    def test_apply_and_verify_then_apply_again_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            result = migration.verify_plan(root, self.manifest)
            self.assertEqual(result["source_files"], 8)
            self.assertEqual(result["session_files"], 1)
            self.assertGreater(result["sections"], 8)
            self.assertEqual(result["body_bytes"], sum(map(len, self.sources.values())))
            self.assertGreater(result["relative_links"], 0)
            after_first = snapshot(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            self.assertEqual(snapshot(root), after_first)
            self.assertEqual(migration.verify_plan(root, self.manifest), result)

    def test_owner_readme_update_block_survives_verify_and_idempotent_apply(self):
        readme_path = "docs/작업기록/정이량/README.md"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            expected_totals = migration.verify_plan(root, self.manifest)
            owner_update = (
                migration.OWNER_UPDATE_START
                + "## 담당자 수동 재개 요약\n검수 대기. 완료를 새로 주장하지 않는다.\n".encode()
                + migration.OWNER_UPDATE_END
            )
            readme = root.joinpath(*readme_path.split("/"))
            readme.write_bytes(readme.read_bytes() + owner_update)
            after_owner_update = snapshot(root)
            self.assertEqual(migration.verify_plan(root, self.manifest), expected_totals)
            migration.apply_plan(root, self.manifest, self.outputs)
            self.assertEqual(snapshot(root), after_owner_update)
            self.assertTrue(readme.read_bytes().endswith(owner_update))

    def test_changed_cumulative_input_aborts_before_any_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            source = SOURCE_PATHS[0]
            root.joinpath(*source.split("/")).write_bytes(self.sources[source] + b"changed")
            before = snapshot(root)
            with self.assertRaises(migration.MigrationError):
                migration.apply_plan(root, self.manifest, self.outputs)
            self.assertEqual(snapshot(root), before)

    def test_preexisting_conflicting_output_aborts_before_any_writes(self):
        output_path = next(path for path in self.outputs if path not in self.sources)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            write_files(root, {output_path: b"preexisting different bytes"})
            before = snapshot(root)
            with self.assertRaises(migration.MigrationError):
                migration.apply_plan(root, self.manifest, self.outputs)
            self.assertEqual(snapshot(root), before)

    def test_extra_or_escaping_output_is_rejected_before_any_writes(self):
        for extra_path in ("docs/unmanifested.md", "../escape.md"):
            with self.subTest(path=extra_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_root(root)
                malicious_outputs = dict(self.outputs)
                malicious_outputs[extra_path] = b"unexpected"
                before = snapshot(root)
                with self.assertRaises(migration.MigrationError):
                    migration.apply_plan(root, self.manifest, malicious_outputs)
                self.assertEqual(snapshot(root), before)

    def test_missing_planned_output_is_rejected_before_any_writes(self):
        incomplete_outputs = dict(self.outputs)
        incomplete_outputs.pop(next(path for path in self.outputs if path not in self.sources))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            before = snapshot(root)
            with self.assertRaises(migration.MigrationError):
                migration.apply_plan(root, self.manifest, incomplete_outputs)
            self.assertEqual(snapshot(root), before)

    def test_changed_declared_output_bytes_are_rejected_before_any_writes(self):
        changed_outputs = dict(self.outputs)
        output_path = next(path for path in self.outputs if path not in self.sources)
        changed_outputs[output_path] += b"\nchanged planned bytes\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            before = snapshot(root)
            with self.assertRaises(migration.MigrationError):
                migration.apply_plan(root, self.manifest, changed_outputs)
            self.assertEqual(snapshot(root), before)

    def test_changed_session_aborts_before_any_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            root.joinpath(*SESSION_PATH.split("/")).write_bytes(b"changed session")
            before = snapshot(root)
            with self.assertRaises(migration.MigrationError):
                migration.apply_plan(root, self.manifest, self.outputs)
            self.assertEqual(snapshot(root), before)

    def test_verify_detects_archive_body_rootindex_readme_and_session_tampering(self):
        source = SOURCE_PATHS[0]
        archive_path = next(
            path for path, data in self.outputs.items()
            if path != source and data == self.sources[source]
        )
        marker = "첫 번째 고유 본문 정이량 작업기록".encode()
        body_path = next(
            path for path, data in self.outputs.items()
            if path != archive_path and path != source and marker in data
            and "두 번째 고유 본문 정이량 작업기록".encode() not in data
        )
        readme_path = next(path for path in self.outputs if path.endswith("/README.md"))
        for tamper_path in (archive_path, body_path, source, readme_path, SESSION_PATH):
            with self.subTest(path=tamper_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_root(root)
                migration.apply_plan(root, self.manifest, self.outputs)
                path = root.joinpath(*tamper_path.split("/"))
                path.write_bytes(path.read_bytes() + b"\nTAMPER\n")
                with self.assertRaises(migration.MigrationError):
                    migration.verify_plan(root, self.manifest)

    def test_verify_rejects_tampered_link_inverse_metadata(self):
        tampered = copy.deepcopy(self.manifest)
        edit = next(
            entry for entry in nested_dicts(tampered)
            if {"source_start", "source_end", "rendered_start", "rendered_end"}
            <= entry.keys()
        )
        edit["rendered_start"] += 1
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            with self.assertRaises(migration.MigrationError):
                migration.verify_plan(root, tampered)

    def test_verify_rejects_a_gap_in_manifest_byte_coverage(self):
        tampered = copy.deepcopy(self.manifest)
        source = tampered["sources"][0]
        self.assertGreater(len(source["sections"]), 1)
        source["sections"][1]["start"] += 1
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            with self.assertRaises(migration.MigrationError):
                migration.verify_plan(root, tampered)

    def test_cli_verify_binds_to_mocked_immutable_git_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            with patch.object(migration, "_git_sources",
                              return_value=(COMMIT, self.sources, self.sessions)) as git_sources:
                migration.verify_git_source(root, self.manifest)
                git_sources.assert_called_once_with(root, COMMIT)
            with patch.object(migration, "_git_sources",
                              return_value=(COMMIT, self.sources, self.sessions)) as git_sources:
                with contextlib.redirect_stdout(io.StringIO()):
                    status = migration.main(["--root", str(root), "--verify"])
                self.assertEqual(status, 0)
                git_sources.assert_called_once_with(root, COMMIT)

    def test_git_proof_rejects_source_blob_mismatch_without_real_git(self):
        changed_sources = dict(self.sources)
        changed_sources[SOURCE_PATHS[0]] += b"changed fixed snapshot"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root)
            migration.apply_plan(root, self.manifest, self.outputs)
            before = snapshot(root)
            with patch.object(migration, "_git_sources",
                              return_value=(COMMIT, changed_sources, self.sessions)):
                with self.assertRaises(migration.MigrationError):
                    migration.verify_git_source(root, self.manifest)
            self.assertEqual(snapshot(root), before)

    def test_git_proof_rejects_changed_session_inventory_without_real_git(self):
        missing_receipt = copy.deepcopy(self.manifest)
        missing_receipt["sessions"] = []
        extra_session = dict(self.sessions)
        extra_session["docs/작업근거/세션/정이량/unrecorded-fixture.md"] = b"unrecorded"
        cases = ((missing_receipt, self.sessions), (self.manifest, {}),
                 (self.manifest, extra_session))
        for manifest, git_sessions in cases:
            with self.subTest(session_count=len(git_sessions)), \
                    tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_root(root)
                migration.apply_plan(root, self.manifest, self.outputs)
                before = snapshot(root)
                with patch.object(migration, "_git_sources",
                                  return_value=(COMMIT, self.sources, git_sessions)):
                    with self.assertRaises(migration.MigrationError):
                        migration.verify_git_source(root, manifest)
                self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
