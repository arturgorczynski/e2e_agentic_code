"""Demonstrate a narrow PreToolUse rule for recognizable destructive Git commands."""

import json
import re
import sys


def check(event):
    args = event.get("tool_input", {})
    command = args.get("command", args.get("cmd", ""))
    if not isinstance(command, str):
        raise ValueError("Expected a text command.")
    # This is a text heuristic, not a shell parser or a security boundary.
    for segment in re.split(r"[;|&\r\n]", command):
        if not re.search(r"\bgit(?:\.exe)?\s", segment, re.IGNORECASE):
            continue
        dangerous = (
            re.search(r"\breset\s+[^;]*--hard\b", segment)
            or re.search(r"\bclean\s+[^;]*(?:--force\b|(?<!\S)-[A-Za-z]*f[A-Za-z]*\b)", segment)
            or re.search(r"\bpush\s+[^;]*(?:--force(?:-with-lease|-if-includes)?\b|(?<!\S)-[A-Za-z]*f\b|(?<!\S)\+\S+)", segment)
        )
        if dangerous:
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Repository example blocks destructive Git reset, clean, and force-push commands. Inspect git status and git diff first; this hook has no approval bypass.",
            }}
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, AttributeError):
        result = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Invalid Git hook input.",
        }}
    print(json.dumps(result))
