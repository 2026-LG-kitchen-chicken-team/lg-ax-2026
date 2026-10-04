"""Queue/worker ownership contracts using isolated local Git and inert packets."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.automation import worker
from services.automation.state import Store


class QueueWorkerContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root / "queue.sqlite3", {})
        self.store.formal_snapshot("jeongiryang", {"approved_commit": "a" * 40, "approval_reference": "fixture PM",
                                                   "tasks": {"T": {"owner": "unknownamed", "status": "ready"}}})
        self.store.mode("jeongiryang", "on")
        self.store.mode("unknownamed", "on", "unknownamed")

    def packet(self, job_id, code_path):
        item = {"job_id": job_id, "owner": "unknownamed", "task_id": "T", "assignment_id": "fixture-" + job_id,
                "base_commit": "a" * 40, "title": "Small approved unit", "prompt": "fixture request",
                "approval_reference": "fixture PM", "approved": True, "kind": "implementation",
                "allowed_paths": [code_path], "validation_commands": [["python", "-m", "unittest"]]}
        item["allowed_paths"] += worker.session_records(item, item["owner"])
        return item

    def submit(self, job):
        capability = self.store.authorize_publish("unknownamed", job["job_id"], job["lease_token"])
        self.store.finish("unknownamed", job["job_id"], {
            "lease_token": job["lease_token"], "publish_token": capability["publish_token"],
            "outcome": "review_requested", "summary": "fixture individual validation",
            "pr_url": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/99", "head_commit": "b" * 40})

    def test_review_pending_keeps_code_lock_but_distinct_job_records_allow_next_disjoint_unit(self):
        for job_id, path in (("UNIT1", "packages/core/a.py"), ("UNIT2", "packages/core/b.py")):
            self.store.register("jeongiryang", self.packet(job_id, path))
        first = self.store.claim("unknownamed")["job"]
        self.submit(first)
        second = self.store.claim("unknownamed")["job"]
        self.assertEqual(second["job_id"], "UNIT2")
        for record in worker.session_records(second, second["owner"]):
            self.assertTrue(worker.allowed_path(record, second["allowed_paths"], second["owner"]))
        self.assertEqual(self.store.status("jeongiryang")["jobs"][0]["status"], "review_requested")

    def test_pending_review_still_blocks_overlapping_code_even_with_distinct_records(self):
        for job_id in ("UNIT1", "UNIT2"):
            self.store.register("jeongiryang", self.packet(job_id, "packages/core/a.py"))
        self.submit(self.store.claim("unknownamed")["job"])
        self.assertIsNone(self.store.claim("unknownamed")["job"])

    def test_retry_creates_a_new_real_git_branch_and_keeps_previous_worktree(self):
        repo = self.root / "clone"
        repo.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(self.root / "empty.config"), "GIT_CONFIG_NOSYSTEM": "1"}
        (self.root / "empty.config").touch()

        def command(*args):
            return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True,
                                  check=True, timeout=10).stdout.decode().strip()

        command("init", "-q")
        command("config", "user.name", "Fixture")
        command("config", "user.email", "fixture@example.invalid")
        (repo / "README.md").write_text("isolated fixture\n", encoding="utf-8")
        command("add", ".")
        command("commit", "-qm", "fixture base")
        base = command("rev-parse", "HEAD")
        command("remote", "add", "origin", "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026.git")
        command("update-ref", "refs/remotes/origin/main", base)
        config = worker.WorkerConfig(account="unknownamed", repository=repo, state_dir=self.root / "private-state",
            codex_home=self.root / "private-codex", controller_url="http://127.0.0.1:18871",
            token_file=self.root / "private.token", isolation_acknowledged=True)
        original_git = worker.git

        def local_only_git(config, argv, **kwargs):
            if argv[:1] == ["fetch"]:
                return ""  # No network: the approved remote tracking ref is already pinned above.
            return original_git(config, argv, **kwargs)

        job = {**self.packet("RETRY", "packages/core/a.py"), "base_commit": base, "lease_token": "fixture"}
        with patch.object(worker, "git", side_effect=local_only_git), patch.dict(os.environ, env):
            run1 = self.root / "attempt1"
            run2 = self.root / "attempt2"
            run1.mkdir()
            run2.mkdir()
            first = worker.prepare_worktree(config, {**job, "attempt": 1, "lease_generation": 1}, run1)
            second = worker.prepare_worktree(config, {**job, "attempt": 2, "lease_generation": 3}, run2)
        self.assertNotEqual(first[1], second[1])
        self.assertTrue((first[0] / "README.md").is_file())
        self.assertTrue((second[0] / "README.md").is_file())
        branches = command("branch", "--format=%(refname:short)").splitlines()
        self.assertIn(first[1], branches)
        self.assertIn(second[1], branches)


if __name__ == "__main__":
    unittest.main()
