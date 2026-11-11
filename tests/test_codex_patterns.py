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
        for command in ("git status", "git diff", "git log -3",
                        "git clean -nd", "Get-Content README.md"):
            self.assertEqual(self.run_hook("git_safety.py", {"tool_input": {"command": command}}), {})

    def test_staging_commit_creation_and_publication_are_denied(self):
        for command in ("git add .", "git stage lesson.py", "git commit -m lesson",
                        "git commit-tree HEAD", "git update-index --add lesson.py",
                        "git update-ref refs/heads/demo HEAD", "git write-tree",
                        "git hash-object -w lesson.py", "git merge origin/main",
                        "git rebase main", "git cherry-pick HEAD", "git revert HEAD",
                        "git am change.patch", "git push origin main",
                        "git -C repo commit -m lesson", "git -c user.name=Demo add ."):
            for field in ("command", "cmd"):
                with self.subTest(command=command, field=field):
                    output = self.run_hook("git_safety.py", {"tool_input": {field: command}})
                    self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_notebook_patch_gets_context_but_prose_does_not(self):
        patch = "*** Begin Patch\n*** Update File: notebooks/lesson.ipynb\n@@\n-old\n+new\n*** End Patch"
        for args in (patch, {"command": patch}):
            output = self.run_hook("notebook_context.py", {"tool_input": args})
            self.assertIn("additionalContext", output["hookSpecificOutput"])
            self.assertNotIn("permissionDecision", output["hookSpecificOutput"])
        prose = "*** Begin Patch\n*** Add File: example.md\n+Read lesson.ipynb\n*** End Patch"
        self.assertEqual(self.run_hook("notebook_context.py", {"tool_input": {"command": prose}}), {})

    def test_deletion_denial_covers_shell_patch_and_connector(self):
        for command in ("rm example.txt", "Remove-Item example.txt", "del example.txt",
                        "git rm example.txt", "git clean -nd", "[IO.File]::Delete('example.txt')",
                        "python -c \"import os; os.unlink('example.txt')\"",
                        "python -c \"import shutil; shutil.rmtree('example')\""):
            for tool in ("Bash", "PowerShell", "exec_command"):
                for field in ("command", "cmd"):
                    with self.subTest(tool=tool, command=command, field=field):
                        result = self.run_hook("block_delete.py", {"tool_name": tool, "tool_input": {field: command}})
                        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        for header in ("*** Delete File: example.txt", "*** Move to: moved.txt"):
            for args in (header, {"command": header}, {"patch": header}):
                result = self.run_hook("block_delete.py", {"tool_name": "apply_patch", "tool_input": args})
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        for tool in ("mcp__fs__delete_file", "mcp__fs__remove_file"):
            result = self.run_hook("block_delete.py", {"tool_name": tool, "tool_input": {"path": "example.txt"}})
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_joke_writes_are_denied_without_changing_the_file(self):
        target = ROOT / "jokes.txt"
        before = target.read_bytes() if target.exists() else None
        events = [
            {"tool_name": "Write", "tool_input": {"file_path": "jokes.txt", "content": "1. Joke"}},
            {"tool_name": "mcp__fs__write_file", "tool_input": {"path": str(target), "content": "jokes"}},
            {"tool_name": "apply_patch", "tool_input": "*** Add File: jokes.txt\n+1. Joke"},
            {"tool_name": "apply_patch", "tool_input": {"command": "*** Update File: jokes.txt\n@@\n+new"}},
            {"tool_name": "apply_patch", "cwd": str(ROOT / "notebooks"), "tool_input": {"command": "*** Add File: ../jokes.txt\n+1. Joke"}},
        ]
        for command in ("Set-Content jokes.txt 'jokes'", "echo jokes > jokes.txt",
                        "Copy-Item sample.txt jokes.txt", "New-Item jokes.txt",
                        "python -c \"from pathlib import Path; Path('jokes.txt').write_text('jokes')\"",
                        "python -c \"open('jokes.txt', 'w').write('jokes')\""):
            events.append({"tool_name": "Bash", "tool_input": {"command": command}})
        for event in events:
            event.setdefault("cwd", str(ROOT))
            with self.subTest(event=event):
                result = self.run_hook("block_jokes_write.py", event)
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(target.read_bytes() if target.exists() else None, before)

    def test_file_guards_allow_reads_and_unrelated_edits(self):
        events = [
            {"tool_name": "Bash", "tool_input": {"command": "Get-Content jokes.txt"}},
            {"tool_name": "Bash", "tool_input": {"command": "git status"}},
            {"tool_name": "Write", "tool_input": {"file_path": "README.md", "content": "Explain jokes.txt"}},
            {"tool_name": "apply_patch", "tool_input": {"command": "*** Add File: README.md\n+Explain jokes.txt"}},
            {"tool_name": "mcp__fs__read_file", "tool_input": {"path": "jokes.txt"}},
        ]
        for name in ("block_delete.py", "block_jokes_write.py"):
            for event in events:
                with self.subTest(hook=name, event=event):
                    self.assertEqual(self.run_hook(name, event), {})

    def test_file_guards_deny_invalid_input(self):
        for name in ("block_delete.py", "block_jokes_write.py"):
            for event in (None, [], {}, {"tool_name": "Bash", "tool_input": {"command": 42}}):
                with self.subTest(hook=name, event=event):
                    result = self.run_hook(name, event)
                    self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

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
            for group in config["hooks"][event]:
                handler = group["hooks"][0]
                probe = command
                if "block_delete.py" in handler["commandWindows"]:
                    probe = "Remove-Item disposable-demo.txt"
                if "block_jokes_write.py" in handler["commandWindows"]:
                    probe = "Set-Content jokes.txt 'demo'"
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                         handler["commandWindows"]], cwd=ROOT / "notebooks",
                                        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": probe}}),
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"], event)


if __name__ == "__main__":
    unittest.main()
