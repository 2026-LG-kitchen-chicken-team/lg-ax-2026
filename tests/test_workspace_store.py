"""Persistence, immutable user input lineage and ownership/source boundaries."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

from lgax_contracts import validate
from lgax_core import DemoStore
from lgax_core.errors import DomainError
from lgax_core.workspace import WorkspaceStore


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "workspace.sqlite3"
        self.evidence = DemoStore()
        self.store = WorkspaceStore(self.path, self.evidence)
        self.request = {
            "product_group": "fridge", "target_customer": "냉장고 사용자", "use_situation": "선반 청소",
            "improvement_task": "청소 불편과 기존 기능 대조", "exclusions": ["실기기 제어"],
            "model_ids": ["FRIDGE-A"], "dataset_version": "0.1.0",
        }
        self.project = self.store.create_project("청소 기획", self.request, "planner-a", {"FRIDGE-A": "1.0"})
        self.project_id = self.project["project"]["id"]

    def assert_domain(self, code, function, *args, **kwargs):
        with self.assertRaises(DomainError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    def test_hash_is_canonical_dataset_not_file_or_transport_metadata(self):
        dataset = self.evidence.bootstrap()["data"]
        dataset.pop("contract_version")
        canonical = json.dumps(dataset, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(self.store.dataset_sha256, expected)
        self.assertEqual(self.project["dataset_sha256"], expected)

    def test_saved_snapshot_is_not_mutated_by_inputs_or_returned_values(self):
        request = deepcopy(self.request)
        versions = {"FRIDGE-A": "1.0"}
        project = self.store.create_project("원본 보존", request, "planner-a", versions)
        project_id = project["project"]["id"]
        request["exclusions"].append("나중에 추가")
        versions["FRIDGE-A"] = "2.0"
        project["project"]["request"]["improvement_task"] = "반환값 수정"
        stored = self.store.get_project(project_id, "planner-a")
        self.assertEqual(stored["project"]["request"], self.request)
        self.assertEqual(stored["document_versions"], {"FRIDGE-A": "1.0"})
        run = self.store.create_run(project_id, self.request, "planner-a", "web", unconfirmed=["수요 확인"])
        run_id = run["run"]["id"]
        run["request"]["exclusions"].append("반환값 변경")
        run["unconfirmed"].clear()
        self.assertEqual(self.store.get_run(run_id, "planner-a")["request"], self.request)
        self.assertEqual(self.store.get_run(run_id, "planner-a")["unconfirmed"], ["수요 확인"])

    def test_process_restart_retains_project_and_run(self):
        run = self.store.create_run(self.project_id, self.request, "planner-a", "api")
        script = """
