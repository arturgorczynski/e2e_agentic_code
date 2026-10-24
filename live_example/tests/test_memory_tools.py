"""Cross-conversation persistence and persona isolation for explicit notes."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from acme.app_store import RunContext
from acme.memory_tools import open_memory, recall, remember


class MemoryToolTests(unittest.TestCase):
    def test_notes_persist_across_threads_but_stay_with_the_selected_persona(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            first = RunContext(state, state, state, "actor-one", "thread-1", "run-1")
            later = RunContext(state, state, state, "actor-one", "thread-2", "run-2")
            other = RunContext(state, state, state, "actor-two", "thread-3", "run-3")

            def actor(context):
                return {"id": context.session_token}

            with (
                patch("acme.memory_tools.authorize", side_effect=actor),
                patch("acme.memory_tools.event"),
            ):
                with open_memory(state) as store:
                    result = remember(first, store, "answer style", "Prefer concise bullet points")
                    self.assertEqual(result["status"], "saved")
                with open_memory(state) as store:
                    self.assertEqual(
                        recall(later, store, "answer style")["notes"][0]["note"],
                        "Prefer concise bullet points",
                    )
                    self.assertEqual(recall(other, store)["count"], 0)
                    with self.assertRaisesRegex(ValueError, "email addresses"):
                        remember(later, store, "contact", "Email me at person@example.com")


if __name__ == "__main__":
    unittest.main()
