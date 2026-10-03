"""Verify real SDK stdio protocol and MCP read-only annotations."""

import asyncio
import importlib.util
from pathlib import Path
import unittest

from lgax_mcp.server import create_mcp


class McpTests(unittest.TestCase):
    def test_stdio_initialize_list_and_call(self):
        path = Path(__file__).resolve().parents[1] / "scripts/smoke_mcp.py"
        spec = importlib.util.spec_from_file_location("smoke_mcp", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = asyncio.run(module.smoke_stdio())
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["analysis_implemented"])

    def test_only_three_readonly_tools_exposed(self):
        tools = asyncio.run(create_mcp().list_tools())
        self.assertEqual({tool.name for tool in tools}, {"list_products", "search_evidence", "get_evidence"})
        for tool in tools:
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.destructiveHint)
            self.assertFalse(tool.annotations.openWorldHint)


if __name__ == "__main__":
    unittest.main()
