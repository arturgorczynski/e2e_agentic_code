"""Exercise the middleware authored inside the teaching notebook itself."""
import ast
import asyncio
import inspect
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "notebooks/langchain/06_middlewares"
sys.path.insert(0, str(LESSONS))

from lab.faults import ScriptedModel, tool_request


class CustomMiddlewareLesson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = LESSONS / "16_custom_middleware.ipynb"
        book = json.loads(path.read_text(encoding="utf-8"))
        module = ModuleType("custom_middleware_lesson_under_test")
        sys.modules[module.__name__] = module
        cls.addClassCleanup(sys.modules.pop, module.__name__, None)
        cls.namespace = module.__dict__
        cells = ["".join(cell["source"]) for cell in book["cells"] if cell["cell_type"] == "code"]
        with redirect_stdout(io.StringIO()):
            for index, source in enumerate(cells):
                compiled = compile(source, f"{path.name}:code-{index}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
                if compiled.co_flags & inspect.CO_COROUTINE:
                    asyncio.run(eval(compiled, cls.namespace))
                else:
                    exec(compiled, cls.namespace)  # noqa: S102 - trusted notebook code
                if index == 0:
                    # Only the final case uses get_model. Middleware definitions,
                    # graph, tools, state and reducers remain the real lesson code.
                    cls.namespace["get_model"] = lambda: ScriptedModel(responses=[
                        tool_request("add_numbers", a=7, b=5), AIMessage(content="Wynik to 12."),
                    ])

    def test_teaching_notebooks_keep_imports_in_the_first_code_cell(self):
        paths = sorted((ROOT / "notebooks/langchain").glob("*.ipynb")) + sorted(LESSONS.glob("*.ipynb"))
        for path in paths:
            book = json.loads(path.read_text(encoding="utf-8"))
            cells = ["".join(cell["source"]) for cell in book["cells"] if cell["cell_type"] == "code"]
            for index, source in enumerate(cells):
                tree = ast.parse(source)
                imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
                with self.subTest(notebook=path.name, cell=index):
                    if index:
                        self.assertEqual(imports, [])
                    else:
                        self.assertTrue(imports)
                        self.assertTrue(all(node in tree.body for node in imports))
                        self.assertFalse(any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in tree.body))

    def test_module_imports_stay_at_module_scope(self):
        paths = [Path(__file__), LESSONS / "verify_notebooks.py", *sorted((LESSONS / "lab").glob("*.py"))]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    with self.subTest(module=path.name):
                        self.assertIn(node, tree.body)

    def test_polish_text_and_added_prompt_newline_survive_serialization(self):
        source = (LESSONS / "16_custom_middleware.ipynb").read_text(encoding="utf-8")
        self.assertIn("Własne middleware", source)
        self.assertIn("współdzielone", source)
        self.assertNotIn("\ufffd", source)
        self.assertIn("\nJęzyk odpowiedzi: polski", self.namespace["prompt_requests"][0])

    def test_lifecycle_and_order_match_actual_two_turn_tool_loop(self):
        ns = self.namespace
        self.assertEqual(ns["lifecycle_probe"].events.count("before_agent"), 1)
        self.assertEqual(ns["lifecycle_probe"].events.count("before_model"), 2)
        self.assertEqual(ns["lifecycle_probe"].events.count("tool:enter"), 1)
        self.assertEqual(ns["order_events"], ["A:before", "B:before", "A:enter", "B:enter", "B:leave", "A:leave", "B:after", "A:after"])

    def test_state_isolated_and_message_replacement_does_not_append(self):
        ns = self.namespace
        self.assertEqual([ns[name]["turns"] for name in ("state_first", "state_second", "state_other")], [1, 2, 1])
        self.assertEqual(len(ns["trim_result"]["messages"]), 2)
        self.assertEqual(ns["trim_result"]["messages"][-1].content, "Krótka odpowiedź.")

    def test_after_model_revision_succeeds_or_terminates_at_its_budget(self):
        ns = self.namespace
        self.assertTrue(ns["format_result"]["format_valid"])
        self.assertEqual(ns["format_result"]["review_retries"], 1)
        self.assertFalse(ns["invalid_format_result"]["format_valid"])
        self.assertEqual(ns["invalid_format_model"]._index, 2)

    def test_hidden_schema_is_not_authorization_and_guard_blocks_effect(self):
        ns = self.namespace
        self.assertEqual(len(ns["filter_only_effects"]), 1)
        self.assertNotIn("publish_note", ns["visible_catalogs"][0])
        self.assertEqual(ns["reader_effects"], [])
        tool_message = next(m for m in ns["reader_result"]["messages"] if m.type == "tool")
        self.assertEqual(tool_message.status, "error")

    def test_normalization_preserves_original_arguments_and_call_id(self):
        ns = self.namespace
        self.assertEqual(ns["normalization_events"], [{"before": "  warszawa  ", "after": "Warszawa", "same_id": True}])
        calls = [call for message in ns["normalization_result"]["messages"] if message.type == "ai" for call in message.tool_calls]
        self.assertEqual(calls[0]["args"]["city"], "  warszawa  ")
        result = next(m for m in ns["normalization_result"]["messages"] if m.type == "tool")
        self.assertEqual(result.tool_call_id, calls[0]["id"])
        self.assertEqual(result.content, "Warszawa")

    def test_registered_and_discovered_tools_reach_real_implementations(self):
        ns = self.namespace
        self.assertEqual(next(m for m in ns["health_result"]["messages"] if m.type == "tool").content, "healthy")
        self.assertIn("demo-rate=4.00", next(m for m in ns["discovery_result"]["messages"] if m.type == "tool").content)

    def test_retry_and_idempotency_measure_attempts_and_actual_effects(self):
        ns = self.namespace
        self.assertEqual((ns["retry_result"]["turns"], ns["connection_retry"].attempts, ns["retry_model"]._index), (1, 3, 1))
        self.assertEqual(len(ns["unsafe_bookings"]), 2)
        self.assertEqual(len(ns["safe_bookings"]), 1)
        self.assertEqual(len(ns["safe_attempts"]), 2)
        self.assertEqual(ns["exhausted_retry"].attempts, 2)

    def test_retry_does_not_retry_programming_errors(self):
        class ProgrammingError(AgentMiddleware):
            def wrap_model_call(self, request, handler):
                raise ValueError("Invalid configuration")

        retry = self.namespace["RetryConnections"](max_attempts=3)
        agent = create_agent(model=ScriptedModel(responses=[]), middleware=[retry, ProgrammingError()])
        with self.assertRaisesRegex(ValueError, "Invalid configuration"):
            agent.invoke({"messages": [("user", "Hello")]})
        self.assertEqual(retry.attempts, 1)

    def test_command_composition_keeps_preference_and_parallel_audit_entries(self):
        result = self.namespace["command_result"]
        self.assertEqual(result["favorite_color"], "niebieski")
        self.assertEqual(sorted(result["audit_entries"]), ["tool:preference", "wrapper:add_numbers", "wrapper:remember_color"])
        call_ids = {call["id"] for message in result["messages"] if message.type == "ai" for call in message.tool_calls}
        self.assertEqual({m.tool_call_id for m in result["messages"] if m.type == "tool"}, call_ids)
        self.assertEqual(self.namespace["composed_result"]["layers"], ["inner", "outer"])
        self.assertEqual(self.namespace["composed_result"]["winning_layer"], "outer")
        self.assertEqual(self.namespace["usage_result"]["recorded_tokens"], 10)

    def test_cache_isolated_by_tenant_and_system_prompt(self):
        ns = self.namespace
        self.assertEqual(ns["text_cache"].events, ["miss", "hit", "miss"])
        self.assertEqual(ns["cache_model"]._index, 2)
        cache = ns["ScopedTextCache"]()
        model = ScriptedModel(responses=[AIMessage(content="First policy"), AIMessage(content="Second policy")])
        first = create_agent(model=model, system_prompt="Policy A", context_schema=ns["CacheContext"], middleware=[cache])
        second = create_agent(model=model, system_prompt="Policy B", context_schema=ns["CacheContext"], middleware=[cache])
        a = first.invoke({"messages": [("user", "Same question")]}, context=ns["CacheContext"](tenant="same"))
        b = second.invoke({"messages": [("user", "Same question")]}, context=ns["CacheContext"](tenant="same"))
        self.assertEqual(model._index, 2)
        self.assertNotEqual(a["messages"][-1].content, b["messages"][-1].content)

    def test_cache_does_not_reuse_tool_calls(self):
        ns = self.namespace
        cache = ns["ScopedTextCache"]()
        model = ScriptedModel(responses=[
            tool_request("add_numbers", a=1, b=2), AIMessage(content="3"),
            tool_request("add_numbers", a=1, b=2), AIMessage(content="3"),
        ])
        agent = create_agent(model=model, tools=[ns["add_numbers"]], context_schema=ns["CacheContext"], middleware=[cache])
        for _ in range(2):
            result = agent.invoke({"messages": [("user", "Same question")]}, context=ns["CacheContext"](tenant="same"))
            self.assertEqual(len([m for m in result["messages"] if m.type == "tool"]), 1)
        self.assertEqual(model._index, 4)
        self.assertEqual(cache.entries, {})

    def test_async_hooks_and_cancellation_propagate_without_retry(self):
        ns = self.namespace
        self.assertEqual(ns["cancellation_result"], "cancelled")
        self.assertEqual(ns["cancel_probe"].events.count("async:tool:enter"), 1)
        self.assertEqual(ns["cancel_probe"].events.count("async:tool:leave"), 1)
        self.assertTrue(all(event.startswith("async:") for event in ns["async_probe"].events))
        self.assertEqual(next(m for m in ns["async_result"]["messages"] if m.type == "tool").content, "9")

    def test_transformer_preserves_output_and_budget_stops_model(self):
        ns = self.namespace
        self.assertTrue(ns["observed_methods"])
        self.assertEqual(ns["stream_result"]["messages"][-1].content, "Odpowiedź w strumieniu.")
        self.assertEqual(ns["budget_model"]._index, 1)
        self.assertEqual(ns["budget_probe"].events[-1], "after_agent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
