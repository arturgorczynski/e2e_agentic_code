"""Add validation context after notebook edits without executing a kernel."""

import json
import re
import sys


def check(event):
    args = event.get("tool_input", {})
    paths = []
    if isinstance(args, dict):
        paths = [args.get("file_path", ""), args.get("notebook_path", "")]
        command = args.get("command", args.get("patch", ""))
    else:
        command = args
    if isinstance(command, str):
        paths += re.findall(r"^\*\*\* (?:Add File|Update File|Move to): (.+)$", command, re.MULTILINE)
    if any(isinstance(path, str) and path.strip().lower().endswith(".ipynb") for path in paths):
        return {"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "Notebook changed. Follow root AGENTS.md: keep imports in the first code cell and run the relevant import-layout checks. This reminder has not executed a notebook or verified its output.",
        }}
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, AttributeError):
        result = {}
    print(json.dumps(result))
