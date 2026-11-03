"""Add a focused validation reminder after a notebook patch; never run a kernel."""

import json
import re
import sys


def check(event):
    args = event.get("tool_input", {})
    command = args.get("command", args.get("patch", "")) if isinstance(args, dict) else args
    if not isinstance(command, str):
        return {}
    paths = re.findall(r"^\*\*\* (?:Add File|Update File|Move to): (.+)$", command, re.MULTILINE)
    if any(path.strip().lower().endswith(".ipynb") for path in paths):
        return {"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "Notebook changed. Check notebooks/AGENTS.md and the import-layout tests. Keep imports in the first code cell. Report static checks separately from kernel execution; this hook ran neither.",
        }}
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, AttributeError):
        result = {}
    print(json.dumps(result))
