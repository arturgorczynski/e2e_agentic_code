"""Validate/execute notebooks without replacing the student's saved outputs.

uv run --group middleware python notebooks/langchain/06_middlewares/verify_notebooks.py --execute
Add filenames/globs to run a subset, e.g. 04* 05*.
"""
import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="*", default=["*.ipynb"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--input", action="append", default=[], help="Explicit test answers for input(), in order; only affects the verification copy")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    paths = sorted({path for pattern in args.patterns for path in HERE.glob(pattern)})
    if not paths:
        parser.error("No notebooks matched.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = HERE / "artifacts" / "verification" / f"{stamp}-{uuid4().hex[:8]}"
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for path in paths:
        start = perf_counter()
        notebook = nbformat.read(path, as_version=4)
        entry = {"notebook": path.name, "status": "validated",
                 "source_sha256": sha256(path.read_bytes()).hexdigest(),
                 "versions": {name: version(name) for name in ("langchain", "langgraph", "deepagents")},
                 "checked_at": datetime.now(UTC).isoformat()}
        try:
            nbformat.validate(notebook)
            for index, cell in enumerate(notebook.cells):
                if cell.cell_type == "code":
                    compile(cell.source, f"{path.name}:cell-{index}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            if args.execute:
                # Verification copies of the memory lesson must not overwrite
                # the learner's saved conversations.
                if path.name == "04_adding_memory.ipynb":
                    for cell in notebook.cells:
                        if cell.cell_type == "code":
                            cell.source = cell.source.replace(
                                'MEMORY_DIR = NOTEBOOK_DIR / "03_memory"',
                                f"MEMORY_DIR = Path({str(output / 'memory')!r})",
                            )
                needs_input = any("input(" in cell.source for cell in notebook.cells if cell.cell_type == "code")
                if needs_input:
                    if not args.input:
                        raise ValueError("Interactive lesson: supply explicit --input test answers. The source notebook still asks the human.")
                    header = next(cell for cell in notebook.cells if cell.cell_type == "code")
                    header.source += "\nimport builtins\n"
                    setup = nbformat.v4.new_code_cell(
                        f"_test_answers = iter({args.input!r})\n"
                        "def _verification_input(prompt=''):\n"
                        "    try:\n"
                        "        answer = next(_test_answers)\n"
                        "    except StopIteration as error:\n"
                        "        raise RuntimeError('Not enough explicit --input answers') from error\n"
                        "    print(prompt + answer + ' [verification answer]')\n"
                        "    return answer\n"
                        "input = _verification_input\n"
                    )
                    notebook.cells.insert(notebook.cells.index(header) + 1, setup)
                    entry["human_input"] = "explicit simulated answers in verification copy only"
                manager = KernelManager(kernel_name="python3")
                manager.kernel_spec.argv[0] = sys.executable
                try:
                    NotebookClient(
                        notebook, km=manager, timeout=args.timeout,
                        resources={"metadata": {"path": str(path.resolve().parent)}},
                    ).execute()
                finally:
                    if manager.has_kernel:
                        manager.shutdown_kernel(now=True)
                entry["status"] = "executed"
                text = "\n".join(
                    out.get("text", "") for cell in notebook.cells
                    for out in cell.get("outputs", []) if out.get("output_type") == "stream"
                )
                entry["skipped_integrations"] = [
                    line for line in text.splitlines()
                    if "SKIPPED:" in line or "DOCKER NOT READY:" in line or "DOCKER IMAGE MISSING:" in line
                ]
                if entry["skipped_integrations"]:
                    entry["status"] = "executed_with_skips"
        except Exception as error:  # noqa: BLE001 - report the failed lesson and continue checking the others
            entry["status"] = "failed"
            entry["error"] = str(error)
        if args.execute:
            nbformat.write(notebook, output / path.name)
        entry["seconds"] = round(perf_counter() - start, 2)
        report.append(entry)
        suffix = ".execution.json" if args.execute else ".validation.json"
        (output / f"{path.stem}{suffix}").write_text(json.dumps(entry, indent=2), encoding="utf-8")
        print(f"{entry['status'].upper():10} {path.name} ({entry['seconds']}s)", flush=True)
        if entry["status"] == "failed":
            print(entry["error"][-4000:], flush=True)
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Report:", report_path)
    return int(any(item["status"] == "failed" for item in report))


if __name__ == "__main__":
    sys.exit(main())
