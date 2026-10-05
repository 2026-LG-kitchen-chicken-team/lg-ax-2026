"""Actual queue metadata -> fixed child Project, without models or parent Done."""
from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from services.automation.orchestration import DEVELOPMENT_PROJECT, DevelopmentIssueMirror, Orchestration
from services.automation.pm import PMError, fingerprint
from tests import test_automation_development_queue as development

FIRST, ROOT = development.FIRST, development.ROOT


class DevelopmentProjectTests(unittest.TestCase):
    def setUp(self):
        development.DevelopmentQueueTests.setUp(self)
        self.map = json.loads((ROOT / "docs/pm/development-project-map-20261005.json").read_bytes())
        self.map_path = self.root / "project-map.json"
        self.broker.authenticate = Mock(return_value={"account": "jeongiryang", "operator": True})
        self.broker.enabled = Mock(return_value=True)
        self.broker.driver = Mock()
        self.mutations = []
        self.partial = False
        self.remote = self.project()
        self.actual_issues = {row["number"]: {"id": row["issue_id"], "html_url": row["url"],
            "assignees": [{"login": row["owner"]}], "body": f"<!-- lgax-development-capability:{key} -->"}
            for key, row in self.map["capabilities"].items()}
        self.github.command.side_effect = self.graphql
        self.github.request.side_effect = self.request
        self.mirror = self.build()

    def result(self, key, **kwargs):
        return development.DevelopmentQueueTests.result(self, key, **kwargs)

    def build(self):
        self.map_path.write_bytes((json.dumps(self.map) + "\n").encode())
        options = {"path": str(self.map_path), "sha256": hashlib.sha256(self.map_path.read_bytes()).hexdigest()}
        return DevelopmentIssueMirror(self.live, options)

    def project(self):
        return {**{key: DEVELOPMENT_PROJECT[key] for key in ("id", "number", "url")},
            "owner": {"login": DEVELOPMENT_PROJECT["owner"]},
            "fields": {"pageInfo": {"hasNextPage": False}, "nodes": [
                {"id": field, "name": name, **({"options": [{"name": status, "id": value}
                    for status, value in DEVELOPMENT_PROJECT["statuses"].items()]} if name == "Status" else {})}
                for name, field in DEVELOPMENT_PROJECT["fields"].items()]},
            "items": {"pageInfo": {"hasNextPage": False}, "nodes": [{"id": row["project_item_id"],
                "content": {"number": row["number"], "url": row["url"], "repository": {"nameWithOwner": self.map["repo"]}},
                "fieldValues": {"pageInfo": {"hasNextPage": False}, "nodes": [
                    {"field": {"id": DEVELOPMENT_PROJECT["fields"]["Status"]}, "name": "Todo", "optionId": "f75ad846"}]}}
                for row in self.map["capabilities"].values()]}}

    def request(self, method, route):
        self.assertEqual(method, "GET")
        if "/sub_issues" in route:
            parent = int(route.split("/")[-2])
            return [{"id": row["issue_id"]} for row in self.map["capabilities"].values()
                    if row["parent_issue_number"] == parent]
        return deepcopy(self.actual_issues[int(route.rsplit("/", 1)[1])])

    def graphql(self, argv, *, data):
        self.assertEqual(argv, ["api", "--hostname", "github.com", "graphql", "--input", "-"])
        payload = json.loads(data)
        if not payload["query"].startswith("mutation"):
            return json.dumps({"data": {"node": self.remote}}).encode()
        self.mutations.append(payload)
        variables = payload["variables"]
        item = next(row for row in self.remote["items"]["nodes"] if row["id"] == variables["i"])
        answers = {}
        for index in range((len(variables) - 2) // 2):
            field, value = variables[f"f{index}"], variables[f"v{index}"]
            self.assertIn(field, DEVELOPMENT_PROJECT["fields"].values())
            values = item["fieldValues"]["nodes"]
            values[:] = [row for row in values if row["field"]["id"] != field]
            if "text" in value:
                values.append({"field": {"id": field}, "text": value["text"]})
            else:
                status = next(name for name, option in DEVELOPMENT_PROJECT["statuses"].items() if option == value["singleSelectOptionId"])
                values.append({"field": {"id": field}, "name": status, "optionId": value["singleSelectOptionId"]})
            answers[f"v{index}"] = {"projectV2Item": {"id": item["id"]}}
            if self.partial:
                return json.dumps({"data": answers, "errors": [{"message": "Unknown outcome"}]}).encode()
        return json.dumps({"data": answers}).encode()

    def value(self, key, name):
        item = next(row for row in self.remote["items"]["nodes"] if row["id"] == self.map["capabilities"][key]["project_item_id"])
        return self.mirror._values(item).get(DEVELOPMENT_PROJECT["fields"][name])

    def job(self, status):
        cap = self.registry["capabilities"][FIRST]
        unit = {"job_id": "auto-current", "capability_id": FIRST, "task_id": cap["task_id"],
                "base_commit": "a" * 40, "reconciled": False}
        self.broker.state["units"][unit["job_id"]] = unit
        self.observation["jobs"] = [{"job_id": unit["job_id"], "capability_id": FIRST,
            "task_id": cap["task_id"], "owner": cap["owner"], "status": status}]
        return unit

    def test_only_four_metadata_fields_are_written_and_repeat_or_heartbeat_costs_nothing(self):
        before = deepcopy(self.observation)
        result = self.mirror.synchronize(self.observation, collect=True)
        self.assertEqual(result, {"state": "applied", "updated": 24, "model_called": False})
        self.assertEqual(self.observation, before)
        count = len(self.mutations)
        calls = self.github.command.call_count + self.github.request.call_count
        self.observation["worker_presence"] = {"updated_at": "new heartbeat", "sequence": 500}
        self.assertEqual(self.mirror.synchronize(self.observation, collect=True)["state"], "unchanged")
        self.assertEqual(count, len(self.mutations))
        self.assertEqual(calls, self.github.command.call_count + self.github.request.call_count)
        self.broker.driver.assert_not_called()

    def test_collect_false_and_off_do_not_authenticate_write_or_call_model(self):
        for collect, mode in ((False, "on"), (True, "off")):
            self.observation["global_mode"] = mode
            self.assertEqual(self.mirror.synchronize(self.observation, collect=collect)["state"], "read_only")
        self.github.request.assert_not_called()
        self.github.command.assert_not_called()
        self.broker.authenticate.assert_not_called()
        self.broker.driver.assert_not_called()

    def test_live_orchestration_loads_pinned_map_and_calls_metadata_only_on_collecting_tick(self):
        self.broker.config["development_issue_registry"] = {"path": str(self.map_path),
            "sha256": hashlib.sha256(self.map_path.read_bytes()).hexdigest()}
        live = Orchestration(self.broker)
        live.synchronize(self.observation, collect=False)
        self.github.command.assert_not_called()
        live.synchronize(self.observation, collect=True)
        self.assertEqual(len(self.broker.state["development_project_mirror"]["items"]), 24)
        self.broker.driver.assert_not_called()

    def test_corrupt_cache_or_another_map_requires_explicit_migration_without_writes(self):
        for cache in ({"map_sha256": "f" * 64, "items": {}},
                      {"map_sha256": self.mirror.digest, "items": []},
                      {"map_sha256": self.mirror.digest, "items": {"invented-unit": "e" * 64}}):
            self.broker.state["development_project_mirror"] = cache
            with self.assertRaisesRegex(PMError, "explicit map migration"):
                self.mirror.synchronize(self.observation, collect=True)
        self.github.command.assert_not_called()

    def test_actual_running_blocked_review_and_revision_are_visible_without_fake_acceptance(self):
        unit = self.job("running")
        self.mirror.synchronize(self.observation, collect=True)
        self.assertEqual(self.value(FIRST, "Status"), "In Progress")
        self.observation["jobs"][0]["status"] = "blocked"
        self.mirror.synchronize(self.observation, collect=True)
        self.assertIn("자동 재시도 없음", self.value(FIRST, "다음 행동"))
        self.observation["jobs"][0]["status"] = "review_requested"
        unit.update(pr_number=101, head="b" * 40, revision_requested=True)
        self.mirror.synchronize(self.observation, collect=True)
        self.assertIn("수정 작업 대기", self.value(FIRST, "다음 행동"))
        self.assertIn("/pull/101", self.value(FIRST, "실행 증빙"))
        self.assertNotEqual(self.value(FIRST, "Status"), "Done")

    def test_done_needs_actual_accepted_reconciled_job_and_verified_ledger_not_worker_claim(self):
        unit = self.job("accepted")
        unit["reconciled"] = True
        self.mirror.synchronize(self.observation, collect=True)
        self.assertEqual(self.value(FIRST, "Status"), "In Progress")
        # Existing trusted receipt creation verifies actual merge and postmerge.
        self.observation["jobs"] = []
        self.broker.state["units"] = {}
        self.result(FIRST)
        self.live.synchronize(self.observation, collect=False)
        self.github.request.side_effect = self.request
        before = deepcopy(self.observation["formal_snapshot"])
        self.mirror.synchronize(self.observation, collect=True)
        self.assertEqual(self.value(FIRST, "Status"), "Done")
        self.assertEqual(self.observation["formal_snapshot"], before)

    def test_wrong_operator_or_actual_issue_owner_prevents_all_writes(self):
        self.broker.authenticate.return_value = {"account": "choigilung", "operator": False}
        with self.assertRaises(PMError):
            self.mirror.synchronize(self.observation, collect=True)
        self.assertFalse(self.mutations)
        self.broker.authenticate.return_value = {"account": "jeongiryang", "operator": True}
        self.actual_issues[103]["assignees"] = [{"login": "choigilung"}]
        with self.assertRaisesRegex(PMError, "Issue identity"):
            self.mirror.synchronize(self.observation, collect=True)
        self.assertFalse(self.mutations)

    def test_project_item_identity_field_option_parent_and_pagination_drift_are_refused(self):
        pristine = deepcopy(self.remote)
        changes = [lambda: self.remote.update(url="https://github.com/orgs/other/projects/1"),
            lambda: self.remote["items"]["nodes"][0]["content"].update(number=999),
            lambda: self.remote["fields"]["nodes"][0].update(name="팀원 보고"),
            lambda: self.remote["items"]["pageInfo"].update(hasNextPage=True)]
        for change in changes:
            self.remote = deepcopy(pristine)
            change()
            with self.assertRaises(PMError):
                self.mirror.synchronize(self.observation, collect=True)
            self.assertFalse(self.mutations)
        self.remote = pristine
        self.github.request.side_effect = lambda method, route: [] if "sub_issues" in route else self.request(method, route)
        with self.assertRaisesRegex(PMError, "parent relationship"):
            self.mirror.synchronize(self.observation, collect=True)
        self.assertFalse(self.mutations)

    def test_partial_or_unknown_update_never_enters_applied_cache_then_readback_recovers(self):
        self.partial = True
        with self.assertRaisesRegex(PMError, "not confirmed"):
            self.mirror.synchronize(self.observation, collect=True)
        self.assertNotIn(FIRST, self.broker.state["development_project_mirror"]["items"])
        self.partial = False
        self.assertEqual(self.mirror.synchronize(self.observation, collect=True)["state"], "applied")

    def test_map_tampering_stale_owner_scope_and_arbitrary_field_or_project_are_refused(self):
        for mutate in (lambda: self.map["project"]["fields"].update({"팀원 보고": "arbitrary"}),
                       lambda: self.map["project"].update(number=2),
                       lambda: self.map["capabilities"][FIRST].update(owner="jeongiryang"),
                       lambda: self.map["capabilities"][FIRST].update(capability_fingerprint="f" * 64)):
            saved = deepcopy(self.map)
            mutate()
            with self.assertRaises(PMError):
                self.build()
            self.map = saved
        self.mirror = self.build()
        self.map_path.write_bytes(b"{}")
        with self.assertRaisesRegex(PMError, "map changed"):
            self.mirror.synchronize(self.observation, collect=True)
        self.mirror = self.build()
        self.registry["capabilities"][FIRST]["allowed_paths"] = ["packages/core/new-path.py"]
        self.broker.policy["capabilities"][FIRST] = deepcopy(self.registry["capabilities"][FIRST])
        with self.assertRaisesRegex(PMError, "capability scope"):
            self.build()
        self.assertFalse(self.mutations)

    def test_wrong_job_owner_unknown_state_or_duplicate_current_jobs_cannot_publish(self):
        self.job("running")
        self.observation["jobs"][0]["owner"] = "jeongiryang"
        with self.assertRaisesRegex(PMError, "ownership"):
            self.mirror.synchronize(self.observation, collect=True)
        self.job("invented")
        with self.assertRaisesRegex(PMError, "queue status"):
            self.mirror.synchronize(self.observation, collect=True)
        self.job("running")
        self.broker.state["units"]["another"] = deepcopy(self.broker.state["units"]["auto-current"])
        with self.assertRaisesRegex(PMError, "one current job"):
            self.mirror.synchronize(self.observation, collect=True)
        self.assertFalse(self.mutations)

    def test_public_map_binds_original_registration_bytes_and_exact_cap_scope(self):
        receipt = ROOT / self.map["registration_receipt"]["path"]
        self.assertEqual(hashlib.sha256(receipt.read_bytes()).hexdigest(), self.map["registration_receipt"]["sha256"])
        self.assertEqual(set(self.map["capabilities"]), set(self.registry["capabilities"]))
        for key, row in self.map["capabilities"].items():
            self.assertEqual(row["capability_fingerprint"], fingerprint(self.registry["capabilities"][key]))


if __name__ == "__main__":
    unittest.main()
