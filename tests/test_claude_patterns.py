"""Exercise Claude approval hooks with synthetic events and no model calls."""

import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("joke_hook", ROOT / ".claude/hooks/approve_jokes.py")
JOKES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JOKES)


class ClaudePatternTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ROOT / ".tmp" / ("hook-tests-" + uuid4().hex)
        self.fixture.mkdir(parents=True)
        self.addCleanup(self.cleanup_fixture)

    def cleanup_fixture(self):
        if self.fixture.resolve().parent != (ROOT / ".tmp").resolve():
            raise ValueError("Fixture must stay inside the checkout's .tmp directory.")
        shutil.rmtree(self.fixture)

    def run_hook(self, name, event):
        result = subprocess.run([sys.executable, str(ROOT / ".claude/hooks" / name)],
                                input=json.dumps(event), text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_commits_and_deletions_ask_in_both_shells(self):
        commands = ["git commit -m lesson", "git -C repo commit --amend",
                    "git commit --dry-run", "git commit-tree HEAD",
                    "rm example.txt", "Remove-Item example.txt", "del example.txt",
                    "git clean -fd", "git rm example.txt",
                    "python -c \"import os; os.remove('example.txt')\"",
                    "[System.IO.File]::Delete('example.txt')",
                    "apply_patch '*** Delete File: example.txt'"]
        for tool in ("Bash", "PowerShell"):
            for command in commands:
                with self.subTest(tool=tool, command=command):
                    output = self.run_hook("ask_before_change.py", {"tool_name": tool, "tool_input": {"command": command}})
                    self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_read_commands_and_normal_edits_continue(self):
        for command in ("git status", "git diff", "Get-Content README.md", "python -m unittest"):
            self.assertEqual(self.run_hook("ask_before_change.py", {
                "tool_name": "Bash", "tool_input": {"command": command}}), {})
        self.assertEqual(self.run_hook("ask_before_change.py", {
            "tool_name": "Write", "tool_input": {"file_path": "README.md", "content": "Updated"}}), {})

    def test_recognizable_connector_changes_ask(self):
        for tool in ("mcp__git__create_commit", "mcp__fs__delete_file", "mcp__fs__remove_file"):
            output = self.run_hook("ask_before_change.py", {"tool_name": tool, "tool_input": {}})
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_invalid_events_deny(self):
        for name in ("ask_before_change.py", "approve_jokes.py"):
            for event in (None, [], {}, {"tool_name": "Write", "tool_input": {"content": 42}}):
                output = self.run_hook(name, event)
                if name == "ask_before_change.py" and isinstance(event, dict) and event.get("tool_name") == "Write":
                    self.assertEqual(output, {})
                else:
                    self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_joke_hook_asks_without_writing_and_rejects_other_paths(self):
        base = self.fixture.resolve()
        target = base / "jokes.txt"
        event = {"tool_name": "Write", "cwd": str(base),
                 "tool_input": {"file_path": str(target),
                                "content": "\n".join(f"{i}. Fresh test joke." for i in range(1, 6))}}
        with patch.object(JOKES, "ROOT", base), patch.object(JOKES, "TARGET", target):
            self.assertEqual(JOKES.check(event)["hookSpecificOutput"]["permissionDecision"], "ask")
            self.assertFalse(target.exists())
            event["tool_input"]["file_path"] = "nested/jokes.txt"
            self.assertEqual(JOKES.check(event)["hookSpecificOutput"]["permissionDecision"], "deny")
            event["tool_input"]["file_path"] = "jokes.txt"
            target.write_text("Existing user content")
            self.assertEqual(JOKES.check(event)["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertEqual(target.read_text(), "Existing user content")

    def test_joke_content_and_tool_are_validated(self):
        base = self.fixture.resolve()
        with patch.object(JOKES, "ROOT", base), patch.object(JOKES, "TARGET", base / "jokes.txt"):
            for content in ("", "1. One joke", "1.\n2.\n3.\n4.\n5."):
                event = {"tool_name": "Write", "cwd": str(base),
                         "tool_input": {"file_path": "jokes.txt", "content": content}}
                self.assertEqual(JOKES.check(event)["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertEqual(JOKES.check({"tool_name": "Bash"})["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_project_launcher_is_direct_argv_and_runs_from_subdirectory(self):
        config = json.loads((ROOT / ".claude/settings.json").read_text())
        handler = config["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(handler["onFailure"], "block")
        args = [arg.replace("${CLAUDE_PROJECT_DIR}", str(ROOT)) for arg in handler["args"]]
        result = subprocess.run([handler["command"], *args], cwd=ROOT / "notebooks",
                                input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit --dry-run"}}),
                                text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")


if __name__ == "__main__":
    unittest.main()
