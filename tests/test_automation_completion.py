"""Adversarial metadata-only tests; fixtures are not live requirement evidence."""

import copy
import json
import unittest

from services.automation.completion import (
    CATALOG,
    PM,
    REPO,
    AcceptedUnit,
    Admission,
    ArtifactRef,
    CompletionError,
    DependencyEvidence,
    RequirementEvidence,
    TrustedReceiptRegistry,
    assess_parent,
    criterion_digest,
    dependency_release_allowed,
    digest,
    load_contract,
)

BASE = "1" * 40
HEAD = "2" * 40
MAIN = "3" * 40
PUBLISHED = "4" * 40
TASK = "P2-CORE-002"
JOB = "auto-test-001"
OWNER = "unknownamed"


class Fixture:
    def __init__(self):
        self.store = {}
        self.admissions = {}
        self.serial = 0
        self.catalog = {
            "schema_version": 1,
            "source": {"kind": "accepted_application_commitment_mapping", "path": "기획/accepted.md",
                       "sha256_at_extraction": "a" * 64},
            "requirements": [{"id": r, "commitment": "Accepted " + r, "acceptance": "Execute " + r,
                              "linked_task_ids": [TASK]} for r in sorted(CATALOG)],
        }
        self.task = {"id": TASK, "owner": "황대겸", "scope": "required", "requirement_ids": ["R01", "R02"],
                     "actions": ["Run actual input", "Check changed condition"], "depends_on": [],
                     "allowed_execution_kinds": ["live_model", "live_service"]}
        self.cap = {"task_id": TASK, "requirement_ids": ["R01", "R02"],
                    "allowed_paths": ["packages/core"], "required_checks": ["core-test"]}
        self.policy = {"schema_version": 1, "repo": REPO, "pm_account": PM,
                       "tasks": {TASK: {"owner": OWNER, "scope": "required",
                                        "requirement_ids": ["R01", "R02"], "depends_on": []}},
                       "capabilities": {"core-cap": self.cap}, "independent_reviewers": [PM]}
        self.load()
        self.unit = self.make_unit()
        self.coverage = [self.make_coverage(r) for r in ("R01", "R02")]
        self.parent = self.make_parent()

    @property
    def registry(self):
        return TrustedReceiptRegistry(self.admissions)

    def read(self, ref):
        return self.store[(ref.path, ref.commit)]

    def put(self, value, kind=None, commit=MAIN, path=None, *, admit=True):
        self.serial += 1
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
        ref = ArtifactRef(path or f"control/{self.serial}.json", digest(raw), commit)
        self.store[(ref.path, ref.commit)] = raw
        if kind and admit:
            self.admissions[ref.sha256] = Admission(kind, commit)
        return ref

    def obj(self, ref):
        return json.loads(self.read(ref))

    def altered(self, ref, kind, **changes):
        value = self.obj(ref)
        value.update(changes)
        return self.put(value, kind, ref.commit)

    def load(self):
        self.requirements_ref = self.put(self.catalog, commit=BASE, path="harness/phase2/requirements.json")
        self.task_ref = self.put(self.task, commit=BASE, path=f"harness/phase2/tasks/{TASK}.json")
        self.policy_ref = self.put(self.policy, "policy", BASE)
        self.contract = load_contract(TASK, BASE, self.requirements_ref, self.task_ref, self.policy_ref,
                                      self.registry, self.read)

    def make_unit(self):
        records = {f"docs/{d}/세션/황대겸/{JOB}.md": self.put(b"Immutable own record\n", commit=HEAD,
                   path=f"docs/{d}/세션/황대겸/{JOB}.md").as_dict() for d in ("작업기록", "작업근거")}
        review = self.put({"schema_version": 1, "kind": "pm_review", "reviewer": PM,
                           "implementation_session_id": "impl-1", "reviewer_session_id": "review-1",
                           "outcome": "approve", "findings": [], "head": HEAD, "base": BASE}, "pm_review", HEAD)
        merge = self.put({"schema_version": 1, "kind": "github_merge", "repo": REPO, "author": OWNER,
                          "base_ref": "main", "pr_number": 100, "head": HEAD, "base": BASE,
                          "merged_commit": MAIN, "merged": True, "merge_parents": [BASE],
                          "changed_paths": ["packages/core/run.py", *records], "added_paths": list(records),
                          "path_modes": {p: "100644" for p in ["packages/core/run.py", *records]},
                          "session_record_refs": records}, "github_merge", HEAD)
        log = self.put(b"Actual fixture test stdout\n")
        postmerge = self.put({"schema_version": 1, "kind": "postmerge", "head": HEAD, "base": BASE,
                              "commit": MAIN, "result": "passed",
                              "checks": [{"id": "core-test", "passed": True, "output": log.as_dict()}]}, "postmerge")
        accepted = self.put({"schema_version": 1, "kind": "unit_acceptance", "job_id": JOB, "task_id": TASK,
                             "capability_id": "core-cap", "capability_fingerprint": self.contract.capabilities[0].fingerprint,
                             "owner": OWNER, "status": "accepted", "controller_receipt": "controller/direct-receipt",
                             "project_receipt": "project/direct-ack", "base": BASE, "head": HEAD,
                             "merged_commit": MAIN, "pr_number": 100, "implementation_session_id": "impl-1",
                             "review_sha256": review.sha256, "merge_sha256": merge.sha256,
                             "postmerge_sha256": postmerge.sha256}, "unit_acceptance")
        return AcceptedUnit(accepted, review, merge, postmerge)

    def make_coverage(self, requirement_id):
        common = {"schema_version": 1, "task_id": TASK, "requirement_id": requirement_id, "job_id": JOB,
                  "tested_commit": MAIN, "criterion_sha256": dict(self.contract.requirements)[requirement_id],
                  "contract_fingerprint": self.contract.fingerprint}
        code = self.put(b"Fixed source code\n", path="packages/core/run.py")
        source, inp, out, log = [self.put(v) for v in (b"Source bytes", b"Actual input", b"Actual output", b"Check log")]
        execution = self.put({**common, "kind": "requirement_execution", "execution_kind": "live_model",
                              "result": "pass", "implementation_session_id": "impl-1",
                              "observations": ["Observed actual tool call"], "limitations": ["Fixture only in tests"],
                              "code_versions": [code.as_dict()], "source_versions": [source.as_dict()],
                              "inputs": [inp.as_dict()], "outputs": [out.as_dict()],
                              "checks": [{"name": "changed-condition", "passed": True, "output": log.as_dict()}],
                              "model": {"model_id": "fixture", "revision": "fixed", "license": "test",
                                        "runtime": "unittest", "settings": {"temperature": 0}}}, "requirement_execution")
        acceptance = self.put({**common, "kind": "requirement_acceptance", "reviewer": PM,
                               "reviewer_session_id": "independent-coverage-1", "outcome": "approve", "findings": [],
                               "execution_sha256": execution.sha256}, "requirement_acceptance")
        return RequirementEvidence(requirement_id, JOB, execution, acceptance)

    def make_parent(self):
        return self.put({"schema_version": 1, "kind": "parent_acceptance", "task_id": TASK, "tested_commit": MAIN,
                         "actor": PM, "contract_fingerprint": self.contract.fingerprint,
                         "reviewer": PM, "reviewer_session_id": "parent-review-1",
                         "outcome": "approve", "findings": [], "requirement_ids": ["R01", "R02"],
                         "actions": [{"criterion_sha256": c, "outcome": "approve",
                                      "execution_sha256": self.coverage[i].execution.sha256}
                                     for i, c in enumerate(self.contract.action_criteria)]}, "parent_acceptance")

    def assessment(self, **changes):
        args = {"contract": self.contract, "accepted_units": [self.unit], "requirement_evidence": self.coverage,
                "parent_acceptance": self.parent, "dependencies": [], "registry": self.registry,
                "read": self.read, "current_main": MAIN}
        args.update(changes)
        return assess_parent(**args)

    def ack(self, task, completion_sha256, commit=MAIN):
        return self.put({"schema_version": 1, "kind": "snapshot_ack", "repo": REPO, "approved_commit": commit,
                         "outcome": "accepted", "project_receipt": "actual-project-ack",
                         "controller_receipt": "actual-controller-ack", "task_states": {task: "done"},
                         "completion_digests": {task: completion_sha256}}, "snapshot_ack", commit)


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def assertHeld(self, result):
        self.assertFalse(result.complete)
        self.assertIsNone(result.receipt)
        self.assertIsNotNone(result.next_unit_needed)

    def test_all_actual_chains_create_candidate_without_state_or_dependency_release(self):
        before = copy.deepcopy(self.f.store)
        result = self.f.assessment()
        self.assertTrue(result.complete, result.issues)
        self.assertEqual(result.receipt.sha256, digest(result.receipt.raw))
        self.assertEqual(self.f.store, before)
        self.assertFalse(result.receipt.payload["dependency_release_allowed"])
        self.assertEqual({c["requirement_id"] for c in result.receipt.payload["coverage"]}, {"R01", "R02"})

    def test_accepted_small_unit_and_verified_flags_never_cover_parent(self):
        unit = self.f.unit
        acceptance = self.f.altered(unit.acceptance, "unit_acceptance", verified=True, completes_task=True)
        result = self.f.assessment(accepted_units=[AcceptedUnit(acceptance, unit.review, unit.merge, unit.postmerge)],
                                   requirement_evidence=[], parent_acceptance=None)
        self.assertHeld(result)
        self.assertEqual(result.missing_requirements, ("R01", "R02"))

    def test_partial_coverage_identifies_remaining_requirement(self):
        result = self.f.assessment(requirement_evidence=self.f.coverage[:1])
        self.assertHeld(result)
        self.assertEqual(result.next_unit_needed.requirement_ids, ("R02",))

    def test_unadmitted_self_report_rejected_even_with_collector_verified_or_mail_flags(self):
        original = self.f.coverage[0]
        value = self.f.obj(original.execution)
        value.update(verified=True, collector="trusted_pm", email_sent=True)
        ref = self.f.put(value, "requirement_execution", admit=False)
        result = self.f.assessment(requirement_evidence=[RequirementEvidence("R01", JOB, ref, original.acceptance),
                                                       self.f.coverage[1]])
        self.assertHeld(result)
        self.assertIn("R01", result.missing_requirements)

    def test_tampered_bytes_wrong_kind_and_old_commit_rejected(self):
        for failure in ("bytes", "kind", "commit"):
            with self.subTest(failure=failure):
                f = Fixture()
                ref = f.coverage[0].execution
                if failure == "bytes":
                    f.store[(ref.path, ref.commit)] += b" "
                elif failure == "kind":
                    f.admissions[ref.sha256] = Admission("notification", ref.commit)
                else:
                    f.admissions[ref.sha256] = Admission("requirement_execution", BASE)
                self.assertHeld(f.assessment())

    def test_scope_other_owner_alias_and_nonregular_modes_rejected(self):
        for path, mode in (("packages/core-extra/a.py", "100644"),
                           ("docs/작업기록/세션/정이량/auto-test-001.md", "100644"),
                           ("packages/core/link", "120000"), ("packages/core/../other.py", "100644")):
            with self.subTest(path=path):
                f = Fixture()
                value = f.obj(f.unit.merge)
                value["changed_paths"].append(path)
                value["path_modes"][path] = mode
                merge = f.put(value, "github_merge", HEAD)
                acceptance = f.altered(f.unit.acceptance, "unit_acceptance", merge_sha256=merge.sha256)
                self.assertHeld(f.assessment(accepted_units=[AcceptedUnit(acceptance, f.unit.review, merge, f.unit.postmerge)]))

    def test_required_independent_review_exact_head_postmerge_and_logs(self):
        for failure in ("self-review", "findings", "wrong-head", "stale-postmerge", "missing-check", "bad-log"):
            with self.subTest(failure=failure):
                f = Fixture()
                review, post = f.unit.review, f.unit.postmerge
                if failure == "self-review":
                    review = f.altered(review, "pm_review", reviewer_session_id="impl-1")
                elif failure == "findings":
                    review = f.altered(review, "pm_review", findings=["Unresolved bug"])
                elif failure == "wrong-head":
                    review = f.altered(review, "pm_review", head=BASE)
                elif failure == "stale-postmerge":
                    post = f.altered(post, "postmerge", commit=HEAD)
                elif failure == "missing-check":
                    post = f.altered(post, "postmerge", checks=[])
                else:
                    log = ArtifactRef.parse(f.obj(post)["checks"][0]["output"])
                    f.store[(log.path, log.commit)] = b"Changed log"
                acceptance = f.altered(f.unit.acceptance, "unit_acceptance", review_sha256=review.sha256,
                                       postmerge_sha256=post.sha256)
                self.assertHeld(f.assessment(accepted_units=[AcceptedUnit(acceptance, review, f.unit.merge, post)]))

    def test_duplicate_identical_or_conflicting_units_and_coverage_hold(self):
        self.assertHeld(self.f.assessment(accepted_units=[self.f.unit, self.f.unit]))
        self.assertHeld(self.f.assessment(requirement_evidence=[*self.f.coverage, self.f.coverage[0]]))
        self.assertHeld(self.f.assessment(requirement_evidence=[*self.f.coverage, self.f.make_coverage("R01")]))

    def test_requirement_current_main_real_kind_criterion_and_review(self):
        for changes in ({"tested_commit": BASE}, {"execution_kind": "fixture"},
                        {"criterion_sha256": "f" * 64}, {"result": "fail"}, {"outputs": []}, {"model": {}}):
            with self.subTest(changes=changes):
                f = Fixture()
                old = f.coverage[0]
                execution = f.altered(old.execution, "requirement_execution", **changes)
                acceptance = f.altered(old.acceptance, "requirement_acceptance", execution_sha256=execution.sha256)
                self.assertHeld(f.assessment(requirement_evidence=[RequirementEvidence("R01", JOB, execution, acceptance),
                                                                  f.coverage[1]]))
        f = Fixture()
        old = f.coverage[0]
        acceptance = f.altered(old.acceptance, "requirement_acceptance", reviewer_session_id="impl-1")
        self.assertHeld(f.assessment(requirement_evidence=[RequirementEvidence("R01", JOB, old.execution, acceptance),
                                                          f.coverage[1]]))

    def test_source_acceptance_hash_policy_scope_and_catalog_are_mandatory(self):
        self.assertEqual(dict(self.f.contract.requirements)["R01"], criterion_digest("Execute R01"))
        for failure in ("missing-catalog", "duplicate-catalog", "scope", "owner", "requirement-link", "policy"):
            with self.subTest(failure=failure):
                f = Fixture()
                if failure == "missing-catalog":
                    f.catalog["requirements"].pop()
                elif failure == "duplicate-catalog":
                    f.catalog["requirements"].append(f.catalog["requirements"][0])
                elif failure == "scope":
                    f.task["scope"] = "proposed_extension"
                elif failure == "owner":
                    f.policy["tasks"][TASK]["owner"] = PM
                elif failure == "requirement-link":
                    next(r for r in f.catalog["requirements"] if r["id"] == "R01")["linked_task_ids"] = ["P2-OTHER"]
                else:
                    f.policy["tasks"][TASK]["requirement_ids"] = ["R01"]
                with self.assertRaises(CompletionError):
                    f.load()

    def test_changed_source_criteria_stale_execution_cannot_be_reused(self):
        f = self.f
        next(r for r in f.catalog["requirements"] if r["id"] == "R01")["acceptance"] = "Stricter accepted criterion"
        f.load()
        self.assertHeld(f.assessment())

    def test_parent_full_action_acceptance_cannot_be_missing_or_unrelated(self):
        for failure in ("missing", "duplicate", "unrelated", "self-review"):
            with self.subTest(failure=failure):
                f = Fixture()
                value = f.obj(f.parent)
                if failure == "missing":
                    value["actions"].pop()
                elif failure == "duplicate":
                    value["actions"].append(value["actions"][0])
                elif failure == "unrelated":
                    value["actions"][0]["execution_sha256"] = f.unit.acceptance.sha256
                else:
                    value["reviewer_session_id"] = "impl-1"
                self.assertHeld(f.assessment(parent_acceptance=f.put(value, "parent_acceptance")))

    def test_dependencies_need_protected_completion_and_exact_dual_snapshot_ack(self):
        f = self.f
        dependency = "P2-CORE-001"
        f.task["depends_on"] = [dependency]
        f.policy["tasks"][TASK]["depends_on"] = [dependency]
        f.load()
        f.unit = f.make_unit()
        f.coverage = [f.make_coverage(r) for r in ("R01", "R02")]
        f.parent = f.make_parent()
        self.assertHeld(f.assessment())
        completion = f.put({"schema_version": 1, "kind": "parent_completion", "task_id": dependency,
                            "decision": "complete", "actor": PM, "tested_commit": BASE}, "parent_completion", BASE)
        ack = f.ack(dependency, completion.sha256)
        deps = [DependencyEvidence(dependency, completion, ack)]
        self.assertTrue(f.assessment(dependencies=deps).complete)
        bad = f.altered(ack, "snapshot_ack", controller_receipt=None)
        self.assertHeld(f.assessment(dependencies=[DependencyEvidence(dependency, completion, bad)]))
        bad = f.ack(dependency, completion.sha256, BASE)
        self.assertHeld(f.assessment(dependencies=[DependencyEvidence(dependency, completion, bad)]))
        f.admissions.pop(completion.sha256)
        self.assertHeld(f.assessment(dependencies=deps))

    def test_release_requires_pm_publication_admission_and_fresh_matching_ack(self):
        f = self.f
        receipt = f.assessment().receipt
        ack = f.ack(TASK, receipt.sha256, PUBLISHED)
        self.assertFalse(dependency_release_allowed(receipt, PUBLISHED, ack, f.registry, f.read))
        f.admissions[receipt.sha256] = Admission("parent_completion", PUBLISHED)
        self.assertTrue(dependency_release_allowed(receipt, PUBLISHED, ack, f.registry, f.read))
        wrong = f.ack(TASK, "f" * 64, PUBLISHED)
        self.assertFalse(dependency_release_allowed(receipt, PUBLISHED, wrong, f.registry, f.read))
        old = f.ack(TASK, receipt.sha256)
        self.assertFalse(dependency_release_allowed(receipt, PUBLISHED, old, f.registry, f.read))

    def test_unsafe_refs_duplicate_json_keys_and_untrusted_registry_actor_fail(self):
        for path in ("/auth.json", "../auth.json", "C:/auth.json", "control\\auth.json", "control/./x.json"):
            with self.subTest(path=path), self.assertRaises(CompletionError):
                ArtifactRef(path, "a" * 64, MAIN)
        with self.assertRaises(CompletionError):
            TrustedReceiptRegistry({"a" * 64: Admission("pm_review", MAIN, OWNER)})
        f = self.f
        raw = b'{"schema_version":1,"kind":"parent_acceptance","kind":"notification"}'
        ref = f.put(raw, "parent_acceptance")
        self.assertHeld(f.assessment(parent_acceptance=ref))


if __name__ == "__main__":
    unittest.main()
