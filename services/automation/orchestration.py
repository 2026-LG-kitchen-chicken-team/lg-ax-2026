"""Trusted live adapter for the pinned backlog and private, report-only mail.

Only the deployed broker instantiates this adapter. Repository plans are not
releases: their copied bytes and capability definitions must match pinned policy.
The caller already holds the PM process lock; no model or worker supplies receipts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.automation.backlog import (
    append_progress,
    collector_candidates,
    load_backlog,
    ready_units,
    verify_progress,
)
from services.automation.isolation import regular_file
from services.automation.pm import PMError, fingerprint, protected_path
from services.automation.state import REPO
from services.automation.worker import write_json


class Orchestration:
    def __init__(self, broker):
        self.broker = broker
        options = broker.config.get("backlog")
        self.plan = None
        if options:
            self.plan = load_backlog(protected_path(options["path"]), options["sha256"],
                                     registered_tasks=broker.policy["tasks"])
            for key, capability in self.plan["capabilities"].items():
                actual = broker.policy["capabilities"].get(key)
                if not actual or any(actual.get(field) != capability.get(field) for field in (
                        "task_id", "requirement_ids", "allowed_paths", "acceptance",
                        "validation_commands", "required_checks", "shared_resources", "title", "purpose")):
                    raise PMError("fixed backlog and deployed capability contract differ")
            verify_progress(self.plan, broker.state.get("backlog_ledger", []))
        self.mail = None
        mail = broker.config.get("mail")
        if mail:
            from services.automation.mail_broker import MailBroker
            from services.automation.mail_connector import CodexGmailTransport

            raw = regular_file(protected_path(mail["path"]))
            if hashlib.sha256(raw).hexdigest() != mail["sha256"]:
                raise PMError("fixed private mail configuration changed")
            config = json.loads(raw)
            if config.get("transport") != "codex_appserver":
                raise PMError("live orchestration requires the verified CLI mail transport")
            binary = regular_file(Path(config["codex_executable"]), maximum=512 * 1024 * 1024)
            if hashlib.sha256(binary).hexdigest() != config.get("codex_executable_sha256"):
                raise PMError("pinned CLI mail executable changed")
            transport = CodexGmailTransport(executable=config["codex_executable"],
                                           workspace=config["connector_workspace"], timeout_seconds=45)
            self.mail = MailBroker(config, gmail=transport)
        self._mail_checked = False
        self._mail_poll_at = 0.0
        self.parent = None
        self._parent_key = None
        self._parent_result = None
        if self.plan and broker.config.get("parent_completion_enabled") is True:
            from services.automation.completion_publish import CompletionPublisher
            from services.automation.parent_collector import ParentCollector

            self.parent = ParentCollector(broker, publisher=CompletionPublisher(broker))

    def _event(self, cap_id, suffix, event, receipt):
        broker = self.broker
        event_id = event + "-" + fingerprint({"cap": cap_id, "id": suffix})[:48]
        broker.state["backlog_ledger"] = append_progress(self.plan,
            broker.state.get("backlog_ledger", []), event_id=event_id,
            capability_id=cap_id, event=event, receipt=receipt)
        broker.save()

    def synchronize(self, observation, *, collect=False):
        if not self.plan:
            return
        jobs = {row["job_id"]: row for row in observation["jobs"]}
        state = verify_progress(self.plan, self.broker.state.get("backlog_ledger", []))
        # Old accepted pilot/revision jobs seed the ledger from the direct queue,
        # actual GitHub merge, and protected independent postmerge proof.
        latest = {unit["capability_id"]: unit for unit in self.broker.state["units"].values()
                  if not unit.get("superseded_by") and unit["job_id"] in jobs}
        for unit in latest.values():
            cap_id = unit["capability_id"]
            if cap_id not in self.plan["capabilities"] or unit.get("superseded_by"):
                continue
            job = jobs.get(unit["job_id"])
            if not job:
                continue
            if unit.get("superseded_by"):
                continue
            prior = state.get(cap_id)
            if prior in {"accepted", "parent_verified", "blocked"}:
                continue
            if prior is None:
                self._event(cap_id, unit["job_id"], "released", {"base_commit": unit["base_commit"]})
                prior = "released"
            if prior in {"released", "unblocked"}:
                self._event(cap_id, unit["job_id"], "assigned", {
                    "base_commit": unit["base_commit"], "job_id": unit["job_id"]})
            if unit.get("revision_requested"):
                if prior != "unblocked":
                    self._event(cap_id, unit["job_id"], "blocked", {
                        "reason": "Independent exact-head PM correction requires a new bounded job",
                        "operator_reference": "protected-revision:" + unit["job_id"]})
                    self._event(cap_id, unit["job_id"], "unblocked", {
                        "reason": "Recorded PM correction releases this fixed capability only",
                        "operator_reference": "protected-revision:" + unit["job_id"]})
                    state = verify_progress(self.plan, self.broker.state["backlog_ledger"])
                continue
            if job.get("status") in {"blocked", "orphaned"}:
                self._event(cap_id, unit["job_id"], "blocked", {
                    "reason": "Actual queue blocked/orphaned; no automatic retry",
                    "operator_reference": "controller-job:" + unit["job_id"]})
            elif unit.get("reconciled") and job.get("status") == "accepted":
                actual = self.broker.github.request("GET", f"repos/{REPO}/pulls/{unit['pr_number']}")
                cap_fp = fingerprint(self.broker.policy["capabilities"][cap_id])
                proof = next((p for p in self.broker.state["proofs"].values()
                    if p.get("verified") is True and p.get("collector") == "trusted_pm"
                    and p.get("result") == "passed" and p.get("commit") == actual.get("merge_commit_sha")
                    and p.get("head") == unit.get("head") and p.get("base") == unit["base_commit"]
                    and p.get("capability_fingerprint") == cap_fp), None)
                if not actual.get("merged") or actual.get("head", {}).get("sha") != unit.get("head") or not proof:
                    raise PMError("accepted legacy unit lacks direct merge/postmerge collection")
                self._event(cap_id, unit["job_id"], "accepted", {
                    "base_commit": unit["base_commit"], "merge_commit": actual["merge_commit_sha"],
                    "integration_evidence_sha256": proof["evidence_sha256"], "queue_status": "accepted"})
            state = verify_progress(self.plan, self.broker.state["backlog_ledger"])
        result = ready_units(self.plan, observation, self.broker.state.get("backlog_ledger", []))
        observation["capabilities_ready"] = [key for key in result["ready"]
                                              if key in self.broker._released_capabilities()]
        observation["backlog"] = {"plan_digest": result["plan_digest"], "waiting": result["waiting"],
                                  "parents_needing_collection": collector_candidates(self.plan,
                                      self.broker.state.get("backlog_ledger", []))}
        write_json(self.broker.state_dir / "backlog-observation.json", observation["backlog"])
        if self.parent and collect and self.broker.enabled():
            selected = tuple(sorted({unit["task_id"] for unit in latest.values() if unit.get("reconciled")}))
            key = fingerprint({"main": observation["main_commit"], "units": latest,
                               "store": self.parent.store.index})
            # Current-head and protected evidence changes wake collection;
            # unchanged polling does not rerun product tests or model reviews.
            pending = self._parent_result and any(row.get("publication_pending") for row in
                                                  self._parent_result["tasks"].values())
            if selected and (key != self._parent_key or pending):
                self._parent_result = self.parent.tick(observation, task_ids=selected)
                self._parent_key = fingerprint({"main": observation["main_commit"], "units": latest,
                                               "store": self.parent.store.index})
            if self._parent_result:
                observation["parent_completion"] = self._parent_result

    def mail_tick(self, *, poll=True):
        import time

        if self.mail is None:
            return []
        if not self._mail_checked:
            self.mail.preflight()
            self._mail_checked = True
        if poll and time.monotonic() - self._mail_poll_at >= 60:
            self.mail.poll_replies(limit=20)
            self._mail_poll_at = time.monotonic()
        return self.mail.observation_events(limit=20)

    def notify(self, outbox):
        if self.mail is None:
            return None
        self.mail.preflight()
        receipt = self.mail.deliver(outbox)
        write_json(Path(outbox).with_suffix(".receipt.json"), receipt)
        return "sent_verified" if receipt.get("verified_sent") else "unknown"

    def close(self):
        if self.mail:
            self.mail.gmail.close()
