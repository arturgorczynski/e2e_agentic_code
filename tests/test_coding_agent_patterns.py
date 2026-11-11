"""Check host isolation, documentation links, and example import layout."""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodingAgentPatternTests(unittest.TestCase):
    def test_only_this_hosts_skill_directory_exists(self):
        codex = (ROOT / ".codex/config.toml").is_file()
        own, other = (".agents", ".claude") if codex else (".claude", ".agents")
        self.assertFalse(list((ROOT / other / "skills").glob("*/SKILL.md")))
        self.assertEqual({p.parent.name for p in (ROOT / own / "skills").glob("*/SKILL.md")},
                         {"explain-code", "review-lesson"})
        self.assertFalse((ROOT / "CLAUDE.md").exists())
        self.assertFalse((ROOT / ".claude").exists())
        self.assertEqual({p.stem for p in (ROOT / ".codex/agents").glob("*.toml")},
                         {"joke_writer", "lesson_reviewer"})

    def test_documentation_links_resolve(self):
        for path in (ROOT / "docs").glob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(), (path, target))

    def test_example_python_imports_are_at_module_scope(self):
        paths = [*ROOT.glob("tests/test_*patterns.py"), *ROOT.glob(".codex/hooks/*.py"),
                 *ROOT.glob(".claude/hooks/*.py"), *ROOT.glob("agent_demo/*.py"),
                 *ROOT.glob(".agents/skills/*/scripts/*.py")]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self.assertIn(node, tree.body, path)


if __name__ == "__main__":
    unittest.main()