import json, sys
from pathlib import Path
from lgax_core.workspace import WorkspaceStore
store = WorkspaceStore(Path(sys.argv[1]))
print(json.dumps([store.get_project(sys.argv[2], 'planner-a'), store.get_run(sys.argv[3], 'planner-a')]))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script, str(self.path), self.project_id, run["run"]["id"]],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )
        project_again, run_again = json.loads(completed.stdout)
        self.assertEqual(project_again, self.project)
        self.assertEqual(run_again, run)

    def test_request_lineage_is_separate_from_agent_revision_and_never_fakes_results(self):
        first = self.store.create_run(self.project_id, self.request, "planner-a", "web")
        changed = {**self.request, "use_situation": "우유를 쏟은 구획만 청소"}
        second = self.store.create_run(self.project_id, changed, "planner-a", "mcp", first["run"]["id"])
        replay = self.store.create_run(self.project_id, changed, "planner-a", "skill", second["run"]["id"])
        third_request = {**changed, "exclusions": [*changed["exclusions"], "식품 전체 이동"]}
        third = self.store.create_run(self.project_id, third_request, "planner-a", "api", replay["run"]["id"])
        fourth_request = {**third_request, "target_customer": "식품이 많은 다인 가구"}
        fourth = self.store.create_run(self.project_id, fourth_request, "planner-a", "web", third["run"]["id"])
        snapshots = (first, second, replay, third, fourth)
        self.assertEqual([snapshot["request_revision"] for snapshot in snapshots], [0, 1, 1, 2, 3])
        for snapshot in snapshots:
            validate("Run", snapshot["run"])
            validate("PlanningRequest", snapshot["request"])
            validate("WorkspaceRunSnapshot", snapshot)
            self.assertEqual(snapshot["run"]["revision_count"], 0)
            self.assertEqual(snapshot["run"]["max_revisions"], 2)
            self.assertEqual(snapshot["run"]["status"], "not_implemented")
            self.assertEqual(snapshot["run"]["stage"], "plan")
            self.assertEqual(snapshot["run"]["concepts"], [])
            self.assertEqual(snapshot["run"]["evidence_ids"], [])
            self.assertIsNone(snapshot["output"])
            self.assertEqual(snapshot["unconfirmed"], [])
            self.assertTrue(snapshot["run"]["unresolved"])
            self.assertEqual(len(snapshot["run"]["events"]), 1)
            self.assertIn("분석은 실행하지 않았습니다", snapshot["run"]["events"][0]["summary"])
        self.assertEqual(self.store.get_run(first["run"]["id"], "planner-a")["request"], self.request)
        self.assertEqual(self.store.get_project(self.project_id, "planner-a"), self.project)

    def test_owner_access_unknown_records_and_admin_are_explicit(self):
        run = self.store.create_run(self.project_id, self.request, "planner-a", "web")
        self.assertEqual(self.store.list_projects("planner-b"), [])
        self.assert_domain("FORBIDDEN", self.store.get_project, self.project_id, "planner-b")
        self.assert_domain("FORBIDDEN", self.store.get_run, run["run"]["id"], "planner-b")
        self.assert_domain("FORBIDDEN", self.store.list_runs, self.project_id, "planner-b")
        self.assert_domain("FORBIDDEN", self.store.create_run, self.project_id, self.request, "planner-b", "web")
        missing = self.assert_domain("NOT_FOUND", self.store.get_run, "run-missing", "planner-b")
        self.assertEqual(missing.details, {})
        self.assertNotIn(self.project_id, str(missing))
        self.assertEqual(self.store.get_run(run["run"]["id"], "admin-user", admin=True), run)
        self.assertEqual(self.store.list_projects("admin-user", admin=True), [self.project])
        self.assert_domain("INVALID_ARGUMENT", self.store.get_project, self.project_id, "planner-b", admin="true")

    def test_parent_must_exist_belong_to_project_and_be_accessible(self):
        other = self.store.create_project("다른 프로젝트", self.request, "planner-a", {"FRIDGE-A": "1.0"})
        foreign_project_run = self.store.create_run(other["project"]["id"], self.request, "planner-a", "web")
        self.assert_domain("INVALID_ARGUMENT", self.store.create_run, self.project_id, self.request,
                           "planner-a", "api", previous_run_id=foreign_project_run["run"]["id"])
        private_project = self.store.create_project("타인 기획", self.request, "planner-b", {"FRIDGE-A": "1.0"})
        private_run = self.store.create_run(private_project["project"]["id"], self.request, "planner-b", "web")
        error = self.assert_domain("FORBIDDEN", self.store.create_run, self.project_id, self.request,
                                  "planner-a", "api", previous_run_id=private_run["run"]["id"])
        self.assertEqual(error.details, {})
        self.assert_domain("NOT_FOUND", self.store.create_run, self.project_id, self.request,
                           "planner-a", "api", previous_run_id="run-unknown")
        self.assertEqual(self.store.list_runs(self.project_id, "planner-a"), [])

    def test_wrong_models_group_versions_or_dataset_are_rejected_without_partial_writes(self):
        cases = [({**self.request, "model_ids": ["UNKNOWN"]}, {"UNKNOWN": "1.0"}, "INVALID_ARGUMENT"),
                 ({**self.request, "product_group": "dishwasher"}, {"FRIDGE-A": "1.0"}, "INVALID_ARGUMENT"),
                 (self.request, {"FRIDGE-A": "missing-version"}, "INVALID_ARGUMENT"),
                 (self.request, {}, "INVALID_ARGUMENT"),
                 ({**self.request, "dataset_version": "9.0"}, {"FRIDGE-A": "1.0"}, "DATASET_MISMATCH")]
        for request, versions, code in cases:
            with self.subTest(code=code, versions=versions):
                self.assert_domain(code, self.store.create_project, "거부할 입력", request, "planner-a", versions)
        self.assertEqual(len(self.store.list_projects("planner-a")), 1)
        self.assert_domain("INVALID_ARGUMENT", self.store.create_run, self.project_id,
                           {**self.request, "model_ids": ["FRIDGE-B"]}, "planner-a", "web")
        self.assert_domain("INVALID_ARGUMENT", self.store.create_run, self.project_id,
                           {**self.request, "target_customer": " "}, "planner-a", "web")
        self.assertEqual(self.store.list_runs(self.project_id, "planner-a"), [])

    def test_same_version_label_with_changed_content_rejects_new_runs_but_keeps_old_records(self):
        run = self.store.create_run(self.project_id, self.request, "planner-a", "api")
        changed_dataset = self.evidence.bootstrap()["data"]
        changed_dataset.pop("contract_version")
        manual = next(item for item in changed_dataset["evidence"] if item["source_type"] == "manual")
        manual["text"] += " 같은 버전 이름으로 원문 변경."
        changed_store = WorkspaceStore(self.path, DemoStore(changed_dataset))
        self.assertNotEqual(changed_store.dataset_sha256, self.project["dataset_sha256"])
        self.assertEqual(changed_store.get_run(run["run"]["id"], "planner-a"), run)
        self.assertEqual(changed_store.get_project(self.project_id, "planner-a"), self.project)
        self.assert_domain("DATASET_MISMATCH", changed_store.create_run, self.project_id,
                           self.request, "planner-a", "api", previous_run_id=run["run"]["id"])
        self.assertEqual(len(changed_store.list_runs(self.project_id, "planner-a")), 1)

    def test_parameter_binding_preserves_sql_like_user_text(self):
        title = "기획'); DROP TABLE workspace_projects; --"
        request = {**self.request, "improvement_task": "선반' OR '1'='1의 불편 검토"}
        project = self.store.create_project(title, request, "planner-a", {"FRIDGE-A": "1.0"})
        self.assertEqual(self.store.get_project(project["project"]["id"], "planner-a")["project"]["name"], title)
        self.assertEqual(len(self.store.list_projects("planner-a")), 2)
        self.assert_domain("INVALID_ARGUMENT", self.store.get_project, "' OR 1=1--", "planner-a")

    def test_concurrent_writers_and_separate_instances_do_not_lose_snapshots(self):
        def create(index):
            store = WorkspaceStore(self.path, self.evidence)
            return store.create_run(self.project_id, self.request, "planner-a", "api", unconfirmed=[f"확인 {index}"])

        with ThreadPoolExecutor(max_workers=4) as executor:
            snapshots = list(executor.map(create, range(12)))
        self.assertEqual(len({snapshot["run"]["id"] for snapshot in snapshots}), 12)
        saved = self.store.list_runs(self.project_id, "planner-a")
        self.assertEqual(len(saved), 12)
        self.assertEqual({item["run"]["id"] for item in saved}, {item["run"]["id"] for item in snapshots})
        self.assertEqual({item["unconfirmed"][0] for item in saved}, {f"확인 {index}" for index in range(12)})


if __name__ == "__main__":
    unittest.main()
