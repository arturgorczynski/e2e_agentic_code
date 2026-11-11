"""Execute a notebook into an ignored copy, preserving its source file."""

import argparse
import json
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[4]


def run_copy(source):
    source = Path(source).resolve()
    relative = source.relative_to(ROOT)
    if source.suffix.lower() != ".ipynb":
        raise ValueError("Choose a repository notebook.")
    target = ROOT / ".tmp" / "lesson-review" / relative
    output_root = (ROOT / ".tmp" / "lesson-review").resolve()
    if not target.resolve().is_relative_to(output_root) or target.resolve() == source:
        raise ValueError("The output must be a separate copy under .tmp/lesson-review.")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Preserve the existing review copy; ask the user to remove it manually: {target}")
    book = nbformat.read(source, as_version=4)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        NotebookClient(book, timeout=600, allow_errors=True,
                       resources={"metadata": {"path": str(source.parent)}}).execute()
    finally:
        # Retain completed outputs even if kernel startup or execution fails.
        with target.open("x", encoding="utf-8") as stream:
            nbformat.write(book, stream)
    failed = [index for index, cell in enumerate(book.cells, 1)
              if any(output.get("output_type") == "error" for output in cell.get("outputs", []))]
    return {"source": str(source), "copy": str(target), "failed_cells": failed,
            "status": f"cell {failed[0]} failed" if failed else "ran clean"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook")
    args = parser.parse_args()
    print(json.dumps(run_copy(args.notebook)))
