"""Live adapter tests with local Git/control fixtures; no application model runs."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from services.automation.completion import (
    PM,
    REPO,
    ArtifactRef,
    CompletionError,
    digest,
    validate_completion_bundle,
)
from services.automation.parent_collector import EvidenceBundle, EvidenceStore, ParentCollector
from tests.test_automation_completion import MAIN, TASK, Fixture


class GitFixtureBroker:
    def __init__(self, root):
        self.state_dir = root / "state"
        self.state_dir.mkdir()
        self.repo = root / "source"
        self.repo.mkdir()
        self.calls = []
        fixture = Fixture()
        for path, value in (("harness/phase2/requirements.json", fixture.catalog),
                            (f"harness/phase2/tasks/{TASK}.json", fixture.task)):
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding="utf-8")
        self._command(["init", "-q"])
        self._command(["config", "user.name", "Test fixture"])
        self._command(["config", "user.email", "fixture@example.invalid"])
        self._command(["remote", "add", "origin", f"https://github.com/{REPO}.git"])
        self._command(["add", "."])
        self._command(["commit", "-qm", "fixture"])
        self.main = self._command(["rev-parse", "HEAD"]).decode().strip()
        self.policy = fixture.policy
        raw = json.dumps(self.policy).encode()
        policy = root / "policy.json"
        policy.write_bytes(raw)
        self.config = {"policy_file": str(policy), "policy_sha256": digest(raw),
                       "parent_contract_source_commit": self.main}
        self.state = {"units": {}, "proofs": {}, "actions": {}}
        self.auth_calls = 0
        self.github = SimpleNamespace(request=lambda method, path: {"sha": self.main})
        self.status = {"formal_snapshot": {"tasks": {TASK: {"status": "pending"}}}, "jobs": []}
        self.controller = SimpleNamespace(request=lambda path: self.status)
        self.executor = SimpleNamespace(config=SimpleNamespace(image="sha256:" + "a" * 64))

    def _command(self, args):
        result = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        return result.stdout

    def _git(self, args, *, binary=False):
        self.calls.append(args)
        raw = b"" if args[0] == "fetch" else self._command(args)
        return raw if binary else raw.decode().strip()

    def authenticate(self):
        self.auth_calls += 1
        return {"account": PM, "operator": True}

    def enabled(self):
        return False


class ParentCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.broker = GitFixtureBroker(self.root)
        self.collector = ParentCollector(self.broker)

    def test_actual_git_source_persisted_missing_and_no_host_repository_execution(self):
        result = self.collector.tick({"main_commit": self.broker.main})
        task = result["tasks"][TASK]
        self.assertEqual(task["state"], "waiting_evidence")
        self.assertEqual(task["missing_requirements"], ["R01", "R02"])
        self.assertEqual(task["next_unit_needed"]["task_id"], TASK)
        self.assertEqual(json.loads(self.collector.assessment_path.read_bytes()), result)
        self.assertGreater(self.broker.auth_calls, 0)
        self.assertTrue(all(call[0] in {"remote", "fetch", "ls-tree", "cat-file"} for call in self.broker.calls))
        self.assertFalse(self.broker.state["proofs"])

    def test_existing_formal_done_is_history_not_new_coverage(self):
        self.broker.status["formal_snapshot"]["tasks"][TASK]["status"] = "done"
        result = self.collector.tick({"main_commit": self.broker.main})
        self.assertEqual(result["tasks"][TASK], {"state": "existing_formal_done", "new_requirement_coverage": False})
        self.assertEqual(self.broker.calls, [])

    def test_changed_policy_hash_and_nonregular_source_hold(self):
        self.broker.config["policy_sha256"] = "f" * 64
        result = self.collector.tick({"main_commit": self.broker.main})
        self.assertEqual(result["tasks"][TASK]["state"], "blocked_evidence")
        with self.assertRaises(CompletionError):
            self.collector._source("missing.json", self.broker.main)

    def test_source_main_race_and_unknown_task_fail_before_persistence(self):
        with self.assertRaises(CompletionError):
            self.collector.tick({"main_commit": "f" * 40})
        self.assertFalse(self.collector.assessment_path.exists())
        with self.assertRaises(CompletionError):
            self.collector.tick({"main_commit": self.broker.main}, ("P2-UNAPPROVED",))

    def test_caller_self_claims_never_create_requirement_admissions(self):
        self.broker.state["proofs"]["fake"] = {"verified": True, "collector": "trusted_pm",
                                                "requirement_proofs": {"R01": {"verified": True}}}
        result = self.collector.tick({"main_commit": self.broker.main})
        self.assertEqual(result["tasks"][TASK]["missing_requirements"], ["R01", "R02"])
        self.assertTrue(all(v["kind"] == "policy" for v in self.collector.store.index["admissions"].values()))

    def test_policy_normalization_defaults_do_not_invalidate_fixed_raw_policy(self):
        self.broker.policy = {**self.broker.policy, "limits": {"normalized_default": 1}}
        result = self.collector.tick({"main_commit": self.broker.main})
        self.assertEqual(result["tasks"][TASK]["state"], "waiting_evidence")

    def test_protected_store_rejects_tampered_or_unregistered_bytes(self):
        store = EvidenceStore(self.root / "separate-evidence")
        ref = store.blob("data/fixture.txt", self.broker.main, b"Fixed source\n")
        self.assertEqual(store.read(ref), b"Fixed source\n")
        (store.root / (ref.sha256 + ".blob")).write_bytes(b"Changed")
        with self.assertRaises(CompletionError):
            store.read(ref)
        with self.assertRaises(CompletionError):
            store.read(ArtifactRef("data/other.txt", ref.sha256, ref.commit))

    def test_on_off_publication_gate_applies_to_actual_candidate(self):
        f = Fixture()
        broker = self.broker
        broker.main = MAIN
        broker.status = {"formal_snapshot": {"tasks": {TASK: {"status": "pending"}}}, "jobs": []}
        broker.state["units"] = {"u": {"task_id": TASK, "reconciled": True}}
        publisher_calls = []
        collector = ParentCollector(broker,
            requirement_collector=lambda contract, main, units, store: EvidenceBundle(tuple(f.coverage), f.parent),
            publisher=lambda *args: publisher_calls.append(args))
        collector._contract = lambda task_id, main: f.contract
        collector._unit = lambda unit, jobs: f.unit
        for (path, commit), raw in f.store.items():
            collector.store.blob(path, commit, raw)
        for key, admission in f.admissions.items():
            collector.store.index["admissions"][key] = {"kind": admission.kind, "commit": admission.commit,
                                                        "collected_by": admission.collected_by}
        collector.store.save()
        result = collector.tick({"main_commit": MAIN})
        self.assertEqual(result["tasks"][TASK]["state"], "candidate")
        self.assertTrue(result["tasks"][TASK]["publication_pending"])
        self.assertEqual(publisher_calls, [])
        path = collector.store.root / "bundles" / (result["tasks"][TASK]["completion_sha256"] + ".json")
        exported = json.loads(path.read_bytes())
        self.assertEqual(validate_completion_bundle(exported, collector.store.read).sha256,
                         result["tasks"][TASK]["completion_sha256"])
        unrelated = collector.store.blob("control/unrelated-private.txt", MAIN, b"Unrelated private fixture")
        exported = collector.completion_bundle(f.contract, (f.unit,), EvidenceBundle(tuple(f.coverage), f.parent),
                                                f.assessment().receipt, MAIN)
        self.assertNotIn(unrelated.as_dict(), exported["artifacts"])
        broker.enabled = lambda: True
        result = collector.tick({"main_commit": MAIN})
        self.assertEqual(len(publisher_calls), 1)
        self.assertEqual(result["tasks"][TASK]["state"], "candidate")
        self.assertTrue(result["tasks"][TASK]["publication_pending"])

    def test_operator_intake_only_reuses_admitted_matching_source_receipts(self):
        f = Fixture()
        self.broker.main = MAIN
        for (path, commit), raw in f.store.items():
            self.collector.store.blob(path, commit, raw)
        self.collector.store.index["admissions"] = {key: {"kind": value.kind, "commit": value.commit,
                                                        "collected_by": value.collected_by}
                                                     for key, value in f.admissions.items()}
        bundle = EvidenceBundle(tuple(f.coverage), f.parent)
        self.collector.register_requirement_bundle(f.contract, MAIN, bundle)
        restored = self.collector._registered_evidence(f.contract, MAIN, (f.unit,), self.collector.store)
        self.assertEqual(restored, bundle)
        self.collector.store.index["admissions"].pop(f.coverage[0].execution.sha256)
        with self.assertRaises(CompletionError):
            self.collector.register_requirement_bundle(f.contract, MAIN, bundle)

    def test_legacy_done_without_exact_snapshot_full_chain_and_execution_not_imported(self):
        status = {"formal_snapshot": {"approved_commit": self.broker.main,
                  "tasks": {TASK: {"owner": "unknownamed", "status": "done"}}}}
        with self.assertRaises(CompletionError):
            self.collector._legacy_dependency(TASK, self.broker.main, status)


if __name__ == "__main__":
    unittest.main()
