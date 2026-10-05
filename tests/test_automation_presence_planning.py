"""Alive metadata cannot create billable planning churn, but outages stay visible."""
import unittest
from copy import deepcopy

from services.automation.pm import AutonomousPM, fingerprint, stable_observation
from tests.test_automation_pm import observation, policy


class PresencePlanningTests(unittest.TestCase):
    def test_model_context_can_see_outage_without_private_transport_metadata(self):
        pm = object.__new__(AutonomousPM)
        pm.policy = policy()
        facts = observation()
        facts["worker_presence"] = {"jeongiryang": {"presence": "stale", "engine": "codex",
            "phase": "idle", "sequence": 90, "instance_id": "private-instance", "last_seen_at": 1000}}
        context = pm._context(facts)
        self.assertEqual(context["worker_presence"]["jeongiryang"], {
            "presence": "stale", "engine": "codex", "phase": "idle"})
        self.assertIn("never readiness", context["worker_presence_limit"])

    def test_routine_heartbeats_do_not_change_planning_fingerprint(self):
        original = {"worker_presence": {"choigilung": {"presence": "online", "registered": True,
            "phase": "idle", "job_id": None, "engine": "claude", "runtime_version": "presence-v1",
            "runtime_sha256": "a" * 64, "sequence": 1, "instance_id": "old-session",
            "last_seen_at": 1000, "reported_at": 999, "age_seconds": 1}}}
        next_signal = deepcopy(original)
        next_signal["worker_presence"]["choigilung"].update(sequence=2, last_seen_at=1030,
            reported_at=1029, age_seconds=2, instance_id="another-session")
        self.assertEqual(fingerprint(stable_observation(original)), fingerprint(stable_observation(next_signal)))
        self.assertEqual(original["worker_presence"]["choigilung"]["sequence"], 1)

    def test_outage_phase_and_runtime_change_remain_actionable(self):
        original = {"worker_presence": {"jeongiryang": {"presence": "online", "phase": "idle",
            "job_id": None, "runtime_sha256": "a" * 64, "engine": "codex"}}}
        for update in ({"presence": "stale"}, {"phase": "validating", "job_id": "auto-active"},
                       {"runtime_sha256": "b" * 64}, {"engine": "claude"}):
            changed = deepcopy(original)
            changed["worker_presence"]["jeongiryang"].update(update)
            self.assertNotEqual(fingerprint(stable_observation(original)), fingerprint(stable_observation(changed)))


if __name__ == "__main__":
    unittest.main()
