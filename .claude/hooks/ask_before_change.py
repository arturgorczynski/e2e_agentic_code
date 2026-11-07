"""Ask for native approval of recognizable deletions; commits continue normally."""

import json
import re
import sys


def decision(value, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": value,
                                   "permissionDecisionReason": reason}}


def check(event):
    tool = event["tool_name"]
    args = event["tool_input"]
    if not isinstance(tool, str) or not isinstance(args, dict):
        raise ValueError("Expected tool name and object input.")
    if re.search(r"(?:delete_file|remove_file)", tool, re.IGNORECASE):
        return decision("ask", "Review the proposed file deletion.")
    if tool not in {"Bash", "PowerShell"}:
        return {}
    command = args.get("command", args.get("cmd", ""))
    if not isinstance(command, str):
        raise ValueError("Expected text command.")
    # These text patterns demonstrate event handling, not a complete shell parser.
    deletion = any(re.search(pattern, command, re.IGNORECASE) for pattern in (
        r"\b(?:rm|rmdir|rd|Remove-Item|ri|del|erase|unlink)(?:\.exe)?\b",
        r"\bgit(?:\.exe)?\b[^\r\n;|]*\b(?:rm|clean)\b",
        r"\bos\.(?:remove|unlink)\s*\(",
        r"\bshutil\.rmtree\s*\(",
        r"(?:\.|::)(?:Delete|unlink|rmdir|unlinkSync|rmSync)\s*\(",
        r"\*\*\* (?:Delete File|Move to):",
    ))
    if deletion:
        return decision("ask", "Review this tool call's deletion scope before approving it.")
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError):
        result = decision("deny", "Invalid deletion-hook input.")
    print(json.dumps(result))
