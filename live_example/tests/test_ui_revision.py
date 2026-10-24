"""Behavioral regression checks for draft chats, inspection and the independent playground."""

import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import gradio as gr
from fastapi.testclient import TestClient

from acme.agent import TOOLS
from acme.app_store import (
    AccessDenied,
    event,
    list_threads,
    login,
    new_thread,
    now,
    provision,
)
from acme.chat_history import history_html
from acme.dataset import connect
from acme.execution_view import conversation_graph, filter_chats, runs
from acme.tool_catalog import (
    DETAILS,
    EXAMPLES,
    TOOL_SCHEMAS,
    document_catalog,
    report_catalog,
    run_tool,
    saved_report,
    tool_details,
)
from acme.ui import build_ui
from acme.ui_service import LearningService
from acme.web import create_web_app
from acme.web_search import search_web

PROJECT = Path(__file__).resolve().parents[1]


class UIRevision(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="acme-ui-test-")
        self.state = Path(self.temporary.name)
        self.service = LearningService(PROJECT, self.state, PROJECT / "data")
        provision(PROJECT, self.state, "tester", access_profile="super_user")
        provision(PROJECT, self.state, "other", access_profile="employee")
        self.token = login(self.state, "tester")
        self.other = login(self.state, "other")

    def tearDown(self):
        self.temporary.cleanup()

    def test_drafts_are_never_persisted(self):
        for _ in range(5):
            self.assertEqual(self.service.select(self.token), "draft:free")
            self.assertEqual(
                self.service.switch_mode(self.token, "draft:free", "company"), "draft:company"
            )
        self.assertEqual(list_threads(PROJECT, self.state, self.token), [])
        for message in ("", "  ", "x" * 8001):
            with self.assertRaises(ValueError):
                self.service.submit_chat(self.token, "draft:free", message, "invalid")
        self.assertEqual(list_threads(PROJECT, self.state, self.token), [])

    def test_prompt_visible_before_worker_and_submission_is_idempotent(self):
        thread = self.service.submit_chat(self.token, "draft:free", "Visible immediately", "one")
        self.assertEqual(
            self.service.snapshot(self.token, thread)["chat"],
            [{"role": "user", "content": "Visible immediately"}],
        )
        self.assertEqual(
            self.service.submit_chat(self.token, "draft:free", "Visible immediately", "one"), thread
        )
        self.assertEqual(len(self.service.threads(self.token)), 1)
        self.assertEqual(self.service.select(self.token), thread)
        self.assertEqual(self.service.threads(self.other), [])

    def test_saved_transcript_replaces_queued_prompt_without_duplication(self):
        thread = self.service.submit_chat(self.token, "draft:free", "First message", "one")
        db = connect(self.state / "app.sqlite")
        try:
            db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                ("run-one", thread, "one", "First message", "complete", now(), now(), None),
            )
            for role, text in [("human", "First message"), ("ai", "A unique assistant answer")]:
                db.execute(
                    "INSERT INTO transcript(thread_id,message_id,run_id,message_json,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (
                        thread,
                        role,
                        "run-one",
                        json.dumps({"type": role, "data": {"content": text}}),
                        now(),
                    ),
                )
            db.commit()
        finally:
            db.close()
        snapshot = self.service.snapshot(self.token, thread)
        self.assertEqual([m["role"] for m in snapshot["chat"]], ["user", "assistant"])
        self.assertEqual(snapshot["chat_runs"], ["run-one", "run-one"])
        self.assertEqual(
            [r["id"] for r in filter_chats(self.service, self.token, "unique assistant")], [thread]
        )

    def test_rejected_first_submission_does_not_save_empty_chat(self):
        with patch.object(self.service, "enqueue", side_effect=ValueError("queue full")):
            with self.assertRaises(ValueError):
                self.service.submit_chat(self.token, "draft:free", "Hello", "rejected")
        self.assertEqual(list_threads(PROJECT, self.state, self.token), [])

    def test_playground_is_durable_owned_and_excluded_from_chat_history(self):
        chat = self.service.submit_chat(self.token, "draft:free", "My chat", "one")
        empty = new_thread(PROJECT, self.state, self.token, "Old empty")
        workspace = self.service.playground(self.token)
        self.assertEqual(self.service.playground(self.token), workspace)
        other_workspace = self.service.playground(self.other)
        self.assertNotEqual(workspace, other_workspace)
        context = self.service.company_context(self.token, workspace)
        result = run_tool(context, "run_analysis", {"operation": "sum", "values": ["2", "3"]})
        self.assertEqual(result["facts"]["value"], "5")
        self.assertEqual(self.service.select(self.token), chat)
        history = history_html(self.service, self.token, chat)
        self.assertNotIn(workspace, history)
        self.assertNotIn(empty, history)
        self.assertIn(chat, history)
        restarted = LearningService(PROJECT, self.state, PROJECT / "data")
        self.assertEqual(restarted.playground(self.token), workspace)
        with self.assertRaises(AccessDenied):
            self.service.company_context(self.other, workspace)

    def test_document_library_and_actual_model_tool_catalog(self):
        context = self.service.company_context(self.token, self.service.playground(self.token))
        rows, choices = document_catalog(context)
        self.assertGreater(len(rows), 0)
        identifier, version = json.loads(choices[0][1])
        result = run_tool(context, "read_document", {"document_id": identifier, "version": version})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(set(EXAMPLES), {tool.name for tool in TOOLS})
        self.assertEqual(set(EXAMPLES), set(DETAILS))
        self.assertEqual(set(EXAMPLES), set(TOOL_SCHEMAS))
        for name in EXAMPLES:
            _, example, schema = tool_details(name)
            self.assertNotIn("runtime", schema["properties"])
            json.loads(example)
            TOOL_SCHEMAS[name].model_validate(EXAMPLES[name])
            next(t for t in TOOLS if t.name == name).tool_call_schema.model_validate(EXAMPLES[name])
        invalid_note = run_tool(context, "remember_note", {"topic": "x", "note": "no"})
        self.assertEqual(invalid_note["status"], "error")
        self.assertEqual(invalid_note["error"]["code"], "invalid_arguments")

    def test_playground_report_approval_and_report_browser(self):
        context = self.service.company_context(self.token, self.service.playground(self.token))
        proposal = run_tool(context, "save_report", EXAMPLES["save_report"])
        self.assertEqual(proposal["status"], "pending_approval")
        self.assertEqual(report_catalog(self.service, self.token), [])
        self.service.decision(
            self.token,
            context.thread_id,
            proposal["operation_id"],
            "approve",
            EXAMPLES["save_report"],
        )
        choices = report_catalog(self.service, self.token)
        self.assertEqual(len(choices), 1)
        self.assertIn("Learning report", saved_report(self.service, self.token, choices[0][1]))
        self.assertEqual(report_catalog(self.service, self.other), [])
        with self.assertRaises(AccessDenied):
            saved_report(self.service, self.other, choices[0][1])

    def test_chat_filters_and_owned_clickable_graph(self):
        thread = self.service.submit_chat(
            self.token, "draft:company", "Find overdue invoices", "one"
        )
        other = self.service.submit_chat(self.token, "draft:free", "Explain recursion", "two")
        self.assertEqual(
            [r["id"] for r in filter_chats(self.service, self.token, "invoices", "company", "7")],
            [thread],
        )
        self.assertEqual(filter_chats(self.service, self.token, "invoices", "free"), [])
        self.assertEqual(filter_chats(self.service, self.token, start="2099-01-01"), [])
        context = self.service.company_context(self.token, thread)
        event(
            context,
            "tool_result",
            {"tool": "<script>alert(1)</script>", "result": {"status": "ok"}},
        )
        recorded = runs(PROJECT, self.state, self.token, thread)
        graph = conversation_graph(PROJECT, self.state, self.token, thread, recorded[0]["id"])
        self.assertIn("data-step=", graph)
        self.assertNotIn("<script>", graph)
        self.assertNotIn(other, graph)
        with self.assertRaises(AccessDenied):
            conversation_graph(PROJECT, self.state, self.other, thread)

    def test_web_search_success_failure_and_bounds(self):
        context = self.service.company_context(self.token, self.service.playground(self.token))
        with patch("acme.web_search.DDGS") as provider:
            provider.return_value.text.return_value = [
                {"title": "Python", "href": "https://python.org", "body": "Official Python"},
                {"title": "Unsafe", "href": "javascript:alert(1)", "body": "skip"},
            ]
            result = search_web(context, {"query": "python"})
            self.assertEqual(len(result["results"]), 1)
            provider.return_value.text.side_effect = TimeoutError("offline")
            self.assertEqual(search_web(context, {"query": "python"})["status"], "error")
        with self.assertRaises(ValueError):
            search_web(context, {"query": "python", "max_results": 100})
        with self.assertRaises(AccessDenied):
            self.service.context(self.other, context.thread_id)

    def test_ui_build_callbacks_and_import_layout(self):
        blocks = build_ui(gr, self.service)
        callbacks = {fn.name: fn.fn for fn in blocks.fns.values() if fn.fn}
        request = gr.Request(
            request=SimpleNamespace(cookies={"acme_session": self.token}), session_hash=uuid4().hex
        )
        loaded = callbacks["load"](request)
        self.assertEqual(loaded[1]["value"], "draft:free")
        accepted = callbacks["send"]("draft:free", "Immediate UI message", "ui-one", request)
        self.assertEqual(accepted[4][0]["content"], "Immediate UI message")
        selected = accepted[3]["value"]
        navigation = callbacks["navigation"](selected, request)
        self.assertEqual(len(navigation), 3)
        self.assertEqual(len(callbacks["select_execution"](None, None, request)), 6)
        self.assertIn("history_action", callbacks)
        for path in (PROJECT / "acme").glob("*.py"):
            tree = ast.parse(path.read_text("utf-8"))
            nested_imports = [
                node
                for top in tree.body
                if not isinstance(top, (ast.Import, ast.ImportFrom))
                for node in ast.walk(top)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            self.assertFalse(nested_imports, path.name)
        blocks.close()

    def test_http_serves_custom_events_and_rejects_cross_account_actions(self):
        thread = self.service.submit_chat(self.token, "draft:free", "Owned HTTP chat", "http")
        with patch.object(LearningService, "start"), patch.object(LearningService, "close"):
            app = create_web_app(PROJECT, self.state, PROJECT / "data", gr)
            with TestClient(app, base_url="http://testserver") as client:
                client.cookies.set("acme_session", self.token)
                response = client.get("/app/config")
                self.assertEqual(response.status_code, 200)
                config = response.json()
                api_names = {d["api_name"] for d in config["dependencies"]}
                self.assertIn("history_action", api_names)
                self.assertIn("graph_pick", api_names)
                history = next(
                    c for c in config["components"] if c["props"].get("elem_id") == "history-panel"
                )
                self.assertIn("event.preventDefault()", history["props"]["js_on_load"])
                selected = client.post(
                    "/app/gradio_api/run/history_action",
                    json={
                        "data": [],
                        "event_data": {"thread": thread, "action": "select", "title": ""},
                        "session_hash": uuid4().hex,
                    },
                    headers={"Origin": "http://testserver"},
                )
                self.assertEqual(selected.status_code, 200, selected.text)
                self.assertEqual(selected.json()["data"][0]["value"], thread)
                client.cookies.set("acme_session", self.other)
                denied = client.post(
                    f"/chats/{thread}/select", headers={"Origin": "http://testserver"}
                )
                self.assertEqual(denied.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
