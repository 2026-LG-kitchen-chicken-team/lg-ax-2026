"""Planning writes need a bounded model budget; timeout never retries a write."""
import unittest

import httpx
from lgax_core.errors import DomainError
from lgax_mcp.workspace_client import WorkspaceClient


class WorkspacePlanningTimeoutTests(unittest.TestCase):
    def test_planning_write_waits_longer_but_never_retries_uncertain_write(self):
        calls = []

        def route(request):
            calls.append(request)
            raise httpx.ReadTimeout("uncertain write", request=request)

        client = WorkspaceClient("http://127.0.0.1:18879", "x" * 48, transport=httpx.MockTransport(route))
        # Contract-valid development request; no endpoint/model setting in body.
        import json
        from pathlib import Path
        request = json.loads((Path(__file__).resolve().parents[1] /
                              "evals/core-planning/examples/fridge.input.json").read_text("utf-8"))["request"]
        with self.assertRaises(DomainError):
            client.create_run("project-example", request)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].extensions["timeout"]["read"], 300)
        with self.assertRaises(DomainError):
            client.list_runs("project-example")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].extensions["timeout"]["read"], 15)
