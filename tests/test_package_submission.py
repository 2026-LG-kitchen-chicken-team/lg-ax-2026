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

from scripts.package_submission import (
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


class SubmissionPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lgax-package-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
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
