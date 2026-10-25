"""Protect the RAG lesson sequence and repository import convention."""

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "notebooks" / "rag"


class RagLessonLayoutTests(unittest.TestCase):
    def test_nine_standalone_lessons_keep_imports_in_first_code_cell(self):
        paths = sorted(LESSONS.glob("*.ipynb"))
        self.assertEqual([path.name[:2] for path in paths], [f"{number:02d}" for number in range(1, 10)])
        for path in paths:
            book = json.loads(path.read_text(encoding="utf-8"))
            cells = [cell for cell in book["cells"] if cell["cell_type"] == "code"]
            self.assertTrue(cells, path)
            for index, cell in enumerate(cells):
                tree = ast.parse("".join(cell["source"]))
                imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
                with self.subTest(notebook=path.name, cell=index):
                    if index == 0:
                        self.assertTrue(imports)
                        self.assertTrue(all(node in tree.body for node in imports))
                        self.assertFalse(any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in tree.body))
                    else:
                        self.assertEqual(imports, [])
                    self.assertEqual(cell["outputs"], [])

    def test_python_module_imports_are_top_level(self):
        for path in (LESSONS / "lab.py", ROOT / "scripts" / "verify_rag_notebooks.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self.assertIn(node, tree.body, path)


if __name__ == "__main__":
    unittest.main()
