"""Validate the portable teaching workflow files without calling a model."""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodingAgentPatternTests(unittest.TestCase):
    def test_shared_skills_are_identical_in_both_discovery_directories(self):
        for name in ("explain-code", "review-lesson"):
            codex = ROOT / ".agents/skills" / name / "SKILL.md"
            claude = ROOT / ".claude/skills" / name / "SKILL.md"
            self.assertEqual(codex.read_bytes(), claude.read_bytes())
            self.assertTrue(codex.read_text().startswith("---\nname: "))

    def test_documentation_links_resolve(self):
        for path in (ROOT / "docs").glob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(), (path, target))

    def test_example_python_imports_are_at_module_scope(self):
        paths = [Path(__file__), *ROOT.glob(".codex/hooks/*.py"), *ROOT.glob(".claude/hooks/*.py")]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self.assertIn(node, tree.body, path)


if __name__ == "__main__":
    unittest.main()
