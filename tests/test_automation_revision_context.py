"""Immutable Git fixtures, not live GitHub/CLI/model or operating receipts."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.automation.pm import PMError
from services.automation.pm_broker import TrustedPMBroker
from services.automation.state import PM, REPO
from services.automation.worker import session_records


class RevisionContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        self.local(["init", "--quiet"])
        self.product = "tests/product.py"
        (self.repo / "tests").mkdir()
        (self.repo / self.product).write_text("def answer():\n    return 1\n", encoding="utf-8")
        self.local(["add", "--all"])
        self.local(["commit", "--quiet", "-m", "fixture baseline"])
        self.base = self.local(["rev-parse", "HEAD"]).decode().strip()
        self.job = "old-scoped-job"
        self.records = session_records({"job_id": self.job}, PM)
        for index, name in enumerate(self.records):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((f"Original intent and evidence {index}\n" * 500), encoding="utf-8")
        (self.repo / self.product).write_text("def answer():\n    return 2\n", encoding="utf-8")
        self.commit_result()
        self.calls = []
        self.github_calls = []
        self.broker = object.__new__(TrustedPMBroker)
        self.broker.policy = {"tasks": {"TASK": {"owner": PM}}, "capabilities": {"CAP": {
            "task_id": "TASK", "allowed_paths": [self.product]}}}
        self.previous = {"job_id": self.job, "base_commit": self.base, "head": self.head, "task_id": "TASK",
                         "capability_id": "CAP", "pr_number": 7, "revision_requested": True,
                         "revision_reason": "Current main moved", "revision_instructions": ["Reconstruct on approved main"]}
        self.broker.state = {"units": {self.job: self.previous}, "budgets": {"unchanged": 12}}
        self.broker._git = self.fixed_git
        self.broker.github = SimpleNamespace(request=self.github_request)
        self.action = {"capability_id": "CAP", "task_id": "TASK", "owner": PM, "allowed_paths": [self.product],
                       "purpose": "Fixed product behavior", "instructions": ["Complete the scoped regression"],
                       "acceptance": ["Exact behavior"], "requirement_ids": ["R01"], "validation_commands": [["python", "-m", "unittest"]],
                       "shared_resources": [], "timeout_seconds": 100, "priority": 1, "max_attempts": 1,
                       "formal_task_dependencies": [], "title": "Regression", "base_commit": "c" * 40,
                       "approved_snapshot_commit": "c" * 40}

    def local(self, args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false",
                               "-c", "commit.gpgsign=false", "-c", "user.name=LGAXfixture",
                               "-c", "user.email=fixture@local", *args], cwd=self.repo,
                              env=self.env, capture_output=True, check=True).stdout

    def commit_result(self):
        self.local(["add", "--all"])
        self.local(["commit", "--quiet", "-m", "fixture result"])
        self.head = self.local(["rev-parse", "HEAD"]).decode().strip()

    def fixed_git(self, args, *, binary=False):
        self.calls.append(args)
        if args[0] == "remote":
            return f"https://github.com/{REPO}.git"
        if args[0] == "fetch":
            return ""  # Fixed commits are generated locally; never authenticate/fetch.
        raw = self.local(args)
        return raw if binary else raw.decode().strip()

    def github_request(self, method, route):
        self.github_calls.append((method, route))
        self.assertEqual((method, route), ("GET", f"repos/{REPO}/pulls/7"))
        return {"state": "open", "draft": False, "user": {"login": PM},
                "head": {"sha": self.head, "repo": {"full_name": REPO}},
                "base": {"sha": "c" * 40, "ref": "main", "repo": {"full_name": REPO}}}

    def context(self):
        return self.broker._revision_context(self.previous, self.action)

    def test_complete_product_u0_retains_edits_and_hashes_both_big_own_records(self):
        before = deepcopy(self.broker.state)
        result = self.context()
        full = self.local(["diff", "--full-index", self.base, self.head, "--"])
        self.assertGreater(len(full), 12000)
        self.assertEqual(result["product_paths"], [self.product])
        expected = self.local(["diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--binary",
                               "--full-index", "--unified=0", self.base, self.head, "--", ":(literal)" + self.product])
        self.assertEqual(result["patch_as_inert_reference"].encode(), expected)
        self.assertEqual(result["product_diff_sha256"], hashlib.sha256(expected).hexdigest())
        for row in result["immutable_session_records"]:
            blob = self.local(["show", self.head + ":" + row["path"]])
            self.assertEqual(row["sha256"], hashlib.sha256(blob).hexdigest())
            self.assertIn("/blob/" + self.head + "/", row["url"])
            self.assertEqual(row["source_head"], self.head)
        self.assertEqual(len(result["immutable_session_records"]), 2)
        self.assertEqual(self.broker.state, before)
        self.assertEqual(len(self.github_calls), 2)

    def test_whole_review_diff_keeps_full_context_and_its_existing_512k_bound(self):
        result = self.broker._fixed_diff(self.base, self.head)
        expected = self.local(["diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--binary",
                               "--full-index", self.base, self.head, "--"])
        self.assertEqual(result, expected)
        self.assertGreater(len(result), 12000)
        with self.assertRaisesRegex(PMError, "bounded review"):
            self.broker._fixed_diff(self.base, self.head, maximum=12000)

    def test_zero_context_preserves_every_added_deleted_line_in_order(self):
        result = self.context()["patch_as_inert_reference"].encode()
        u3 = self.local(["diff", "--full-index", "--unified=3", self.base, self.head, "--", ":(literal)" + self.product])
        def edits(raw):
            return [line for line in raw.splitlines() if line[:1] in (b"+", b"-") and not line.startswith((b"+++", b"---"))]
        self.assertEqual(edits(result), edits(u3))

    def test_product_12000_allowed_and_12001_rejected_without_truncation(self):
        original = self.fixed_git
        for size in (12000, 12001):
            with self.subTest(size=size):
                def controlled(args, size=size, **kwargs):
                    return b"x" * size if "--unified=0" in args else original(args, **kwargs)
                with patch.object(self.broker, "_git", side_effect=controlled):
                    if size == 12000:
                        self.assertEqual(len(self.context()["patch_as_inert_reference"]), size)
                    else:
                        with self.assertRaisesRegex(PMError, "bounded context"):
                            self.context()

    def test_missing_or_other_job_record_is_not_silently_filtered(self):
        raw = self.local(["diff", "--raw", "-z", "--no-renames", "--abbrev=40", self.base, self.head, "--"])
        bad = raw.replace(self.records[0].encode(), self.records[0].replace(self.job, "other-job").encode())
        original = self.fixed_git
        with (patch.object(self.broker, "_git", side_effect=lambda args, **kw: bad if "--raw" in args else original(args, **kw)),
              self.assertRaisesRegex(PMError, "own exact")):
            self.context()
        self.assertFalse(any("--unified=0" in args for args in self.calls))

    def test_outside_product_path_refuses_even_with_valid_own_records(self):
        path = self.repo / "tests/not-approved.py"
        path.write_text("unapproved = True\n", encoding="utf-8")
        self.commit_result()
        self.previous["head"] = self.head
        with self.assertRaisesRegex(PMError, "outside the fixed product"):
            self.context()
        self.assertFalse(any("--unified=0" in args for args in self.calls))

    def test_nonregular_record_or_product_modes_refuse_before_selection(self):
        raw = self.local(["diff", "--raw", "-z", "--no-renames", "--abbrev=40", self.base, self.head, "--"])
        original = self.fixed_git
        for mode in (b"120000", b"160000"):
            with self.subTest(mode=mode):
                changed = raw.replace(b" 100644 ", b" " + mode + b" ", 1)
                with (patch.object(self.broker, "_git", side_effect=lambda args, changed=changed, **kw: changed if "--raw" in args else original(args, **kw)),
                      self.assertRaisesRegex(PMError, "regular-file")):
                    self.context()

    def test_existing_record_modification_is_not_a_new_immutable_record(self):
        raw = self.local(["diff", "--raw", "-z", "--no-renames", "--abbrev=40", self.base, self.head, "--"])
        fields = raw.split(b"\0")
        for i in range(0, len(fields) - 1, 2):
            if fields[i + 1].decode() == self.records[0]:
                detail = fields[i].split()
                detail[0], detail[2], detail[4] = b":100644", detail[3], b"M"
                fields[i] = b" ".join(detail)
        bad = b"\0".join(fields)
        original = self.fixed_git
        with (patch.object(self.broker, "_git", side_effect=lambda args, **kw: bad if "--raw" in args else original(args, **kw)),
              self.assertRaisesRegex(PMError, "new immutable")):
            self.context()

    def test_incomplete_nul_metadata_and_unsafe_path_are_rejected(self):
        raw = self.local(["diff", "--raw", "-z", "--no-renames", "--abbrev=40", self.base, self.head, "--"])
        original = self.fixed_git
        for invalid in (raw[:-1], raw.replace(self.product.encode(), b"../tests/product.py"),
                        raw.replace(self.product.encode(), b":(glob)tests/product.py")):
            with (self.subTest(invalid=invalid[-30:]),
                  patch.object(self.broker, "_git", side_effect=lambda args, invalid=invalid, **kw: invalid if "--raw" in args else original(args, **kw)),
                  self.assertRaises(PMError)):
                self.context()

    def test_binary_product_is_not_a_complete_text_reference(self):
        (self.repo / self.product).write_bytes(b"\0binary\0")
        self.commit_result()
        self.previous["head"] = self.head
        with self.assertRaisesRegex(PMError, "text changes"):
            self.context()

    def test_head_moves_during_collection_has_no_state_mutation(self):
        before = deepcopy(self.broker.state)
        original = self.fixed_git
        def changed(args, **kwargs):
            result = original(args, **kwargs)
            if "--unified=0" in args:
                self.head = "f" * 40
            return result
        with patch.object(self.broker, "_git", side_effect=changed), self.assertRaisesRegex(PMError, "head/ownership changed"):
            self.context()
        self.assertEqual(self.broker.state, before)
        self.assertTrue(all(method == "GET" for method, _ in self.github_calls))

    def test_untrusted_unit_or_wrong_capability_cannot_choose_source(self):
        with self.assertRaisesRegex(PMError, "trusted unit"):
            self.broker._revision_context(deepcopy(self.previous), self.action)
        self.previous["task_id"] = "OTHER"
        with self.assertRaisesRegex(PMError, "trusted unit"):
            self.context()

    def test_fresh_packet_only_allows_new_record_paths_and_keeps_old_hash_references(self):
        assignment, packet, previous = self.broker._prepare_assignment("pm-" + "d" * 40, self.action)
        self.assertIs(previous, self.previous)
        self.assertTrue(all(record not in packet["allowed_paths"] for record in self.records))
        self.assertEqual(packet["allowed_paths"], [self.product] + session_records(packet, PM))
        self.assertIn("immutable_session_records", packet["prompt"])
        self.assertIn("do not apply", packet["prompt"])
        self.assertEqual(assignment["assignment_id"], packet["assignment_id"])

    def test_oversized_combined_prompt_refuses_before_posting(self):
        with (patch.object(self.broker, "_revision_context", return_value={"patch_as_inert_reference": "x" * 16000}),
              self.assertRaisesRegex(PMError, "safe task bounds")):
            self.broker._prepare_assignment("pm-" + "d" * 40, self.action)
        self.assertEqual(self.github_calls, [])


class AssignmentPreflightTests(unittest.TestCase):
    def test_bad_revision_head_scope_or_prompt_cannot_post_save_register_or_consume_state(self):
        from tests import test_automation_pm_broker as fixture_module

        for error in ("head moved", "outside scope"):
            with self.subTest(error=error):
                fixture = fixture_module.BrokerTests()
                fixture.setUp()
                try:
                    fixture.add_unit()
                    prior = fixture.broker.state["units"]["initial-job"]
                    prior.update(revision_requested=True, revision_reason="new base", revision_instructions=["reconstruct"])
                    action, expected = fixture.action("assign")
                    before = deepcopy(fixture.broker.state)
                    fixture.github.calls.clear()
                    fixture.controller.calls.clear()
                    context = {"patch_as_inert_reference": "x" * 16000}
                    kwargs = {"return_value": context} if error == "prompt too large" else {"side_effect": PMError(error)}
                    with patch.object(fixture.broker, "_revision_context", **kwargs), self.assertRaises(PMError):
                        fixture.broker.execute("pm-" + "e" * 40, action, expected)
                    self.assertEqual(fixture.broker.state, before)
                    self.assertFalse(any(call[0] != "GET" for call in fixture.github.calls))
                    self.assertFalse(any(body is not None for _, body in fixture.controller.calls))
                    self.assertFalse((fixture.broker.state_dir / "assignments").exists())
                finally:
                    fixture.tearDown()
