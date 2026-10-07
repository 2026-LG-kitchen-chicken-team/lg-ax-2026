"""Synthetic Git repositories exercise exact source bytes and unsafe archives."""

import io
import json
import stat
import subprocess
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.package_submission import (
    APPROVED_AUTHORIZATION_NOTES,
    GUIDE_PATH,
    MANIFEST_PATH,
    REQUIRED_FILES,
    PackageError,
    _check_content,
    _safe_name,
    _zip_info,
    build,
    digest,
    unpack,
    verify,
)

HISTORICAL_NOTES = (
    ("data/research/P2-DATA-001-stage123-20261005/execution-context.json",
     "269edbbef899f54051575e3e0eabf32b8ced75d07f74c3c529f48c9df3e33761",
     "/authorization", "ba7fcd39b9e84570889239d310a5065c65606dacf24dee875c4f0db6289bfaaf"),
    ("docs/history/project/20261006/manifest.json",
     "26d718fd723f3ebc7e73eb11c7d24f8be6173163bd340c052af0a7636afb5f29",
     "/additional_sources_note/authorization", "8871207a1414b8763e6de9efa89c4ab08c2a999051a16579b8d192d4a96d8896"),
    ("evals/core-manual-quality/20261006/integration-r4-audit/pm-review-correction.json",
     "1c383018fefd37398a3c80cfd8571a6f90fbd42ed5f8c1f841447244dac97d7c",
     "/authorization", "edb349f7d197401fbef340a0e8d47ea067f5e55b0830466b2183d17b708d7a28"),
)


class ApprovedHistoricalAuthorizationTests(unittest.TestCase):
    """Real immutable note bytes, with adversarial copies and same-file mutations."""

    def originals(self):
        for name, file_sha, pointer, value_sha in HISTORICAL_NOTES:
            data = (Path(__file__).resolve().parents[1] / name).read_bytes()
            self.assertEqual(digest(data), file_sha, name)
            yield name, data, pointer, value_sha

    def replace_note(self, data, pointer, value):
        document = json.loads(data)
        parts = pointer.removeprefix("/").split("/")
        parent = document
        for part in parts[:-1]:
            parent = parent[part]
        parent[parts[-1]] = value
        return json.dumps(document, ensure_ascii=False).encode("utf-8")

    def test_exact_three_historical_note_bytes_and_values_pass(self):
        self.assertEqual(APPROVED_AUTHORIZATION_NOTES, frozenset(HISTORICAL_NOTES))
        for name, data, pointer, value_sha in self.originals():
            with self.subTest(name=name):
                value = json.loads(data)
                for part in pointer.removeprefix("/").split("/"):
                    value = value[part]
                self.assertIsInstance(value, str)
                encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.assertEqual(digest(encoded), value_sha)
                before = bytes(data)
                _check_content(name, data)
                self.assertEqual(data, before)

    def test_original_note_copies_other_paths_and_whole_file_changes_are_rejected(self):
        for name, data, _, _ in self.originals():
            with self.subTest(name=name):
                for copy_name, changed in [("copies/" + name, data), (name, data + b" ")]:
                    with self.assertRaisesRegex(PackageError, "Literal credential field"):
                        _check_content(copy_name, changed)

    def test_changed_note_literal_and_extra_nested_credential_are_rejected(self):
        synthetic_token = "Z" * 64
        for name, data, pointer, _ in self.originals():
            with self.subTest(name=name):
                with self.assertRaisesRegex(PackageError, "Literal credential field"):
                    _check_content(name, self.replace_note(data, pointer, synthetic_token))
                document = json.loads(data)
                # Keep the original permission note while adding a separate credential.
                document["nested"] = [{"api_key": synthetic_token}]
                with self.assertRaisesRegex(PackageError, "Literal credential field"):
                    _check_content(name, json.dumps(document, ensure_ascii=False).encode("utf-8"))

    def test_pointer_and_value_sha_must_also_match_the_fixed_note(self):
        # A mistaken future approval cannot rely on only the path and file digest.
        for name, data, pointer, value_sha in self.originals():
            for wrong in [(name, digest(data), pointer + "/other", value_sha),
                          (name, digest(data), pointer, "0" * 64)]:
                with (
                    self.subTest(name=name, wrong_pointer=wrong[2]),
                    patch("scripts.package_submission.APPROVED_AUTHORIZATION_NOTES", frozenset({wrong})),
                    self.assertRaisesRegex(PackageError, "Literal credential field"),
                ):
                    _check_content(name, data)

    def test_secret_patterns_databases_and_personal_identifiers_precede_notes(self):
        for name, data, _, _ in self.originals():
            with self.subTest(name=name):
                for content in [data + b"hf_" + b"z" * 32, b"SQLite format 3\0" + data]:
                    with self.assertRaisesRegex(PackageError, "Credential/database content"):
                        _check_content(name, content)
                for field, value, message in [("student_id", "20999999", "Student identifier"),
                                              ("phone", "010-0000-0000", "Personal mobile")]:
                    document = json.loads(data)
                    document["private_copy"] = [{field: value}]
                    with self.assertRaisesRegex(PackageError, message):
                        _check_content(name, json.dumps(document, ensure_ascii=False).encode("utf-8"))


class SubmissionPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lgax-package-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        # No detached Git maintenance may race TemporaryDirectory cleanup.
        self.git("config", "gc.auto", "0")
        self.git("config", "maintenance.auto", "false")
        self.git("config", "user.name", "Synthetic fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.files = {name: b"synthetic public fixture\n" for name in REQUIRED_FILES}
        rows = [{"id": f"R{number:02}", "status": "pending"} for number in range(1, 29)]
        rows += [{"id": f"E{number:02}", "status": "pending"} for number in range(1, 4)]
        self.files["harness/phase2/requirements.json"] = json.dumps({"requirements": rows}).encode()
        self.files["README.md"] = "실행 README — 합성 시험 자료\n".encode()
        self.files["src/example.py"] = b"print('fixture')\n"
        self.files[".gitignore"] = b"private/\n"
        for name, value in self.files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        self.commit = self.commit_all()
        self.archive = self.repo / "private/source.zip"

    def git(self, *args, input_bytes=None):
        process = subprocess.run(["git", "-C", str(self.repo), *args], input=input_bytes,
                                 capture_output=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        return process.stdout

    def commit_all(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Synthetic fixture snapshot")
        return self.git("rev-parse", "HEAD").decode().strip()

    def dangerous_file(self, name, content=b"synthetic fixture\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.git("add", "-f", "--", name)
        self.git("commit", "-q", "-m", "Synthetic unsafe-path test")
        return self.git("rev-parse", "HEAD").decode().strip()

    def rewrite_archive(self, *, altered=None, extra=None):
        with zipfile.ZipFile(self.archive) as old:
            entries = [(info, old.read(info)) for info in old.infolist()]
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(buffer, "w") as new:
                for info, value in entries:
                    new.writestr(info, altered.get(info.filename, value) if altered else value)
                if extra:
                    for info, value in extra:
                        new.writestr(info, value)
        self.archive.write_bytes(buffer.getvalue())
        # An attacker may also rewrite this sidecar; fixed-commit checks must still fail.
        sidecar = self.archive.with_name(self.archive.name + ".provenance.json")
        provenance = json.loads(sidecar.read_text(encoding="utf-8"))
        provenance["archive_sha256"] = digest(buffer.getvalue())
        sidecar.write_text(json.dumps(provenance), encoding="utf-8")

    def test_every_tracked_file_byte_is_included_and_dirty_untracked_files_are_not(self):
        (self.repo / "README.md").write_bytes(b"dirty worktree must not enter fixed source\n")
        (self.repo / "untracked.txt").write_bytes(b"untracked fixture")
        result = build(self.repo, self.commit, self.archive)
        self.assertTrue(result["draft"])
        self.assertFalse(result["submission_ready"])
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), set(self.files) | {MANIFEST_PATH, GUIDE_PATH})
            for name, value in self.files.items():
                self.assertEqual(archive.read(name), value, name)
            manifest = json.loads(archive.read(MANIFEST_PATH))
            self.assertEqual(manifest["source_commit"], self.commit)
            self.assertEqual(manifest["declared_application_coverage"]["declared_verified"], 0)
            for entry in manifest["files"]:
                self.assertEqual(entry["sha256"], digest(self.files[entry["path"]]))
        self.assertTrue(verify(self.repo, self.archive)["verified"])

    def test_same_commit_has_deterministic_zip_bytes_and_never_overwrites(self):
        first = build(self.repo, self.commit, self.archive)
        second_path = self.repo / "private/source-second.zip"
        second = build(self.repo, self.commit, second_path)
        self.assertEqual(self.archive.read_bytes(), second_path.read_bytes())
        self.assertEqual(first["archive_sha256"], second["archive_sha256"])
        before = self.archive.read_bytes()
        with self.assertRaises(PackageError):
            build(self.repo, self.commit, self.archive)
        self.assertEqual(self.archive.read_bytes(), before)

    def test_private_database_env_and_copied_application_paths_fail_instead_of_omission(self):
        for name in ["private/team.txt", "config/credentials.json", ".env.production", "data/workspace.sqlite3",
                     "copies/20999999_가상팀원.pdf", "copies/LG_AX_4인최종본.pdf", "assets/서명.png"]:
            with self.subTest(name=name):
                commit = self.dangerous_file(name)
                with self.assertRaises(PackageError):
                    build(self.repo, commit, self.archive)
                self.assertFalse(self.archive.exists())
                self.git("reset", "--hard", self.commit)

    def test_tracked_symlink_is_rejected_without_native_windows_symlink_permissions(self):
        oid = self.git("hash-object", "-w", "--stdin", input_bytes=b"README.md").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{oid},src/link")
        self.git("commit", "-q", "-m", "Synthetic symlink fixture")
        commit = self.git("rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(PackageError, "Symlink"):
            build(self.repo, commit, self.archive)

    def test_missing_required_skill_is_rejected(self):
        self.git("rm", "skills/review_revision/SKILL.md")
        commit = self.commit_all()
        with self.assertRaisesRegex(PackageError, "Required source"):
            build(self.repo, commit, self.archive)

    def test_placeholder_env_example_is_allowed_but_literal_value_and_secret_content_fail(self):
        safe = b"# synthetic template\nAPI_KEY=<YOUR_API_KEY>\nLOCAL_TOKEN=\nMODEL=YOUR_MODEL_NAME\n"
        commit = self.dangerous_file(".env.example", safe)
        build(self.repo, commit, self.archive)
        for unsafe in [b"TOKEN=actual-looking-value\n", b"PASSWORD=123456\n", b"export TOKEN=value\n"]:
            with self.assertRaises(PackageError):
                _check_content(".env.example", unsafe)
        # Artificial credentials only, generated by concatenation so source text carries no key.
        for content in [(b"hf_" + b"a" * 32), (b"-----BEGIN " + b"PRIVATE KEY-----\nsynthetic\n"),
                        b"SQLite format 3\0synthetic"]:
            with self.assertRaises(PackageError):
                _check_content("public/copy.txt", content)

    def test_output_archive_and_extract_cannot_escape_private_or_existing_destination(self):
        with self.assertRaises(PackageError):
            build(self.repo, self.commit, self.repo / "outside.zip")
        build(self.repo, self.commit, self.archive)
        for destination in [self.repo / "src", self.repo / "private/../../outside"]:
            with self.assertRaises(PackageError):
                unpack(self.repo, self.archive, destination)
        destination = self.repo / "private/extracted"
        result = unpack(self.repo, self.archive, destination)
        self.assertFalse(result["replay_executed"])
        for name, value in self.files.items():
            self.assertEqual((destination / name).read_bytes(), value)
        with self.assertRaises(PackageError):
            unpack(self.repo, self.archive, destination)

    def test_zip_byte_corruption_is_rejected_by_sidecar(self):
        build(self.repo, self.commit, self.archive)
        original = self.archive.read_bytes()
        self.archive.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(PackageError, "SHA256"):
            verify(self.repo, self.archive)

    def test_source_tampering_even_with_new_archive_hash_is_rejected(self):
        build(self.repo, self.commit, self.archive)
        self.rewrite_archive(altered={"README.md": b"tampered source\n"})
        with self.assertRaisesRegex(PackageError, "source bytes"):
            verify(self.repo, self.archive)

    def test_zip_traversal_duplicate_and_symlink_entries_are_rejected(self):
        for name, mode in [("../escape.txt", stat.S_IFREG), ("README.md", stat.S_IFREG),
                           ("src/symlink", stat.S_IFLNK)]:
            with self.subTest(name=name):
                output = self.repo / "private" / ("malicious-" + str(mode) + "-" + str(len(name)) + ".zip")
                build(self.repo, self.commit, output)
                self.archive = output
                info = _zip_info(name)
                info.external_attr = (mode | 0o644) << 16
                self.rewrite_archive(extra=[(info, b"synthetic malicious entry")])
                with self.assertRaises(PackageError):
                    unpack(self.repo, self.archive, self.repo / "private/never-extracted")
                self.assertFalse((self.repo / "private/never-extracted").exists())

    def test_nonportable_names_and_repository_subdirectories_are_rejected(self):
        for name in ["/absolute", "a/../b", "a\\b", "C:/escape", "a//b", "CON.txt", "trailing."]:
            with self.assertRaises(PackageError):
                _safe_name(name)
        with self.assertRaises(PackageError):
            build(self.repo / "src", self.commit, self.archive)

    def test_actual_client_config_shape_and_recursive_json_secrets_are_rejected(self):
        synthetic_token = "A" * 64
        for name in ["config/editor-client.json", "config/viewer-client.json", "config/admin-client.json",
                     "config/server-credentials.json"]:
            commit = self.dangerous_file(name, json.dumps({"token": synthetic_token}).encode())
            with self.assertRaises(PackageError):
                build(self.repo, commit, self.archive)
            self.git("reset", "--hard", self.commit)
        for field in ["token", "access_token", "bearer", "password", "api_key"]:
            with self.assertRaises(PackageError):
                _check_content("arbitrary/config.json", json.dumps({"nested": [{field: synthetic_token}]}).encode())
        _check_content("safe/example.json", json.dumps({"token": "${TOKEN}", "api_key": "<API_KEY>",
                       "password": "", "properties": {"token": {"type": "string"}}}).encode())
        for field, value in [("student_id", "20999999"), ("phone", "010-0000-0000")]:
            with self.assertRaises(PackageError):
                _check_content("arbitrary/person.json", json.dumps({field: value}).encode())

    def test_git_replace_cannot_change_the_fixed_commit_bytes(self):
        (self.repo / "README.md").write_bytes(b"replacement must not become the original commit\n")
        replacement = self.commit_all()
        self.git("replace", self.commit, replacement)
        result = build(self.repo, self.commit, self.archive)
        self.assertEqual(result["source_commit"], self.commit)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(archive.read("README.md"), self.files["README.md"])
        self.assertTrue(verify(self.repo, self.archive)["verified"])


if __name__ == "__main__":
    unittest.main()
