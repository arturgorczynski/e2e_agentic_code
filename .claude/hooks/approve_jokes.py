"""Validate the joke writer's sole output and request native approval."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "jokes.txt"


def decision(value, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": value,
                                   "permissionDecisionReason": reason}}


def check(event):
    if event["tool_name"] != "Write":
        return decision("deny", "The joke writer may only create its output through Write.")
    args = event["tool_input"]
    raw_path = args["file_path"]
    content = args["content"]
    if not isinstance(raw_path, str) or not raw_path or not isinstance(content, str):
        raise ValueError("Expected path and text content.")
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(event.get("cwd", ROOT)) / path
    if path.resolve() != TARGET:
        return decision("deny", "The joke writer owns only root jokes.txt.")
    if TARGET.exists() or TARGET.is_symlink():
        return decision("deny", "jokes.txt already exists; preserve it.")
    lines = content.strip().splitlines()
    if len(lines) != 5 or any(not re.fullmatch(rf"{index}\.\s+\S.*", line)
                              for index, line in enumerate(lines, 1)):
        return decision("deny", "Provide exactly five nonempty jokes numbered 1. through 5.")
    return decision("ask", f"Allow joke-writer to create {TARGET} with these five jokes?")


if __name__ == "__main__":
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        result = decision("deny", "Invalid joke-write input; operation was not approved.")
    print(json.dumps(result))
