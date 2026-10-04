import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from services.automation.artifacts import changes, digest, files, import_checked, secret_check, write_copy


class ArtifactBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exact_checked_bytes_and_deletions(self):
        before = {"docs/a.md": b"old", "docs/deleted.md": b"remove"}
        after = {"docs/a.md": b"new", "docs/new.md": b"new file"}
        target = self.root / "publisher"
        write_copy(before, target)
        actual = import_checked(target, before, after, allow=lambda name: name.startswith("docs/"))
        self.assertEqual(set(actual), set(changes(before, after)))
        self.assertEqual(files(target), after)
        self.assertEqual(digest(files(target)), digest(after))

    def test_no_partial_write_when_later_path_is_denied(self):
        before = {"docs/a.md": b"old"}
        after = {"docs/a.md": b"new", "scripts/evil.py": b"danger"}
        target = self.root / "publisher"
        write_copy(before, target)
        with self.assertRaises(ValueError):
            import_checked(target, before, after, allow=lambda name: name.startswith("docs/"))
        self.assertEqual(files(target), before)

    def test_token_shaped_and_exact_harmless_canary_refused(self):
        for value in (b"github_pat_" + b"X" * 32, b"-----BEGIN PRIVATE KEY-----",
                      b"harmless-canary-secret-123456"):
            with self.assertRaises(ValueError) as caught:
                secret_check(b"prefix " + value, [b"harmless-canary-secret-123456"])
            self.assertNotIn(value.decode(), str(caught.exception))
        secret_check(b"Normal product evidence with no credentials.")

    def test_git_private_env_and_case_collision_refused(self):
        for name in (".git/config", "private/token.txt", "docs/.env.local", "../outside"):
            root = self.root / hashlib.sha256(name.encode()).hexdigest()[:8]
            with self.assertRaises(ValueError):
                write_copy({name: b"fixture"}, root)

    @unittest.skipIf(os.name == "nt", "Windows link creation depends on developer mode")
    def test_link_cannot_be_frozen(self):
        guest = self.root / "guest"
        guest.mkdir()
        target = self.root / "secret"
        target.write_text("private harmless fixture")
        (guest / "evidence.md").symlink_to(target)
        with self.assertRaises(ValueError):
            files(guest)

    def test_modified_test_copy_does_not_match_frozen_source(self):
        source = {"a.py": b"approved source"}
        target = self.root / "validator"
        write_copy(source, target)
        (target / "a.py").write_bytes(b"test rewrote source")
        self.assertNotEqual(digest(source), digest(files(target)))


if __name__ == "__main__":
    unittest.main()
