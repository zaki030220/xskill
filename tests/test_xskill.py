#!/usr/bin/env python3
"""Unit tests for xskill_core and xskill_mcp."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import xskill_mcp  # noqa: E402
from xskill_core import XSkillManager, quick_search  # noqa: E402


class TestXSkillCore(unittest.TestCase):
    def test_starter_skills_discovered_both_formats(self):
        mgr = XSkillManager(xskill_root=REPO_ROOT)
        entries = mgr.list_entries(mem_type="skill")["global"]
        names = {e["name"] for e in entries}
        # Folder-based skills
        self.assertIn("anti-defensive-writing", names)
        self.assertIn("figure-creation-standards", names)
        # Single-file skills
        self.assertIn("paper-claim-audit", names)
        self.assertIn("minimal-code-ladder", names)
        self.assertEqual(len(names), 9)

    def test_search_hits_expected_skill(self):
        res = quick_search(
            "论文里的数字和原始结果文件对不上，怎么逐数字核对四舍五入和配置不符",
            xskill_root=REPO_ROOT,
        )
        hit_names = [h["name"] for h in res["skills"]]
        self.assertIn("paper-claim-audit", hit_names)

    def test_project_level_boost_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = XSkillManager(xskill_root=tmp, project="demo_proj")
            mgr.create_skill(
                name="demo-folder-skill",
                description="Custom project workflow for survival analysis and excel modeling",
                domain="demo",
                tools=["python"],
                content="## Steps\n1. Run analysis.",
                project="demo_proj",
                tags=["survival", "excel"],
                folder=True,
            )
            idx = mgr.build_index()
            self.assertIn("demo_proj", idx["projects"])
            self.assertIn("demo-folder-skill", idx["projects"]["demo_proj"])

            entry = mgr.read_entry("demo-folder-skill", project="demo_proj")
            self.assertIsNotNone(entry)
            self.assertTrue(entry["path"].endswith("SKILL.md"))

            res = mgr.search("Custom project workflow for survival analysis and excel modeling", project="demo_proj")
            self.assertEqual(res["skills"][0]["name"], "demo-folder-skill")
            self.assertEqual(res["skills"][0]["source"], "project")


class TestXSkillMCP(unittest.TestCase):
    def test_mcp_stdio_roundtrip_and_path_lock(self):
        reqs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "xskill_search",
                    "arguments": {"query": "论文里的数字和原始结果文件对不上，怎么逐数字核对"},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "xskill_read", "arguments": {"path": "/etc/passwd"}},
            },
        ]
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "xskill_mcp.py"), "--root", str(REPO_ROOT)],
            input="\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n",
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [json.loads(line) for line in proc.stdout.strip().splitlines()]
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0]["result"]["serverInfo"]["name"], xskill_mcp.SERVER_NAME)
        self.assertEqual(len(lines[1]["result"]["tools"]), 2)

        search_payload = json.loads(lines[2]["result"]["content"][0]["text"])
        hit_names = [h["name"] for h in search_payload["hits"]]
        self.assertIn("paper-claim-audit", hit_names)

        # Path lock must reject /etc/passwd
        self.assertTrue(lines[3]["result"]["isError"])
        self.assertIn("access denied", lines[3]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
