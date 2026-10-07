"""Manual field repair ownership and preservation with actual source input, wire stubs only."""

import json
import tempfile
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from test_research_workspace import PACK, ContractOnlyPlanner


class RepairWirePlanner(ContractOnlyPlanner):
    def __init__(self):
        super().__init__()
        self.repairs = []
        self.rewrite_healthy_field = False

    def run(self, bundle, goal, constraints, previous=None):
        result = super().run(bundle, goal, constraints, previous)
        source = next(item for item in bundle["sources"] if item["source_id"] == "LGE-R8-REVIEW-752651")
        result["problems"] = [{"id": "test-problem", "title": "TEST ONLY: 공개 후기 전송 경계",
            "description": source["text"], "source_ids": [source["source_id"]], "counter_source_ids": [],
            "scope_caveat": "TEST ONLY: 모델 기획이 아닌 전송·보존 검사입니다."}]
        return result

    def repair(self, bundle, previous, feedback):
        self.repairs.append(deepcopy(feedback))
        result = deepcopy(previous)
        result.update(brief_id="test-repaired-brief", run_id="test-repaired-run",
                      previous_brief_id=previous["brief_id"], revision=previous["revision"] + 1)
        result["problems"][0]["scope_caveat"] = "구매 SKU·냄새 발생 원인은 미확인입니다."
        if self.rewrite_healthy_field:
            result["problems"][0]["description"] = "TEST ONLY: 허용되지 않은 정상 필드 변경"
        result["runtime"] = {"execution_kind": "public_research_field_repair",
            "independent_semantic_quality_verified": True, "review_feedback": feedback,
            "model_calls": [{"stage": "repair_fields", "status": "returned", "response": {"private": True}}],
            "repair_outcomes": [{"item_kind": "Problem", "item_id": "test-problem", "status": "accepted",
                                 "message": "private-provider-message"}]}
        return result


class ManualRepairApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bundle = json.loads(PACK.read_text("utf-8"))
        self.planner = RepairWirePlanner()
        token = "test-only-manual-repair-token-20261007"
        registry = TokenRegistry([{"principal_id": "manual-repair-test", "role": "editor",
                                   "token_sha256": sha256(token.encode()).hexdigest()}])
        self.workspace = ResearchWorkspace(root / "research.sqlite3", [PACK], self.planner)
        self.client = TestClient(create_workspace_app(root / "workspace.sqlite3", registry,
                                                     research_workspace=self.workspace), base_url="http://127.0.0.1")
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer " + token, "Origin": "http://127.0.0.1:5175"}
        self.payload = {"bundle_id": self.bundle["bundle_id"], "goal": "TEST ONLY: 저장·국소 수정 경계", "constraints": []}
        response = self.client.post("/api/research/planning-runs", headers=self.headers, json=self.payload)
        self.assertEqual(response.status_code, 201)
        self.previous = response.json()
        self.feedback = [{"item_kind": "Problem", "item_id": "test-problem", "fields": ["scope_caveat"],
                          "message": "원문에 없는 원인·구매 모델은 미확인으로 유지하세요."}]

    def request(self, **changes):
        return self.client.post("/api/research/planning-runs", headers=self.headers,
            json={**self.payload, "previous_run_id": self.previous["run_id"],
                  "review_feedback": self.feedback, **changes})

    def test_field_repair_saves_new_version_preserving_original_and_redacts_private_feedback(self):
        response = self.request()
        self.assertEqual(response.status_code, 201)
        result = response.json()
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["previous_brief_id"], self.previous["brief_id"])
        self.assertEqual(result["source_facts"], self.previous["source_facts"])
        self.assertEqual(result["problems"][0]["description"], self.previous["problems"][0]["description"])
        self.assertEqual(result["runtime"]["repair_count"], 1)
        self.assertEqual(result["runtime"]["repair_outcomes"], [{"item_kind": "Problem", "item_id": "test-problem", "status": "accepted"}])
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])
        self.assertNotIn("review_feedback", result["runtime"])
        self.assertNotIn("private-provider-message", response.text)
        self.assertEqual(self.client.get("/api/research/planning-runs/" + result["run_id"], headers=self.headers).json(), result)
        self.assertEqual(self.client.get("/api/research/planning-runs/" + self.previous["run_id"], headers=self.headers).json(), self.previous)

    def test_repair_requires_existing_run_and_unchanged_goal_constraints_before_model(self):
        for changes in ({"previous_run_id": None}, {"goal": "다른 목적"}, {"constraints": ["새 조건"]}):
            with self.subTest(changes=changes):
                response = self.request(**changes)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.planner.repairs, [])

    def test_unknown_items_identity_fields_and_empty_feedback_rejected_before_model(self):
        for feedback in ([], [{**self.feedback[0], "item_id": "unknown-item"}],
                         [{**self.feedback[0], "fields": ["id"]}],
                         [{**self.feedback[0], "message": "x" * 501}]):
            with self.subTest(feedback=feedback):
                response = self.request(review_feedback=feedback)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.planner.repairs, [])

    def test_adapter_cannot_modify_healthy_field_or_overwrite_original(self):
        self.planner.rewrite_healthy_field = True
        response = self.request()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "CONTRACT_MISMATCH")
        with self.workspace.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT status FROM research_attempts ORDER BY rowid DESC LIMIT 1").fetchone()[0], "failed")
        self.assertEqual(self.client.get("/api/research/planning-runs/" + self.previous["run_id"], headers=self.headers).json(), self.previous)


if __name__ == "__main__":
    unittest.main()
