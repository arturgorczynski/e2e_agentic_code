"""Mechanical notebook refactor: one imports/bootstrap cell before examples."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def split_imports(source):
    tree = ast.parse(source)
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    if any(node.col_offset for node in imports):
        raise ValueError("Nested notebook imports require manual review.")
    lines = source.splitlines(keepends=True)
    removed = {index for node in imports for index in range(node.lineno - 1, node.end_lineno)}
    return imports, "".join(line for index, line in enumerate(lines) if index not in removed).strip()


def render_imports(nodes):
    groups = {}
    for node in nodes:
        key = ("import", "") if isinstance(node, ast.Import) else ("from", "." * node.level + node.module)
        aliases = groups.setdefault(key, set())
        aliases.update(alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names)
    standard, other = [], []
    for (kind, module), aliases in sorted(groups.items()):
        if kind == "import":
            for alias in sorted(aliases):
                target = standard if alias.split(".")[0].split()[0] in sys.stdlib_module_names else other
                target.append(f"import {alias}")
        else:
            target = standard if module.split(".")[0] in sys.stdlib_module_names else other
            names = sorted(aliases)
            line = f"from {module} import {', '.join(names)}"
            if len(line) > 100:
                line = f"from {module} import (\n" + "".join(f"    {name},\n" for name in names) + ")"
            target.append(line)
    return "\n".join(standard), "\n".join(other)


def organize(path):
    book = json.loads(path.read_text(encoding="utf-8"))
    imports = []
    first = next(i for i, cell in enumerate(book["cells"]) if cell["cell_type"] == "code")
    bootstrap = []
    for index, cell in enumerate(book["cells"]):
        if cell["cell_type"] != "code":
            continue
        nodes, rest = split_imports("".join(cell["source"]))
        imports.extend(nodes)
        if index == first:
            lines = rest.splitlines(keepends=True)
            removed = set()
            for node in ast.parse(rest).body:
                is_path_assignment = isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id in {"ROOT", "LESSONS"}
                    for target in node.targets
                )
                is_path_guard = isinstance(node, ast.If) and "sys.path" in ast.unparse(node)
                if is_path_assignment or is_path_guard:
                    bootstrap.append("".join(lines[node.lineno - 1:node.end_lineno]).strip())
                    removed.update(range(node.lineno - 1, node.end_lineno))
            rest = "".join(line for i, line in enumerate(lines) if i not in removed).strip()
        cell["source"] = rest.splitlines(keepends=True)
    standard, other = render_imports(imports)
    source = "# Imports and project path setup only; examples start in the next cell.\n"
    source += standard + "\n\n" + "\n".join(bootstrap) + "\n\n" + other
    first_cell = book["cells"][first]
    imports_cell = {
        "cell_type": "code", "id": "imports", "metadata": {"tags": ["imports"]},
        "source": source.splitlines(keepends=True), "execution_count": None, "outputs": [],
    }
    if first_cell["source"]:
        book["cells"].insert(first, imports_cell)
    else:
        book["cells"][first] = imports_cell
    # Drop only newly empty code cells; never discard saved outputs.
    book["cells"] = [cell for cell in book["cells"]
                     if cell["cell_type"] != "code" or cell["source"] or cell.get("outputs")]
    path.write_text(json.dumps(book, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(path.relative_to(ROOT))


def main():
    paths = sorted((ROOT / "notebooks/langchain").glob("*.ipynb"))
    paths += sorted((ROOT / "notebooks/langchain/06_middlewares").glob("*.ipynb"))
    for path in paths:
        organize(path)


if __name__ == "__main__":
    main()
