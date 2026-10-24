"""Application error envelopes reach the model and trace as failed tool messages."""

import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from acme.agent import VisibilityMiddleware
from acme.app_store import new_thread
from acme.dataset import connect
from acme.demo_identity import select
from acme.runtime import submit

PROJECT = Path(__file__).resolve().parents[1]


class ScriptedToolModel(BaseChatModel):
    """Two deterministic messages; this test double makes no provider call."""

    responses: list[AIMessage]
    _index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "acme-tool-status-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self._index >= len(self.responses):
            raise RuntimeError("Scripted tool-status responses exhausted")
        message = self.responses[self._index].model_copy(deep=True)
        self._index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


class AgentToolStatusTests(unittest.TestCase):
    def test_structured_service_errors_become_failed_langchain_messages(self):
        cases = (
            ("lookup_record", {"status": "error", "error": {"code": "access_denied"}}, "error"),
            ("web_search", {"status": "error", "error": "Search unavailable"}, "error"),
            ("analyze_workspace", {"error": "Unknown file"}, "error"),
            ("lookup_record", {"status": "empty", "records": []}, "success"),
            ("my_profile", {"status": "error"}, "success"),
        )
        for name, payload, expected in cases:
            with self.subTest(name=name, payload=payload):
                request = SimpleNamespace(
                    tool_call={"name": name, "id": "call-1"},
                    runtime=SimpleNamespace(context=object()),
                )
                original = ToolMessage(
                    content=json.dumps(payload), name=name, tool_call_id="call-1"
                )
                with patch("acme.agent.span", return_value=nullcontext()), patch(
                    "acme.agent.event"
                ) as recorded:
                    output = VisibilityMiddleware().wrap_tool_call(
                        request, lambda _request: original
                    )
                self.assertEqual(output.status, expected)
                self.assertEqual(output.content, original.content)
                self.assertEqual(recorded.call_args.args[1], "tool_message")
                traced = recorded.call_args.args[2]["messages"][0]["data"]
                self.assertEqual(traced["status"], expected)
                self.assertEqual(traced["content"], original.content)

    def test_native_tool_error_is_preserved(self):
        request = SimpleNamespace(
            tool_call={"name": "lookup_record", "id": "call-2"},
            runtime=SimpleNamespace(context=object()),
        )
        native_error = ToolMessage(
            content="Argument validation failed", name="lookup_record",
            tool_call_id="call-2", status="error",
        )
        with patch("acme.agent.span", return_value=nullcontext()), patch("acme.agent.event"):
            output = VisibilityMiddleware().wrap_tool_call(request, lambda _request: native_error)
        self.assertIs(output, native_error)

    def test_full_agent_graph_keeps_structured_error_status(self):
        with tempfile.TemporaryDirectory(prefix="tool-status-", dir=PROJECT) as directory:
            state = Path(directory)
            token, _persona = select(PROJECT, state, "super_user", "all")
            thread = new_thread(PROJECT, state, token, "Tool status proof", mode="company")
            model = ScriptedToolModel(responses=[
                AIMessage(content="", tool_calls=[{
                    "name": "lookup_record",
                    "args": {"entity": "products", "record_id": ""},
                    "id": "call-invalid-record",
                    "type": "tool_call",
                }]),
                AIMessage(content="The record ID was invalid; no product was read."),
            ])
            reply = submit(
                PROJECT, state, PROJECT / "data", token, thread,
                "invalid-record-proof", "Look up a product with an empty ID",
                model=model, middleware=[],
            )
            self.assertEqual(reply["status"], "complete")
            db = connect(state / "app.sqlite", readonly=True)
            try:
                messages = [json.loads(row[0]) for row in db.execute(
                    "SELECT message_json FROM transcript WHERE run_id=? ORDER BY seq",
                    (reply["run_id"],),
                )]
            finally:
                db.close()
            tools = [message["data"] for message in messages if message["type"] == "tool"]
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["status"], "error")
            self.assertEqual(json.loads(tools[0]["content"])["error"]["code"],
                             "invalid_arguments")
            self.assertEqual(tools[0]["tool_call_id"], "call-invalid-record")
            db = connect(state / "events.sqlite", readonly=True)
            try:
                rows = [json.loads(row[0]) for row in db.execute(
                    "SELECT payload_json FROM events WHERE run_id=? AND kind='tool_message'",
                    (reply["run_id"],),
                )]
            finally:
                db.close()
            self.assertEqual(rows[-1]["messages"][0]["data"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
