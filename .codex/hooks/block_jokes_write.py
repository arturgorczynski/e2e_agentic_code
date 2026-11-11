"""Intercept and deny recognizable writes to root jokes.txt."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "jokes.txt"


def deny():
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "Writing jokes.txt is denied by the project hook. Report that the write was attempted and blocked, then stop. Do not print the jokes in chat, retry using another tool, or change the target. Preserve any existing file.",
    }}


def check(event):
    tool = event["tool_name"]
    args = event["tool_input"]
    if not isinstance(tool, str) or not isinstance(args, (dict, str)):
        raise ValueError("Expected a tool name and tool arguments.")
    cwd = Path(event.get("cwd", ROOT))
    command = args if isinstance(args, str) else args.get("command", args.get("cmd", args.get("patch", "")))
    if not isinstance(command, str):
        raise ValueError("Expected text command or patch.")
    paths = re.findall(r"^\*\*\* (?:Add File|Update File|Move to): (.+)$", command, re.MULTILINE)
    if isinstance(args, dict) and re.search(r"write|create|append|edit|patch|move|rename|save|copy", tool, re.IGNORECASE):
        paths += [args[key] for key in ("file_path", "path", "target", "destination") if key in args]
    for raw_path in paths:
        if not isinstance(raw_path, str):
            raise ValueError("Expected a text path.")
        path = Path(raw_path.strip())
        absolute = path if path.is_absolute() else cwd / path
        # The lexical comparison also catches an existing root symlink.
        if absolute.absolute() == TARGET or absolute.resolve() == TARGET:
            return deny()
    if tool in {"Bash", "PowerShell", "exec_command"} and re.search(r"\bjokes\.txt\b", command, re.IGNORECASE):
        # Conservative shell-text detection can also match quoted examples.
        writes = re.search(
            r">|\b(?:Set-Content|Add-Content|Out-File|New-Item|Copy-Item|Move-Item|sc|ac|ni|tee|touch|cp|mv)\b"
            r"|\b(?:write_text|write_bytes|writeFile|writeFileSync|appendFile|appendFileSync)\s*\("
            r"|\bopen\s*\([^\r\n]*[\"'][wax][+bt]*[\"']",
            command, re.IGNORECASE,
        )
        if writes:
            return deny()
    return {}


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        result = deny()
    print(json.dumps(result))
