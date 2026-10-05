"""Exported multi-unit gates test integrity only; fixtures are not live proof."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_automation_completion import BASE, MAIN, TASK, Fixture

from scripts.phase2 import automatic_completion_errors


class AutomaticParentGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        f = Fixture()
        receipt = f.assessment().receipt
        ref = f.put(receipt.raw)
        self.prefix = f"evals/automation-completion/{TASK}/{receipt.sha256}/"
        self.bundle = {"schema_version": 1, "protocol": "trusted_auto_parent_v1", "task_id": TASK,
                       "source_commit": BASE, "tested_commit": MAIN,
                       "sources": {"requirements": f.requirements_ref.as_dict(), "task": f.task_ref.as_dict(),
                                   "policy": f.policy_ref.as_dict()},
                       "accepted_units": [{k: getattr(f.unit, k).as_dict() for k in
                                           ("acceptance", "review", "merge", "postmerge")}],
                       "requirements": [{"requirement_id": c.requirement_id, "job_id": c.job_id,
                                         "execution": c.execution.as_dict(), "acceptance": c.acceptance.as_dict()}
                                        for c in f.coverage], "dependencies": [],
                       "parent_acceptance": f.parent.as_dict(), "parent_receipt": ref.as_dict(),
                       "admissions": {k: {"kind": v.kind, "commit": v.commit, "collected_by": v.collected_by}
                                      for k, v in f.admissions.items()}, "artifact_files": {}}
        for raw in f.store.values():
            sha = hashlib.sha256(raw).hexdigest()
            path = self.prefix + f"assets/{sha}.blob"
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            self.bundle["artifact_files"][sha] = path
        self.task = copy.deepcopy(f.task)
        self.task.update(status="done", completion_protocol="trusted_auto_parent_v1",
                         completion={"path": self.prefix + "bundle.json", "parent_receipt_sha256": receipt.sha256})
        self.save()

    def save(self):
        raw = json.dumps(self.bundle).encode()
        (self.root / self.task["completion"]["path"]).write_bytes(raw)
        self.task["completion"]["sha256"] = hashlib.sha256(raw).hexdigest()

    def test_complete_multiunit_contract_without_fabricated_legacy_lifecycle(self):
        self.assertEqual(automatic_completion_errors(self.root, self.task), [])
        self.assertNotIn("individual_evidence", self.task)

    def test_removed_requirement_changed_asset_or_owner_rejected(self):
        for failure in ("requirement", "asset", "owner", "path", "digest"):
            with self.subTest(failure=failure):
                test = AutomaticParentGateTests()
                test.setUp()
                self.addCleanup(test.doCleanups)
                if failure == "requirement":
                    test.bundle["requirements"].pop()
                elif failure == "asset":
                    (test.root / next(iter(test.bundle["artifact_files"].values()))).write_bytes(b"changed")
                elif failure == "owner":
                    test.task["owner"] = "정이량"
                elif failure == "path":
                    sha = next(iter(test.bundle["artifact_files"]))
                    test.bundle["artifact_files"][sha] = "../../outside"
                else:
                    test.task["completion"]["parent_receipt_sha256"] = "f" * 64
                test.save()
                self.assertTrue(automatic_completion_errors(test.root, test.task))


if __name__ == "__main__":
    unittest.main()
