"""Request native Claude approval for recognized commits and file deletions."""

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
    if re.search(r"(?:create_commit|delete_file|remove_file)", tool, re.IGNORECASE):
        return decision("ask", "Review the proposed commit or file deletion.")
    command = args.get("command", args.get("cmd", ""))
    if not isinstance(command, str):
        raise ValueError("Expected text command.")
    if tool not in {"Bash", "PowerShell", "exec_command"}:
        return {}
    commit = re.search(r"\bgit(?:\.exe)?\b[^\r\n;|]*\bcommit(?:-tree)?\b", command, re.IGNORECASE)
    deletion = any(re.search(pattern, command, re.IGNORECASE) for pattern in (
        r"\b(?:rm|rmdir|rd|Remove-Item|ri|del|erase|unlink)(?:\.exe)?\b",
        r"\bgit(?:\.exe)?\b[^\r\n;|]*\b(?:rm|clean)\b",
        r"\bos\.(?:remove|unlink)\s*\(",
        r"\bshutil\.rmtree\s*\(",
        r"(?:\.|::)(?:Delete|unlink|rmdir|unlinkSync|rmSync)\s*\(",
        r"\*\*\* (?:Delete File|Move to):",
    ))
    if commit or deletion:
        operation = "commit and file deletion" if commit and deletion else "commit" if commit else "file deletion"
        return decision("ask", f"Review the proposed {operation}. Approve this tool call only if its scope is intended.")
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError):
        result = decision("deny", "Invalid approval-hook input; operation was not approved.")
    print(json.dumps(result))
