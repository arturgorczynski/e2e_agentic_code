"""Agent subprocess entry point. Credentials arrive only through a private stdin pipe."""

import json
import sys
from pathlib import Path

from acme.runtime import submit


def main():
    payload = json.loads(sys.stdin.buffer.read(100000))
    request = payload["request"]
    submit(
        Path(payload["project"]),
        Path(payload["state"]),
        Path(payload["data"]),
        payload["token"],
        request["thread_id"],
        request["submission_id"],
        request["user_text"],
        resume=bool(request["resume"]),
    )


if __name__ == "__main__":
    main()
