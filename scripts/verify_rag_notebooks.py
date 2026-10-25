"""Validate and optionally execute each standalone RAG lesson in a fresh kernel."""

import argparse
import ast
from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "notebooks" / "rag"


def verify(path: Path, execute: bool) -> None:
    book = nbformat.read(path, as_version=4)
    nbformat.validate(book)
    code = [cell.source for cell in book.cells if cell.cell_type == "code"]
    for index, source in enumerate(code):
        tree = ast.parse(source, filename=str(path))
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        if index == 0:
            assert imports and all(node in tree.body for node in imports), path
            assert not any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in tree.body), path
        else:
            assert not imports, (path, index)
    if execute:
        result = NotebookClient(book, timeout=240, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
        output = ROOT / ".tmp" / "rag" / "executed" / path.name
        output.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(result, output)
    print(f"OK {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    names = args.names or [path.name for path in sorted(LESSONS.glob("*.ipynb"))]
    for name in names:
        verify(LESSONS / name, args.execute)


if __name__ == "__main__":
    main()
