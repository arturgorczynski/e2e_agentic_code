"""Run the two offline introductory lessons and check their key contracts."""

import json
import re
import unittest
from pathlib import Path


LESSONS = Path(__file__).resolve().parents[1] / "notebooks" / "langchain"


class IntroLessonTests(unittest.TestCase):
    def run_lesson(self, filename):
        path = LESSONS / filename
        book = json.loads(path.read_text(encoding="utf-8"))
        namespace = {"__name__": "__main__"}
        for cell in book["cells"]:
            source = "".join(cell["source"])
            self.assertIsNone(re.search(r"\w\?\w|\?\?", source), path)
            if cell["cell_type"] == "code":
                exec(compile(source, str(path), "exec"), namespace)  # noqa: S102
        return book, namespace

    def test_context_and_state_lesson(self):
        book, lesson = self.run_lesson("09_context_and_state.ipynb")
        self.assertIn("two different data sources", "".join(book["cells"][0]["source"]))
        self.assertEqual([item["viewer_id"] for item in lesson["observed"]], ["u-101", "u-202"])
        turns = [lesson[name]["turns"] for name in ("graph_first", "graph_second")]
        self.assertEqual(turns, [1, 2])
        self.assertEqual(lesson["other_thread"]["turns"], 1)

    def test_custom_middleware_lesson(self):
        book, lesson = self.run_lesson("10_custom_middleware.ipynb")
        self.assertIn("Custom middleware", "".join(book["cells"][0]["source"]))
        calls = [lesson[name]["model_calls"] for name in ("first", "second", "third")]
        self.assertEqual(calls, [1, 2, 2])
        self.assertEqual(lesson["new_result"]["model_calls"], 1)
        self.assertEqual(lesson["budget"].events.count("model:enter"), 3)


if __name__ == "__main__":
    unittest.main()
