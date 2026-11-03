"""Validate the Codex hook protocol without executing proposed commands."""

import json
import os
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodexPatternTests(unittest.TestCase):
    def run_hook(self, name, payload):
        result = subprocess.run([sys.executable, str(ROOT / ".codex/hooks" / name)],
                                input=json.dumps(payload), text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_dangerous_git_text_is_denied(self):
        for command in ("git reset --hard HEAD", "git -C repo reset --hard",
                        "git clean -fd", "git clean --force", "git push --force-with-lease",
                        "git push -f origin main", "git push origin +HEAD:main"):
            for field in ("command", "cmd"):
                with self.subTest(command=command, field=field):
                    output = self.run_hook("git_safety.py", {"tool_input": {field: command}})
                    self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_ordinary_operations_continue(self):
        for command in ("git status", "git diff", "git commit -m lesson",
                        "git clean -nd", "Get-Content README.md"):
            self.assertEqual(self.run_hook("git_safety.py", {"tool_input": {"command": command}}), {})

    def test_notebook_patch_gets_context_but_prose_does_not(self):
        patch = "*** Begin Patch\n*** Update File: notebooks/lesson.ipynb\n@@\n-old\n+new\n*** End Patch"
        for args in (patch, {"command": patch}):
            output = self.run_hook("notebook_context.py", {"tool_input": args})
            self.assertIn("additionalContext", output["hookSpecificOutput"])
            self.assertNotIn("permissionDecision", output["hookSpecificOutput"])
        prose = "*** Begin Patch\n*** Add File: example.md\n+Read lesson.ipynb\n*** End Patch"
        self.assertEqual(self.run_hook("notebook_context.py", {"tool_input": {"command": prose}}), {})

    def test_invalid_inputs_follow_documented_error_behavior(self):
        for payload in (None, [], {"tool_input": {"command": 42}}):
            output = self.run_hook("git_safety.py", payload)
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertEqual(self.run_hook("notebook_context.py", payload), {})

    def test_configuration_and_agent_fields(self):
        config = tomllib.loads((ROOT / ".codex/config.toml").read_text())
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 2)
        for path in (ROOT / ".codex/agents").glob("*.toml"):
            agent = tomllib.loads(path.read_text())
            self.assertTrue(all(agent.get(key) for key in ("name", "description", "developer_instructions")))
            self.assertNotIn("sandbox_mode", agent)
        hooks = json.loads((ROOT / ".codex/hooks.json").read_text())
        for groups in hooks["hooks"].values():
            for group in groups:
                re.compile(group["matcher"])

    @unittest.skipUnless(os.name == "nt", "Windows command override")
    def test_actual_windows_launchers_from_subdirectory(self):
        config = json.loads((ROOT / ".codex/hooks.json").read_text())
        cases = {"PreToolUse": "git reset --hard HEAD",
                 "PostToolUse": "*** Begin Patch\n*** Update File: lesson.ipynb\n*** End Patch"}
        for event, command in cases.items():
            handler = config["hooks"][event][0]["hooks"][0]
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                     handler["commandWindows"]], cwd=ROOT / "notebooks",
                                    input=json.dumps({"tool_input": {"command": command}}),
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"], event)


if __name__ == "__main__":
    unittest.main()
