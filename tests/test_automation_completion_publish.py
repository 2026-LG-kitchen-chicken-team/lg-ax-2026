"""Metadata publication regressions. No live credentials, model or API writes."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.automation.completion import ArtifactRef, CompletionError, digest
from services.automation.completion_publish import CompletionPublisher
from services.automation.pm import Journal, PMError, canonical
from tests import test_automation_completion as fixture


class FakeStore:
    def __init__(self, root):
        self.root = root
        self.f = fixture.Fixture()
        self.receipt = self.f.assessment().receipt
        receipt_ref = self.f.put(self.receipt.raw)
        self.registry = self.f.registry
        self.index = {}
        self.admissions = []
        self.save = Mock()
        bundle = {"schema_version": 1, "protocol": "trusted_auto_parent_v1", "task_id": fixture.TASK,
            "source_commit": fixture.BASE, "tested_commit": fixture.MAIN,
            "sources": {"requirements": self.f.requirements_ref.as_dict(), "task": self.f.task_ref.as_dict(),
                        "policy": self.f.policy_ref.as_dict()},
            "accepted_units": [{k: getattr(self.f.unit, k).as_dict() for k in ("acceptance", "review", "merge", "postmerge")}],
            "requirements": [{"requirement_id": c.requirement_id, "job_id": c.job_id,
                              "execution": c.execution.as_dict(), "acceptance": c.acceptance.as_dict()} for c in self.f.coverage],
            "dependencies": [], "parent_acceptance": self.f.parent.as_dict(), "parent_receipt": receipt_ref.as_dict(),
            "admissions": {k: {"kind": v.kind, "commit": v.commit, "collected_by": v.collected_by}
                           for k, v in self.f.admissions.items()},
            "artifacts": [ArtifactRef(p, digest(raw), c).as_dict() for (p, c), raw in self.f.store.items()]}
        (root / "bundles").mkdir(parents=True)
        self.bundle_path = root / "bundles" / (self.receipt.sha256 + ".json")
        self.bundle_path.write_bytes(canonical(bundle).encode())

    def read(self, ref):
        return self.f.read(ref)

    def admit(self, kind, commit, value):
        raw = value if isinstance(value, bytes) else canonical(value).encode() + b"\n"
        ref = ArtifactRef("control/" + digest(raw) + ".json", digest(raw), commit)
        self.admissions.append((kind, commit, raw))
        return ref


class Remote:
    def __init__(self):
        self.main = fixture.MAIN
        self.ref = None
        self.pr = None
        self.comments = []
        self.effects = []
        self.ci_success = True
        self.ci_head = "5" * 40
        self.unknown_pr = False
        self.unknown_merge = False
        self.auto_ack = True

    def request(self, method, path, body=None):
        if path.endswith("commits/main"):
            return {"sha": self.main}
        if "/git/ref/heads/" in path:
            if self.ref is None:
                raise PMError("fixture absent branch")
            return {"object": {"sha": self.ref}}
        if path.endswith("/check-runs?per_page=100"):
            return {"total_count": 1, "check_runs": [{"name": "core-test", "head_sha": self.ci_head,
                "app": {"id": 15368},
                "status": "completed" if self.ci_success else "in_progress", "conclusion": "success"}]}
        if "/pulls/" in path:
            return self.pr
        if path.endswith("/comments") and method == "POST":
            self.effects.append("project")
            row = {"id": 100, "body": body["body"], "user": {"login": fixture.PM},
                   "created_at": "now", "updated_at": "now",
                   "html_url": f"https://github.com/{fixture.REPO}/issues/28#issuecomment-100"}
            self.comments.append(row)
            if self.auto_ack:
                self.comments.append({"id": 101, "user": {"login": fixture.PM},
                    "body": f"LGAX-RECEIPT 100 ACCEPTED\n`{self.main}`",
                    "html_url": f"https://github.com/{fixture.REPO}/issues/28#issuecomment-101"})
            return row
        if "/commits/" in path:
            return {"parents": [{"sha": fixture.MAIN}]}
        raise AssertionError((method, path))

    def pages(self, path):
        if "/pulls?" in path:
            return [self.pr] if self.pr else []
        if path.endswith("/comments"):
            return self.comments
        raise AssertionError(path)

    def command(self, args):
        self.effects.append(args[1])
        if args[1] == "create":
            if self.unknown_pr:
                raise PMError("fixture lost create response")
            branch = args[args.index("--head") + 1]
            self.pr = {"number": 42, "draft": False, "state": "open", "merged": False,
                       "user": {"login": fixture.PM},
                       "head": {"ref": branch, "sha": self.ref, "repo": {"full_name": fixture.REPO}},
                       "base": {"ref": "main", "sha": fixture.MAIN, "repo": {"full_name": fixture.REPO}}}
        elif args[1] == "merge":
            if self.unknown_merge:
                raise PMError("fixture lost merge response")
            self.main = fixture.PUBLISHED
            self.pr.update(merged=True, state="closed", merge_commit_sha=self.main)
        else:
            raise AssertionError(args)
        return b""


class FakePublisher(CompletionPublisher):
    """Remote lifecycle fixture; actual object-plumbing is tested separately."""
    def _prepare(self, contract, candidate, entry, files, completion):
        self.exported = dict(files)
        entry.update(head="5" * 40, tree="6" * 40, files={p: digest(v) for p, v in files.items()},
                     branch="codex/fixture-metadata", completion=completion)
        self._save()

    def _verify_metadata(self, entry):
        for path, expected in entry["files"].items():
            if digest(self.exported[path]) != expected:
                raise CompletionError("fixture altered metadata")

    def _offline(self, entry):
        entry["offline"] = {"head": entry["head"], "log_sha256": "a" * 64}
        self._save()

    def _git(self, args, **kwargs):
        if args[0] == "remote":
            return ("https://github.com/" + fixture.REPO).encode()
        if args[0] == "push":
            self.broker.github.effects.append("push")
            self.broker.github.ref = self.state["publications"][self.store.receipt.sha256]["head"]
            return b""
        if args[0] == "fetch":
            return b""
        if args[0] == "rev-parse":
            return ("6" * 40).encode()
        raise AssertionError(args)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        if os.name == "nt":
            # All files are under this freshly allocated test directory. Native
            # extended-path cleanup also covers the intentionally long evidence
            # paths exercised by the Windows export regression.
            self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir())))
            self.addCleanup(shutil.rmtree, "\\\\?\\" + str(self.root.resolve()))
        self.store = FakeStore(self.root / "evidence")
        self.remote = Remote()
        self.snapshot = {"approved_commit": fixture.MAIN, "tasks": {
            fixture.TASK: {"owner": fixture.OWNER, "status": "ready", "depends_on": [], "scope": "required"}}}
        self.controller_effects = []
        self.controller_accepts = True
        controller = SimpleNamespace(request=self.controller)
        config = {"journal_file": str(self.root / "pm.sqlite"), "policy_sha256": "f" * 64,
                  "parent_publication_administrator_bypass": True}
        self.broker = SimpleNamespace(state_dir=self.root / "state", config=config, repository=self.root,
            github=self.remote, controller=controller, authenticate=Mock(), enabled=Mock(return_value=True),
            policy={"allow_auto_merge": True, "allow_admin_bypass": True, "admin_bypass_delegation": "fixture delegation",
                    "limits": {"max_actions_per_day": 100, "max_actions_per_task": 20}},
            _formal_source_matches=Mock())
        self.pub = FakePublisher(self.broker)
        self.pub.store = self.store
        self.contract = self.store.f.contract

    def controller(self, route, value=None):
        if route == "/v1/status":
            return {"formal_snapshot": self.snapshot}
        if route == "/v1/formal-snapshot":
            self.controller_effects.append(value)
            if self.controller_accepts:
                self.snapshot = {"approved_commit": value["approved_commit"], "tasks": value["tasks"]}
            return {"accepted": self.controller_accepts}
        raise AssertionError(route)

    def tick(self):
        # The parent module is a fixed deployed module in production. This test
        # dataclass substitutes only the typed result, never authority evidence.
        with patch.dict("sys.modules", {"services.automation.parent_collector":
                        SimpleNamespace(Publication=lambda commit, snapshot_ack: SimpleNamespace(
                            commit=commit, snapshot_ack=snapshot_ack))}):
            return self.pub(self.contract, self.store.receipt, self.store)

    def test_actual_dual_ack_required_before_admission_and_followup_release(self):
        self.controller_accepts = False
        self.assertIsNone(self.tick())
        self.assertFalse(self.store.admissions)
        self.assertEqual(self.remote.effects, ["push", "create", "merge", "project"])
        self.assertEqual(len(self.controller_effects), 1)
        self.assertIsNone(self.tick())
        self.assertEqual(len(self.controller_effects), 1, "unknown snapshot is not replayed")
        self.snapshot = self.controller_effects[0]
        publication = self.tick()
        self.assertEqual(publication.commit, fixture.PUBLISHED)
        self.assertEqual([kind for kind, _, _ in self.store.admissions], ["parent_completion", "snapshot_ack"])
        self.assertIn(fixture.TASK, self.store.index["published_completions"])
        ack = json.loads(self.store.admissions[-1][2])
        self.assertEqual(ack["completion_digests"][fixture.TASK], self.store.receipt.sha256)
        self.assertEqual(ack["task_states"][fixture.TASK], "done")

    def test_pending_ci_has_no_merge_snapshot_or_admission(self):
        self.remote.ci_success = False
        self.assertIsNone(self.tick())
        self.assertEqual(self.remote.effects, ["push", "create"])
        self.assertFalse(self.controller_effects)
        self.assertFalse(self.store.admissions)
        self.remote.ci_success = True
        self.assertIsNotNone(self.tick())

    def test_wrong_head_ci_or_moved_main_fails_without_merge(self):
        self.remote.ci_head = "7" * 40
        with self.assertRaises(CompletionError):
            self.tick()
        self.assertNotIn("merge", self.remote.effects)
        self.remote.ci_head = "5" * 40
        self.remote.main = "8" * 40
        with self.assertRaises(CompletionError):
            self.tick()
        self.assertNotIn("merge", self.remote.effects)

    def test_distinct_push_and_pr_runs_pass_but_untrusted_app_blocks(self):
        original = self.remote.request
        trusted = False

        def runs(method, path, body=None):
            row = original(method, path, body)
            if path.endswith("/check-runs?per_page=100"):
                first = row["check_runs"][0]
                if not trusted:
                    first["app"] = {"id": 999}
                row["check_runs"].append(dict(first))
                row["total_count"] = 2
            return row

        with patch.object(self.remote, "request", side_effect=runs):
            with self.assertRaises(CompletionError):
                self.tick()
            self.assertNotIn("merge", self.remote.effects)
            trusted = True
            self.assertIsNotNone(self.tick())

    def test_unknown_pr_creation_is_never_blindly_retried(self):
        self.remote.unknown_pr = True
        self.assertIsNone(self.tick())
        self.assertIsNone(self.tick())
        self.assertEqual(self.remote.effects.count("create"), 1)
        self.assertFalse(self.store.admissions)

    def test_unknown_merge_is_never_blindly_retried(self):
        self.remote.unknown_merge = True
        self.assertIsNone(self.tick())
        self.assertIsNone(self.tick())
        self.assertEqual(self.remote.effects.count("merge"), 1)
        self.assertFalse(self.store.admissions)

    def test_off_and_missing_admin_delegation_cannot_mutate(self):
        self.broker.enabled.return_value = False
        self.assertIsNone(self.tick())
        self.assertFalse(self.remote.effects)
        self.broker.enabled.return_value = True
        self.broker.policy["allow_admin_bypass"] = False
        with self.assertRaises(CompletionError):
            self.tick()
        self.assertNotIn("merge", self.remote.effects)

    def test_action_budget_is_combined_with_existing_pm_journal(self):
        journal = Journal(self.broker.config["journal_file"], self.broker.config["policy_sha256"])
        with journal.connect() as db:
            journal.budget(db, "task:" + fixture.TASK)
            db.execute("UPDATE budgets SET actions=20 WHERE scope=?", ("task:" + fixture.TASK,))
        with self.assertRaises(CompletionError):
            self.tick()
        self.assertFalse(self.remote.effects)
        with closing(sqlite3.connect(journal.path)) as db:
            self.assertEqual(db.execute("SELECT actions FROM budgets WHERE scope=?", ("task:" + fixture.TASK,)).fetchone()[0], 20)

    def test_lost_successful_merge_is_observed_without_second_merge(self):
        original = self.remote.command
        def lost_response(args):
            result = original(args)
            if args[1] == "merge":
                raise PMError("fixture lost success response")
            return result
        self.remote.command = lost_response
        self.assertIsNone(self.tick())
        self.assertEqual(self.remote.main, fixture.PUBLISHED)
        self.assertIsNotNone(self.tick())
        self.assertEqual(self.remote.effects.count("merge"), 1)

    def test_pending_resume_after_metadata_main_moves_admits_only_after_dual_ack(self):
        self.remote.auto_ack = False
        self.assertIsNone(self.tick())
        source = self.remote.comments[0]
        self.remote.comments.append({"id": 101, "user": {"login": fixture.PM},
            "body": f"LGAX-RECEIPT {source['id']} ACCEPTED\n`{fixture.PUBLISHED}`",
            "html_url": f"https://github.com/{fixture.REPO}/issues/28#issuecomment-101"})
        with patch.dict("sys.modules", {"services.automation.parent_collector":
                        SimpleNamespace(Publication=lambda commit, snapshot_ack: SimpleNamespace(
                            commit=commit, snapshot_ack=snapshot_ack))}):
            results = self.pub.resume_pending(self.store)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["task_id"], fixture.TASK)
        self.assertEqual(results[0]["publication"].commit, fixture.PUBLISHED)
        self.assertEqual(self.remote.effects.count("merge"), 1)
        self.assertEqual(self.pub.resume_pending(self.store), [])

    def test_export_is_exact_immutable_bytes_and_bad_bundle_cannot_publish(self):
        files, completion = self.pub._export(self.contract, self.store.receipt, self.store)
        bundle = json.loads(files[completion["path"]])
        self.assertEqual(digest(files[completion["path"]]), completion["sha256"])
        self.assertEqual(completion["parent_receipt_sha256"], self.store.receipt.sha256)
        for item in bundle["artifacts"]:
            ref = ArtifactRef.parse(item)
            self.assertEqual(files[bundle["artifact_files"][ref.sha256]], self.store.read(ref))
        source = json.loads(self.store.bundle_path.read_bytes())
        source["requirements"] = source["requirements"][:1]
        self.store.bundle_path.write_bytes(canonical(source).encode())
        with self.assertRaises(CompletionError):
            self.tick()
        self.assertFalse(self.remote.effects)

    def test_project_ack_is_pending_without_duplicate_comment_or_fake_admission(self):
        self.remote.auto_ack = False
        self.assertIsNone(self.tick())
        self.assertIsNone(self.tick())
        self.assertEqual(self.remote.effects.count("project"), 1)
        self.assertFalse(self.store.admissions)

    def test_offline_validator_has_no_auth_network_or_checkout_code_and_unknown_is_not_retried(self):
        files, completion = self.pub._export(self.contract, self.store.receipt, self.store)
        entry = {"head": "5" * 40, "task_id": fixture.TASK, "candidate": self.store.receipt.sha256,
                 "files": {p: digest(raw) for p, raw in files.items()}, "completion": completion}
        self.pub._read_blob = Mock(side_effect=lambda _commit, path: files[path])
        executor = SimpleNamespace(config=SimpleNamespace(workspace_root=self.root / "guest", image="sha256:" + "a" * 64),
            last_boundary={"backend": "docker", "role": "validator", "image_id": "sha256:" + "a" * 64,
                           "uid": 1000, "publisher_credentials_mounted": False, "ai_profile_mounted": False,
                           "network": "none", "readonly_root": True, "caps_dropped": True, "no_new_privileges": True})
        calls = []
        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            self.assertEqual(argv[:3], ["python", "-I", "-c"])
            self.assertEqual(kwargs["role"], "validator")
            self.assertEqual(kwargs["env"], {})
            self.assertTrue(kwargs["readonly_workspace"])
            self.assertEqual(list(kwargs["artifacts"].iterdir()), [])
            self.assertTrue((kwargs["cwd"] / "_trusted_completion.py").is_file())
            self.assertFalse((kwargs["cwd"] / ".git").exists())
            kwargs["output"].write_bytes(b"fixture fixed isolated validation log\n")
            return SimpleNamespace(returncode=0, stopped_reason=None)
        executor.run = run
        self.broker.executor = executor
        CompletionPublisher._offline(self.pub, entry)
        self.assertEqual(len(calls), 1)
        self.assertEqual(entry["offline"]["head"], entry["head"])
        unsafe = {k: v for k, v in entry.items() if k not in {"offline", "offline_started"}}
        executor.last_boundary["publisher_credentials_mounted"] = True
        with self.assertRaises(CompletionError):
            CompletionPublisher._offline(self.pub, unsafe)
        self.assertNotIn("offline", unsafe)
        with self.assertRaises(CompletionError):
            CompletionPublisher._offline(self.pub, unsafe)
        self.assertEqual(len(calls), 2, "failed/unknown validation cannot be blindly replayed")


class ObjectPlumbingTests(unittest.TestCase):
    def test_actual_git_metadata_tree_preserves_product_and_all_old_task_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "fixture")
            git("config", "user.email", "fixture@example.test")
            task_path = f"harness/phase2/tasks/{fixture.TASK}.json"
            original = {"id": fixture.TASK, "owner": "황대겸", "scope": "required", "status": "ready",
                        "requirement_ids": ["R01", "R02"], "history": [{"existing": True}], "custom": "preserve"}
            (repo / task_path).parent.mkdir(parents=True)
            (repo / task_path).write_bytes(canonical(original).encode())
            (repo / "product.txt").write_bytes(b"Do not change product bytes\n")
            git("add", ".")
            git("commit", "-qm", "fixture base")
            base = git("rev-parse", "HEAD").decode()
            git("remote", "add", "origin", "https://github.com/" + fixture.REPO)
            config = {"journal_file": str(root / "journal.sqlite"), "policy_sha256": "a" * 64}
            broker = SimpleNamespace(state_dir=root / "state", config=config, repository=repo)
            publisher = CompletionPublisher(broker)
            fixed_git = publisher._git
            publisher._git = lambda args, **kwargs: b"" if args[0] == "fetch" else fixed_git(args, **kwargs)
            receipt = SimpleNamespace(sha256="f" * 64, payload={"tested_commit": base})
            contract = SimpleNamespace(task_id=fixture.TASK, owner=fixture.OWNER, requirements=(("R01", "x"), ("R02", "y")))
            path = f"evals/automation-completion/{fixture.TASK}/{'f' * 64}/bundle.json"
            completion = {"path": path, "sha256": digest(b"{}\n"), "parent_receipt_sha256": "f" * 64}
            entry = {"base": base, "task_id": fixture.TASK}
            publisher._prepare(contract, receipt, entry, {path: b"{}\n"}, completion)
            head = entry["head"]
            self.assertEqual(git("show", head + ":product.txt"), b"Do not change product bytes")
            task = json.loads(git("show", head + ":" + task_path))
            for key, value in original.items():
                self.assertEqual(task[key], "done" if key == "status" else value)
            self.assertEqual(task["completion_protocol"], "trusted_auto_parent_v1")
            self.assertEqual(task["completion"], completion)
            self.assertEqual(git("rev-parse", "HEAD").decode(), base, "publisher does not move checked-out main")
            (repo / "product.txt").write_bytes(b"Host working tree untouched by metadata commit\n")
            publisher._verify_metadata(entry)
            self.assertEqual(git("diff", "--name-only", base, head).decode().splitlines(), [path, task_path])
