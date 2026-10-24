"""The agent must not report a textual imitation of a tool call as execution."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain.agents.middleware import ModelResponse
from langchain_core.messages import AIMessage

from acme.middleware import NativeToolCallGuardMiddleware, textual_tool_call


class FakeRequest:
    def __init__(self, system_prompt="Use tools for records"):
        self.system_prompt = system_prompt
        self.tools = [SimpleNamespace(name="lookup_record")]
        self.runtime = SimpleNamespace(context=object())

    def override(self, **changes):
        return FakeRequest(changes["system_message"].content)


class NativeToolCallGuardTests(unittest.TestCase):
    def setUp(self):
        self.request = FakeRequest()
        self.fake_call = ModelResponse(
            result=[
                AIMessage(
                    content="<function=lookup_record>\n<parameter=entity>invoices</parameter>"
                    "\n</function>\n</tool_call>"
                )
            ]
        )
        self.native_call = ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "lookup_record",
                            "args": {"entity": "invoices", "record_id": "INV-1"},
                            "id": "call-1",
                        }
                    ],
                )
            ]
        )

    def test_detects_only_offered_tool_markup_without_native_call(self):
        self.assertTrue(textual_tool_call(self.fake_call, self.request.tools))
        self.assertTrue(
            textual_tool_call(
                ModelResponse(result=[AIMessage(content="<function=lookup_record>\n<parameter=entity>")]),
                self.request.tools,
            )
        )
        self.assertFalse(textual_tool_call(self.native_call, self.request.tools))
        self.assertFalse(
            textual_tool_call(
                ModelResponse(
                    result=[
                        AIMessage(content="<function=lookup_record></function>"),
                        self.native_call.result[0],
                    ]
                ),
                self.request.tools,
            )
        )
        self.assertFalse(
            textual_tool_call(
                ModelResponse(result=[AIMessage(content="An example: <function=lookup_record>")]),
                self.request.tools,
            )
        )
        self.assertFalse(
            textual_tool_call(
                ModelResponse(result=[AIMessage(content="<function=unknown></tool_call>")]),
                self.request.tools,
            )
        )

    def test_retries_once_and_accepts_only_a_native_call(self):
        calls = []

        def handler(request):
            calls.append(request.system_prompt)
            return self.fake_call if len(calls) == 1 else self.native_call

        with patch("acme.middleware.event") as recorded:
            result = NativeToolCallGuardMiddleware().wrap_model_call(self.request, handler)
        self.assertIs(result, self.native_call)
        self.assertEqual(len(calls), 2)
        self.assertIn("No tool ran", calls[1])
        self.assertEqual(recorded.call_args.args[1], "native_tool_call_retry")

    def test_fails_instead_of_accepting_an_unverified_answer(self):
        replies = iter(
            [self.fake_call, ModelResponse(result=[AIMessage(content="It is GBP 2,500")])]
        )
        with patch("acme.middleware.event") as recorded:
            with self.assertRaisesRegex(RuntimeError, "native tool call"):
                NativeToolCallGuardMiddleware().wrap_model_call(
                    self.request, lambda _request: next(replies)
                )
        self.assertEqual(recorded.call_args.args[1], "native_tool_call_failed")

    def test_removes_trailing_orphan_marker_but_preserves_raw_provider_message(self):
        raw = ModelResponse(result=[AIMessage(content="Verified answer.<tool_call>", id="ai-1")])
        with patch("acme.middleware.event") as recorded:
            result = NativeToolCallGuardMiddleware().wrap_model_call(
                self.request, lambda _request: raw
            )
        self.assertEqual(result.result[0].content, "Verified answer.")
        self.assertEqual(raw.result[0].content, "Verified answer.<tool_call>")
        self.assertEqual(recorded.call_args.args[1], "provider_markup_removed")
