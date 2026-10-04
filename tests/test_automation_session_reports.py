import unittest

from scripts.project_report_common import source_link

REPO = "2026-LG-kitchen-chicken-team/lg-ax-2026"
PREFIX = f"https://github.com/{REPO}/blob/" + "a" * 40 + "/"


class SessionSourceTests(unittest.TestCase):
    def test_immutable_own_session_and_legacy_both_work(self):
        for path in ("docs/작업기록/신진하.md", "docs/작업기록/세션/신진하/data-01.md"):
            sha, checked = source_link(PREFIX + path, REPO, "신진하", "log")
            self.assertEqual(checked, path)
            self.assertEqual(sha, "a" * 40)

    def test_other_owner_traversal_nested_and_mutable_rejected(self):
        for path in ("docs/작업기록/세션/최길웅/data-01.md", "docs/작업기록/세션/신진하/../x.md",
                     "docs/작업기록/세션/신진하/nested/x.md", "docs/작업근거/세션/신진하/x.md"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                source_link(PREFIX + path, REPO, "신진하", "log")
        with self.assertRaises(ValueError):
            source_link(PREFIX.replace("a" * 40, "main") + "docs/작업기록/신진하.md", REPO, "신진하", "log")
