"""Deny recognizable deletions; leave the operation for the user to perform."""

import json
import re
import sys


def deny(reason):
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}


def check(event):
    tool = event["tool_name"]
    args = event["tool_input"]
    if not isinstance(tool, str) or not isinstance(args, (dict, str)):
        raise ValueError("Expected a tool name and tool arguments.")
    if re.search(r"(?:delete_file|remove_file)", tool, re.IGNORECASE):
        return deny("File deletion is denied. Leave the target for the user to delete manually.")
    command = args if isinstance(args, str) else args.get("command", args.get("cmd", args.get("patch", "")))
    if not isinstance(command, str):
        raise ValueError("Expected text command or patch.")
    if re.search(r"^\*\*\* (?:Delete File|Move to):", command, re.MULTILINE):
        return deny("Patch deletion or moving is denied. Leave the target for the user to handle manually.")
    if tool not in {"Bash", "PowerShell", "exec_command"}:
        return {}
    # Text heuristics mirror the Claude example; they are not a shell parser.
    deletion = any(re.search(pattern, command, re.IGNORECASE) for pattern in (
        r"\b(?:rm|rmdir|rd|Remove-Item|ri|del|erase|unlink)(?:\.exe)?\b",
        r"\bgit(?:\.exe)?\b[^\r\n;|]*\b(?:rm|clean)\b",
        r"\bos\.(?:remove|unlink)\s*\(",
        r"\bshutil\.rmtree\s*\(",
        r"(?:\.|::)(?:Delete|unlink|rmdir|unlinkSync|rmSync)\s*\(",
        r"\*\*\* (?:Delete File|Move to):",
    ))
    if deletion:
        return deny("Deletion is denied. Report the proposed targets for the user to delete manually; do not retry through another tool.")
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError):
        result = deny("Invalid deletion-hook input.")
    print(json.dumps(result))
