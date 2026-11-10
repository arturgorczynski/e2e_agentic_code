"""Check notebook contracts offline; real Ollama acceptance runs the support notebook."""

import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from langchain_core.messages import HumanMessage


LESSONS = Path(__file__).resolve().parents[1] / "notebooks" / "langchain"


class IntroLessonTests(unittest.TestCase):
    def run_lesson(self, filename):
        path = LESSONS / filename
        book = json.loads(path.read_text(encoding="utf-8"))
        namespace = {"__name__": "__main__"}
        with redirect_stdout(io.StringIO()):
            for cell in book["cells"]:
                source = "".join(cell["source"])
                self.assertIsNone(re.search(r"\w\?\w|\?\?", source), path)
                if cell["cell_type"] == "code":
                    exec(compile(source, str(path), "exec"), namespace)  # noqa: S102
        return book, namespace

    def test_custom_middleware_lesson(self):
        book, lesson = self.run_lesson("10_custom_middleware.ipynb")
        self.assertIn("Custom middleware", "".join(book["cells"][0]["source"]))
        calls = [lesson[name]["model_calls"] for name in ("first", "second", "third")]
        self.assertEqual(calls, [1, 2, 2])
        self.assertEqual(lesson["new_result"]["model_calls"], 1)
        self.assertEqual(lesson["budget"].events.count("model:enter"), 3)


class SupportTicketLessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = LESSONS / "09_context_and_state.ipynb"
        cls.book = json.loads(path.read_text(encoding="utf-8"))
        cls.lesson = {"__name__": "__main__"}
        for cell in cls.book["cells"]:
            if cell["cell_type"] == "code" and "setup" in cell["metadata"].get("tags", []):
                exec(compile("".join(cell["source"]), cell["id"], "exec"), cls.lesson)  # noqa: S102

    def setUp(self):
        self.lesson["FAKE_ACTIONS"].clear()
        self.lesson["tool_audit"].clear()
        user_id, order_id = next(iter(self.lesson["FAKE_ORDERS"]))
        self.context = self.lesson["SupportContext"](user_id, order_id, "TKT-TEST")

    def runtime(self, scenario_key, state=None, context=None):
        return self.lesson["ToolRuntime"](
            state={**(state or {}), "messages": [HumanMessage(content=self.lesson["SCENARIO"][scenario_key])]},
            context=context or self.context, config={}, stream_writer=lambda _: None,
            tool_call_id="test-call", store=None,
        )

    def test_model_visible_tools_cannot_choose_identity(self):
        for name in ("lookup_order", "create_replacement", "queue_human_review"):
            self.assertEqual(self.lesson[name].tool_call_schema.model_json_schema()["properties"], {})
        fields = self.lesson["update_ticket"].tool_call_schema.model_json_schema()["properties"]
        self.assertEqual(set(fields), {"stage", "urgency", "summary"})
        self.assertNotIn("ScriptedModel", "".join("".join(c["source"]) for c in self.book["cells"]))

    def test_order_lookup_uses_application_scope(self):
        result = self.lesson["lookup_order"].func(runtime=self.runtime("new"))
        expected = self.lesson["FAKE_ORDERS"][(self.context.user_id, self.context.order_id)]
        self.assertEqual(result["item"], expected["item"])
        self.assertEqual(self.lesson["tool_audit"][-1]["user_id"], self.context.user_id)

    def test_identity_override_escalates_without_disclosure_or_action(self):
        for operation in ("lookup_order", "create_replacement"):
            result = self.lesson[operation].func(runtime=self.runtime("identity"))
            self.assertEqual(result.update["stage"], "for_review")
            self.assertEqual(result.update["urgency"], "high")
            self.assertIn("identity_mismatch", result.update["review_reasons"])
            foreign = list(self.lesson["FAKE_ORDERS"].values())[1]["item"]
            self.assertNotIn(foreign, json.dumps(result.update, default=str))
        self.assertFalse(self.lesson["FAKE_ACTIONS"])

    def test_safety_and_sticky_identity_override_model_proposals(self):
        for scenario, reasons in (("safety", []), ("bypass", ["identity_mismatch"])):
            result = self.lesson["update_ticket"].func(
                stage="automated_process", urgency="low", summary="",
                runtime=self.runtime(scenario, {"review_reasons": reasons}),
            )
            self.assertEqual(result.update["stage"], "for_review")
            self.assertEqual(result.update["urgency"], "high")
        state = result.update
        blocked = self.lesson["create_replacement"].func(runtime=self.runtime("bypass", state))
        self.assertEqual(blocked.update["stage"], "for_review")
        self.assertFalse(self.lesson["FAKE_ACTIONS"])

    def test_current_context_controls_automation_and_replacement_is_idempotent(self):
        readonly = self.lesson["replace"](self.context, allow_automation=False)
        classify = self.lesson["update_ticket"].func
        result = classify(stage="automated_process", urgency="normal", summary="",
                          runtime=self.runtime("permission", context=readonly))
        self.assertEqual(result.update["stage"], "for_review")
        action = self.lesson["create_replacement"].func
        denied = action(runtime=self.runtime("permission", {"stage": "automated_process"}, readonly))
        self.assertEqual(denied["status"], "blocked")
        self.assertFalse(self.lesson["FAKE_ACTIONS"])
        allowed = classify(stage="automated_process", urgency="normal", summary="",
                           runtime=self.runtime("permission_restored", result.update))
        first = action(runtime=self.runtime("new", allowed.update))
        second = action(runtime=self.runtime("urgent", {**allowed.update, **first.update}))
        self.assertEqual(first.update["action_id"], second.update["action_id"])
        self.assertEqual(len(self.lesson["FAKE_ACTIONS"]), 1)

    def test_resolution_requires_customer_confirmation_and_existing_action(self):
        classify = self.lesson["update_ticket"].func
        denied = classify(stage="resolved", urgency="low", summary="",
                          runtime=self.runtime("resolved"))
        self.assertEqual(denied["status"], "blocked")
        result = classify(stage="resolved", urgency="normal", summary="",
                          runtime=self.runtime("resolved", {"action_id": "REP-TEST"}))
        self.assertEqual(result.update["stage"], "resolved")
        self.assertEqual(result.update["urgency"], "low")

    def test_existing_thread_cannot_be_reused_with_foreign_context(self):
        self.lesson["thread_scopes"] = {
            "scope-test": (self.context.user_id, self.context.order_id, self.context.ticket_id),
        }
        foreign_user, foreign_order = list(self.lesson["FAKE_ORDERS"])[1]
        foreign = self.lesson["replace"](self.context, user_id=foreign_user, order_id=foreign_order)
        with self.assertRaises(ValueError):
            self.lesson["run_turn"]("", "", foreign, "scope-test")
        self.assertFalse(self.lesson["FAKE_ACTIONS"])


if __name__ == "__main__":
    unittest.main()
