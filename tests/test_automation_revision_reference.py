"""Lossless inert source and pre-intent rejection, without live credentials."""
from __future__ import annotations

import base64
import hashlib
import json
import random
import subprocess
import tempfile
import unittest
import zlib
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts import build_worker_runtime
from services.automation.pm import AutonomousPM, PMError, PMPreparationRejected
from services.automation.revision_reference import (
    ARTIFACT,
    MARKER,
    MAX_COMPRESSED,
    MAX_RAW,
    ReferenceError,
    decode_reference,
    encode_reference,
    stage_reference,
    verify_staged_reference,
)
from tests import test_automation_orchestration as orchestration_fixture
from tests import test_automation_pm_broker as broker_fixture
from tests import test_automation_revision_context as git_fixture


def product_diff():
    # Large nontrivial changes share predictable file syntax; compression must
    # retain every line, including the last one, rather than taking a prefix.
    return (b"diff --git a/tests/product.py b/tests/product.py\n" +
            b"index " + b"a" * 40 + b".." + b"b" * 40 + b" 100644\n" +
            b"--- a/tests/product.py\n+++ b/tests/product.py\n@@ -1,500 +1,500 @@\n" +
            b"".join(f"-old_case_{i:04}: value\n+new_case_{i:04}: verified\n".encode() for i in range(700)))


def context(raw=None):
    raw = raw or product_diff()
    return {"previous_job_id": "auto-prior-job", "previous_pr": 96,
            "previous_base": "a" * 40, "previous_head": "b" * 40,
            "reason": "Independent correction", "instructions": ["Reconstruct on current approved main"],
            "immutable_session_records": [{"path": "docs/record-one.md", "sha256": "c" * 64},
                                          {"path": "docs/record-two.md", "sha256": "d" * 64}],
            "reference_format": "lossless zlib-base64 inert text", "product_paths": ["tests/product.py"],
            "product_diff_sha256": hashlib.sha256(raw).hexdigest(),
            "patch_as_inert_reference": encode_reference(raw)}


def packet(value):
    return "Implement the fixed task. Do not apply the reference patch." + MARKER + json.dumps(value)


class RevisionReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def stage(self, value, *, owner="jeongiryang", allowed=None, text=None):
        return stage_reference(text or packet(value), self.root,
                               allowed or ["tests/product.py"], owner=owner)

    def test_full_large_source_is_hash_checked_and_staged_without_changing_original_packet(self):
        raw = product_diff()
        self.assertGreater(len(raw), 32000)
        encoded = encode_reference(raw)
        self.assertLess(len(base64.b64decode(encoded["data"])), MAX_COMPRESSED)
        self.assertEqual(decode_reference(encoded), raw)
        value = context(raw)
        original = packet(value)
        rendered = self.stage(value)
        self.assertEqual((self.root / ARTIFACT).read_bytes(), raw)
        self.assertEqual(original, packet(value))
        self.assertNotIn(encoded["data"], rendered)
        self.assertIn("/artifacts/" + ARTIFACT, rendered)
        self.assertIn(encoded["sha256"], rendered)
        self.assertIn("Do not apply", rendered)
        self.assertIn(b"+new_case_0699: verified", (self.root / ARTIFACT).read_bytes())
        self.assertEqual(list(self.root.iterdir()), [self.root / ARTIFACT])
        checked = verify_staged_reference(original, self.root)
        self.assertEqual(checked["sha256"], encoded["sha256"])
        self.assertTrue(checked["verified_after_model"])
        (self.root / ARTIFACT).write_bytes(raw + b"+tampered\n")
        with self.assertRaisesRegex(ReferenceError, "changed the trusted"):
            verify_staged_reference(original, self.root)

    def test_plain_existing_jobs_need_no_upgrade_or_side_effects(self):
        self.assertEqual(stage_reference("normal approved request", self.root, ["packages/core/"],
                                         owner="unknownamed"), "normal approved request")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_remote_owner_is_not_allowed_compressed_packets_before_runtime_upgrade(self):
        for owner in ("unknownamed", "ginaginaring", "choigilung"):
            with self.subTest(owner=owner), self.assertRaises(ReferenceError):
                self.stage(context(), owner=owner)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_hash_size_utf8_binary_and_extra_fields_refuse_without_writing(self):
        original = encode_reference(product_diff())
        for update in ({"sha256": "0" * 64}, {"bytes": original["bytes"] - 1}, {"bytes": True},
                       {"data": original["data"] + "?"}, {"extra": "unapproved"}):
            with self.subTest(update=list(update)), self.assertRaises(ReferenceError):
                decode_reference({**original, **update})
        for raw in (b"diff --git x\n\xff", b"diff --git x\nGIT binary patch\n", b"diff --git x\n\x00",
                    b"not a Git patch\n", b"diff --git x\n" + b"x" * MAX_RAW):
            with self.subTest(prefix=raw[:20]), self.assertRaises(ReferenceError):
                encode_reference(raw)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bomb_concatenated_stream_and_incompressible_source_cannot_raise_the_bound(self):
        original = encode_reference(product_diff())
        streams = (zlib.compress(b"diff --git x\n" + b"a" * (MAX_RAW + 1)),
                   base64.b64decode(original["data"]) + zlib.compress(b"second stream"),
                   base64.b64decode(original["data"]) + b"trailing")
        for stream in streams:
            value = {**original, "data": base64.b64encode(stream).decode()}
            with self.subTest(length=len(stream)), self.assertRaises(ReferenceError):
                decode_reference(value)
        rng = random.Random(103)
        raw = b"diff --git x\n" + bytes(rng.choice(range(33, 127)) for _ in range(40000))
        with self.assertRaisesRegex(ReferenceError, "compressed source"):
            encode_reference(raw)

    def test_metadata_scope_marker_and_duplicate_keys_cannot_choose_unapproved_files(self):
        original = context()
        for update in ({"product_paths": ["../tests/product.py"]}, {"product_paths": ["tests/other.py"]},
                       {"product_paths": ["tests/product.py", "tests/product.py"]},
                       {"product_paths": [{}]}, {"product_diff_sha256": "0" * 64},
                       {"previous_head": "main"}, {"immutable_session_records": []}):
            with self.subTest(update=list(update)), self.assertRaises(ReferenceError):
                self.stage({**original, **update})
        duplicate = packet(original).removesuffix("}") + ',"previous_pr":97}'
        for text in (duplicate, packet(original) + MARKER, "x" * 16001 + MARKER):
            with self.subTest(length=len(text)), self.assertRaises(ReferenceError):
                self.stage(original, text=text)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_artifact_is_never_overwritten(self):
        target = self.root / ARTIFACT
        target.write_bytes(b"preserved")
        with self.assertRaises(FileExistsError):
            self.stage(context())
        self.assertEqual(target.read_bytes(), b"preserved")

    def test_worker_runtime_manifest_contains_helper_and_flat_cli_imports(self):
        output = self.root / "fixed-worker"
        result = build_worker_runtime.build(output)
        self.assertEqual(result["dependency_manifest"]["revision_reference.py"],
                         hashlib.sha256((output / "revision_reference.py").read_bytes()).hexdigest())
        # --help does not authenticate, start an engine or change a switch.
        import sys

        completed = subprocess.run([sys.executable, str(output / "worker_entry.py"), "--help"],
                                   capture_output=True, timeout=20, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        self.assertFalse(result["automation_enabled"])


class RevisionBrokerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = broker_fixture.BrokerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.broker = self.fixture.broker
        self.fixture.add_unit()
        self.prior = self.broker.state["units"]["initial-job"]
        self.prior.update(revision_requested=True, revision_reason="Independent correction",
                          revision_instructions=["Reconstruct fixed behavior"])

    def test_known_pre_intent_rejection_is_durable_lookup_safe_and_does_not_create_a_job_or_mail(self):
        action, expected = self.fixture.action("assign")
        self.fixture.github.calls.clear()
        self.fixture.controller.calls.clear()
        before = deepcopy(self.broker.state)
        with patch.object(self.broker, "_revision_context", return_value={"patch_as_inert_reference": "x" * 16000}):
            result = self.broker.execute(broker_fixture.ACTION, action, expected)
        self.assertEqual(result["outcome"], "rejected")
        stored = self.broker.state["actions"][broker_fixture.ACTION]
        self.assertEqual(stored["details"]["reason_code"], "revision_prompt_bound")
        self.assertTrue(stored["details"]["pre_intent"])
        self.assertFalse(stored["details"]["remote_side_effects"])
        self.assertEqual(self.broker.state["budgets"], before["budgets"])
        self.assertEqual(self.broker.state["units"], before["units"])
        self.assertEqual(self.broker.state["held_capabilities"][broker_fixture.CAP]["action_id"], broker_fixture.ACTION)
        self.assertFalse(any(call[0] != "GET" for call in self.fixture.github.calls))
        self.assertFalse(any(body is not None for _, body in self.fixture.controller.calls))
        self.assertFalse((self.broker.state_dir / "assignments").exists())
        self.assertFalse((self.broker.state_dir / "notifications").exists())
        with patch.object(self.broker, "_remote_action", side_effect=AssertionError("cannot replay rejected preparation")):
            self.assertEqual(self.broker.lookup(broker_fixture.ACTION), result)
        self.assertEqual(json.loads((self.broker.state_dir / "broker-state.json").read_text())["actions"],
                         self.broker.state["actions"])

    def test_known_rejection_finishes_journal_reservation_without_resetting_actual_usage(self):
        decision = {"action": "assign", "task_id": broker_fixture.TASK, "capability_id": broker_fixture.CAP,
                    "pr_number": None, "head_commit": None, "reason": "Fixed required unit", "instructions": ["Correct behavior"]}
        pm = AutonomousPM(policy_path=self.broker.config["policy_file"], policy_sha256=self.broker.config["policy_sha256"],
                          journal_path=self.fixture.root / "journal.sqlite3", broker=self.broker,
                          decide=lambda *_: {"decision": decision, "usage": {"input_tokens": 4, "output_tokens": 2}},
                          clock=lambda: 100000)
        with patch.object(self.broker, "_revision_context", side_effect=PMPreparationRejected("revision_product_bound")):
            result = pm.tick()
        self.assertEqual(result["state"], "rejected")
        self.assertEqual(pm.journal.pending(), [])
        with pm.journal.connect() as db:
            daily = pm.journal.budget(db, "day:1970-01-02")
            self.assertEqual(daily["actions"], 1)
            self.assertEqual(daily["model_calls"], 1)
            self.assertEqual(daily["tokens"], 6)
            self.assertEqual(db.execute("SELECT state FROM actions").fetchone()[0], "rejected")
        pm.journal.verify()

    def test_response_loss_or_remote_error_after_intent_is_not_reclassified_as_preparation_rejection(self):
        action, expected = self.fixture.action("assign")
        request = self.fixture.github.request
        def fail_after_intent(method, route, body=None):
            if method == "POST" and route.endswith("/assignees"):
                raise PMError("remote response lost after saved intent")
            return request(method, route, body)
        with (patch.object(self.broker, "_revision_context", return_value={"patch_as_inert_reference": "short inert text"}),
              patch.object(self.fixture.github, "request", side_effect=fail_after_intent), self.assertRaises(PMError)):
            self.broker.execute(broker_fixture.ACTION, action, expected)
        self.assertNotIn("held_capabilities", self.broker.state)
        self.assertEqual(self.broker.state["actions"][broker_fixture.ACTION]["phase"], "intent")
        self.assertTrue(self.fixture.github.comments)
        self.assertFalse((self.broker.state_dir / "assignments").exists())


class RevisionCompressionGitTests(unittest.TestCase):
    setUp = git_fixture.RevisionContextTests.setUp
    local = git_fixture.RevisionContextTests.local
    commit_result = git_fixture.RevisionContextTests.commit_result
    fixed_git = git_fixture.RevisionContextTests.fixed_git
    github_request = git_fixture.RevisionContextTests.github_request
    context = git_fixture.RevisionContextTests.context

    def test_large_complete_product_requires_explicit_pm_opt_in_and_preserves_every_edit(self):
        # Change a real isolated Git product, preserving all original session
        # metadata and fixed head/base validation from the production helper.
        (self.repo / self.product).write_bytes(b"".join(f"verified_case_{i:04} = {i}\n".encode() for i in range(1600)))
        self.commit_result()
        self.previous["head"] = self.head
        expected = self.local(["diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--binary", "--full-index",
                               "--unified=0", self.base, self.head, "--", ":(literal)" + self.product])
        self.assertGreater(len(expected), 12000)
        self.broker.config = {}
        with self.assertRaises(PMPreparationRejected):
            self.context()
        self.broker.config["allow_lossless_revision_reference"] = True
        value = self.context()
        self.assertEqual(decode_reference(value["patch_as_inert_reference"]), expected)
        self.assertEqual(value["product_diff_sha256"], hashlib.sha256(expected).hexdigest())
        _, job, _ = self.broker._prepare_assignment("pm-" + "d" * 40, self.action)
        self.assertLessEqual(len(job["prompt"]), 16000)
        self.assertIn(MARKER, job["prompt"])
        stage = self.repo / "outside-product-stage"
        stage.mkdir()
        stage_reference(job["prompt"], stage, job["allowed_paths"], owner="jeongiryang")
        self.assertEqual((stage / ARTIFACT).read_bytes(), expected)
        self.assertEqual(self.broker.state["budgets"], {"unchanged": 12})

    def test_lossless_flag_does_not_allow_other_owner_or_outside_scope(self):
        original = self.fixed_git
        self.broker.config = {"allow_lossless_revision_reference": True}
        controlled = lambda args, **kwargs: product_diff() if "--unified=0" in args else original(args, **kwargs)
        with patch.object(self.broker, "_git", side_effect=controlled):
            self.assertEqual(decode_reference(self.context()["patch_as_inert_reference"]), product_diff())
        # Generate another authorized member's own immutable records in a
        # separate real Git result; a valid normal owner remains disallowed for
        # compressed transport until that worker runtime is explicitly updated.
        for record in self.records:
            (self.repo / record).unlink()
        from services.automation.worker import session_records

        self.records = session_records({"job_id": self.job}, "unknownamed")
        for record in self.records:
            file = self.repo / record
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("actual other owner session fixture", encoding="utf-8")
        self.commit_result()
        self.previous["head"] = self.head
        self.broker.policy["tasks"]["TASK"]["owner"] = "unknownamed"
        self.action["owner"] = "unknownamed"
        getter = self.github_request
        def owner(method, route):
            result = getter(method, route)
            result["user"]["login"] = "unknownamed"
            return result
        self.broker.github.request = owner
        with (patch.object(self.broker, "_git", side_effect=controlled),
              self.assertRaises(PMPreparationRejected)):
            self.context()


class HeldCapabilityTests(unittest.TestCase):
    setUp = orchestration_fixture.OrchestrationLifecycleTests.setUp

    def test_one_preparation_hold_does_not_globally_halt_other_released_ready_tasks_or_complete_parent(self):
        cap = orchestration_fixture.FIRST
        self.broker.state["held_capabilities"] = {cap: {"reason_code": "revision_product_bound", "action_id": "pm-" + "e" * 40}}
        self.live.synchronize(self.observation)
        self.assertNotIn(cap, self.observation["capabilities_ready"])
        self.assertTrue(self.observation["capabilities_ready"])
        self.assertEqual(self.observation["backlog"]["waiting"][cap],
                         "fixed_assignment_preparation_rejected_requires_PM_followup")
        self.assertEqual(self.observation["formal_snapshot"]["tasks"]["P2-CORE-002"]["status"], "ready")
        self.live.synchronize(self.observation, collect=False)
        self.assertNotIn(cap, self.observation["capabilities_ready"])

