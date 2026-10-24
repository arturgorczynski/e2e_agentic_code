"""Owned local CSV worker. Fixed algorithms only; independent deadline/parent watchdog."""

import ctypes
import json
import os
import sys
import threading
import time
from pathlib import Path

from acme.analysis import MAX_OUTPUT, analyze_csv, render_report


def watch_parent(parent_pid, seconds):
    started = time.monotonic()
    handle = None
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, parent_pid)
        if not handle:
            os._exit(125)
    try:
        while True:
            parent_dead = (
                kernel.WaitForSingleObject(handle, 0) != 258
                if handle
                else os.getppid() != parent_pid
            )
            if parent_dead or time.monotonic() - started >= seconds:
                os._exit(124)
            time.sleep(0.05)
    finally:
        if handle:
            kernel.CloseHandle(handle)


def main():
    folder = Path(sys.argv[1]).resolve()
    request = json.loads((folder / "request.json").read_text("utf-8"))
    watchdog = threading.Thread(
        target=watch_parent, args=(request["parent_pid"], request["deadline_seconds"]), daemon=True
    )
    watchdog.start()
    try:
        result = analyze_csv((folder / "input.csv").read_bytes(), **request["analysis"])
        payload = json.dumps(result, indent=2).encode()
        report = render_report(result).encode()
        if len(payload) + len(report) > MAX_OUTPUT:
            raise ValueError("Analysis output exceeds 1 MiB")
        (folder / "result.json").write_bytes(payload)
        (folder / "report.md").write_bytes(report)
    except Exception as exc:
        (folder / "error.json").write_text(json.dumps({"error": str(exc)[:500]}), encoding="utf-8")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
