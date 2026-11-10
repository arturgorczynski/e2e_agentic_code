"""Conversation lifecycle and evidence flow through real Acme tools and SQLite."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from acme.app_store import new_thread
from acme.company_tools import execute
from acme.dataset import connect
from acme.demo_identity import select
from acme.execution_flow import build_flow, inspect_flow, message_changes
from acme.middleware import RuntimeContextMiddleware
from acme.portal import create_portal
from acme.runtime import submit
from acme.ui_service import LearningService
from scripts.demo_state_context import ProfileDemoModel, prepare_company
from tests.test_agent_tool_status import ScriptedToolModel

PROJECT = Path(__file__).resolve().parents[1]


class ConversationExperience(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="experience-test-", dir=PROJECT)
        self.state = Path(self.temporary.name)
        prepare_company(self.state)
        self.token, self.persona = select(PROJECT, self.state, "customer", "CUST-A")
        self.thread = new_thread(PROJECT, self.state, self.token, "Address lesson")
        self.submit("one", "ORCHID: read my profile.")

    def tearDown(self):
        self.temporary.cleanup()

    def submit(self, identifier, text):
        return submit(
            PROJECT, self.state, PROJECT / "data", self.token, self.thread, identifier, text,
            model=ProfileDemoModel(), middleware=[RuntimeContextMiddleware("read_only")],
        )

    def client(self, token=None):
        client = TestClient(create_portal(PROJECT, self.state, PROJECT / "data"))
        client.cookies.set("acme_portal", token or self.token)
        return client

    def test_real_flow_groups_duplicates_and_preserves_sql_provenance_and_state(self):
        self.submit("two", "Read my profile again.")
        result = inspect_flow(self.state, self.persona, self.thread)
        self.assertEqual(len(result["runs"]), 2)
        for index, run in enumerate(result["runs"]):
            self.assertEqual(run["restored_messages"], index * 4)
            steps = run["steps"]
            self.assertEqual([s["kind"] for s in steps],
                             ["input", "model", "tool", "model"])
            tool = steps[2]
            self.assertEqual(tool["title"], "my_profile")
            self.assertEqual(tool["detail"]["arguments"], {})
            self.assertEqual(len(tool["evidence"]), 2)
            self.assertTrue(all(e["payload"]["parameters"] == ["CUST-A"]
                                for e in tool["evidence"]))
            self.assertTrue(all(e["payload"]["parameter_sources"] == [
                "Authenticated persona.subject_id via runtime.context.session_token"
            ] for e in tool["evidence"]))
            self.assertEqual(tool["context"]["resolved_customer"]["subject_id"], "CUST-A")
            self.assertEqual(steps[-1]["context"]["resolved_customer"]["subject_id"], "CUST-A")
            self.assertFalse(steps[0]["context"])
            self.assertEqual(len(tool["changes"]["added"]), 1)
            self.assertEqual(tool["changes"]["added"][0]["type"], "tool")
            self.assertEqual(len(steps[-1]["after"]), (index + 1) * 4)
            self.assertEqual(steps[1]["state_basis"],
                             "Captured model-input state + recorded response")
            self.assertIn("Selected local demo profile:", steps[1]["detail"]["system_prompt"])
            self.assertEqual(steps[1]["context"]["actor_id"], self.persona["actor_id"])
            self.assertNotIn(self.token, json.dumps(run))

    def test_rename_trash_restore_survive_reopening_and_keep_execution(self):
        with patch.object(LearningService, "start"), self.client() as client:
            response = client.patch(f"/api/conversations/{self.thread}",
                                    json={"title": "Saved name"})
            self.assertEqual(response.status_code, 200, response.text)
            response = client.patch(f"/api/conversations/{self.thread}",
                                    json={"status": "archived"})
            self.assertEqual(response.status_code, 200, response.text)
        with patch.object(LearningService, "start"), self.client() as reopened:
            rows = reopened.get("/api/execution/conversations").json()
            row = next(r for r in rows if r["id"] == self.thread)
            self.assertEqual((row["title"], row["topic"], row["status"]),
                             ("Saved name", "Saved name", "archived"))
            self.assertTrue(row["can_manage"])
            flow = reopened.get(f"/api/execution/conversations/{self.thread}/flow")
            self.assertEqual(flow.status_code, 200)
            self.assertEqual(len(flow.json()["runs"][0]["steps"]), 4)
            self.assertEqual(reopened.post("/api/chat", json={
                "text": "Cannot send to trash", "thread_id": self.thread,
            }).status_code, 400)
            self.assertEqual(reopened.patch(f"/api/conversations/{self.thread}",
                                           json={"title": "Renamed in trash"}).status_code, 200)
            self.assertEqual(reopened.get("/api/conversations").json()[0]["status"], "archived")
            self.assertEqual(reopened.patch(f"/api/conversations/{self.thread}",
                                           json={"status": "active"}).status_code, 200)
            self.assertEqual(reopened.get("/api/conversations").json()[0]["title"],
                             "Renamed in trash")

    def test_another_customer_cannot_read_flow_or_manage_thread(self):
        other, _ = select(PROJECT, self.state, "customer", "CUST-B")
        with patch.object(LearningService, "start"), self.client(other) as client:
            self.assertEqual(client.get("/api/conversations").json(), [])
            self.assertEqual(client.get(f"/api/execution/conversations/{self.thread}/flow")
                             .status_code, 403)
            for body in ({"title": "Wrong owner"}, {"status": "archived"}):
                self.assertEqual(client.patch(f"/api/conversations/{self.thread}", json=body)
                                 .status_code, 403)

    def test_chat_creation_is_idempotent_and_busy_thread_cannot_be_deleted(self):
        with patch.object(LearningService, "start"), self.client() as client:
            payload = {"text": "A new conversation", "submission_id": "stable-submission"}
            first = client.post("/api/chat", json=payload)
            again = client.post("/api/chat", json=payload)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json()["thread_id"], again.json()["thread_id"])
            identifier = first.json()["thread_id"]
            response = client.patch(f"/api/conversations/{identifier}", json={"status": "archived"})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(client.patch(f"/api/conversations/{self.thread}",
                                          json={"title": "   "}).status_code, 400)

    def test_message_diff_tracks_replacement_removal_and_ignores_metadata_noise(self):
        before = [{"type": "human", "data": {"id": "a", "content": "old"}}]
        after = [{"type": "human", "data": {"id": "a", "content": "new"}}]
        self.assertEqual(message_changes(before, after)["changed"], after)
        self.assertEqual(message_changes(before, [])["removed"], before)
        metadata = [{"type": "human", "data": {"id": "a", "content": "old", "extra": {}}}]
        self.assertFalse(any(message_changes(before, metadata).values()))

    def test_recorded_model_failure_is_not_rendered_as_an_answer(self):
        db = connect(self.state / "events.sqlite", readonly=True)
        try:
            rows = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY seq")]
        finally:
            db.close()
        for row in rows:
            row["payload"] = json.loads(row["payload_json"])
        first = next(r for r in rows if r["kind"] == "model_request")
        failure = {**first, "id": "test-error", "kind": "model_error", "seq": first["seq"] + 1,
                   "payload": {"request_event_id": first["id"], "message": "Provider failed"}}
        run = build_flow([r for r in rows if r["seq"] <= first["seq"]] + [failure])[0]
        self.assertIn("error", run["steps"][-1])
        self.assertNotIn("output_messages", run["steps"][-1]["detail"])

    def test_overlapping_tools_keep_independent_deltas_in_result_order(self):
        rows = []
        for kind, payload, span in [
            ("tool_attempt_started", {"tool_call": {"id": "a", "name": "first"}}, "span-a"),
            ("tool_attempt_started", {"tool_call": {"id": "b", "name": "second"}}, "span-b"),
            ("tool_message", {"tool_call_id": "b", "messages": [
                {"type": "tool", "data": {"content": "second result", "tool_call_id": "b"}},
            ]}, None),
            ("tool_message", {"tool_call_id": "a", "messages": [
                {"type": "tool", "data": {"content": "first result", "tool_call_id": "a"}},
            ]}, None),
        ]:
            rows.append({"id": str(len(rows)), "seq": len(rows), "run_id": "overlap",
                         "created_at": "test", "kind": kind, "payload": payload,
                         "span_id": span})
        steps = build_flow(rows)[0]["steps"]
        self.assertEqual([step["title"] for step in steps], ["second", "first"])
        self.assertEqual([len(step["changes"]["added"]) for step in steps], [1, 1])
        self.assertEqual([len(step["after"]) for step in steps], [1, 2])
        self.assertEqual(steps[1]["changes"]["added"][0]["data"]["content"], "first result")

    def test_captured_middleware_replacements_and_custom_fields_remain_visible(self):
        before = {"type": "human", "data": {"id": "a", "content": "Original text"}}
        after = {"type": "human", "data": {"id": "a", "content": "Redacted text"}}
        rows = [
            {"kind": "checkpoint_loaded", "payload": {"messages": [before]}},
            {"kind": "model_request", "payload": {
                "state": {"messages": [after], "model_call_count": 1}, "messages": [after],
            }},
        ]
        for index, row in enumerate(rows):
            row.update(id=str(index), seq=index, run_id="edited", created_at="test")
        steps = build_flow(rows)[0]["steps"]
        self.assertEqual([step["kind"] for step in steps], ["model"])
        self.assertEqual(steps[0]["detail"]["input_state_changes"]["changed"], [after])
        self.assertEqual(steps[0]["detail"]["state_field_changes"]["values"],
                         {"model_call_count": 1})

    def test_direct_tool_workspace_retains_result_without_fabricating_chat_state(self):
        service = LearningService(PROJECT, self.state, PROJECT / "data")
        context = service.company_context(self.token, None)
        output = execute(context, "list_records", {"entity": "products", "limit": 2})
        self.assertEqual(output["status"], "empty")
        flow = inspect_flow(self.state, self.persona, context.thread_id)
        steps = flow["runs"][0]["steps"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["title"], "list_records")
        self.assertTrue(steps[0]["detail"]["direct"])
        self.assertEqual(steps[0]["detail"]["result"], output)
        self.assertTrue(steps[0]["evidence"])
        self.assertEqual(steps[0]["after"], [])

    def test_native_company_tool_groups_its_nested_service_events_once(self):
        token, persona = select(PROJECT, self.state, "super_user", "all")
        thread = new_thread(PROJECT, self.state, token, "Native service evidence")
        model = ScriptedToolModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "list_records", "args": {"entity": "products", "limit": 2},
                "id": "native-list", "type": "tool_call",
            }]),
            AIMessage(content="There are no products in this fixture."),
        ])
        submit(PROJECT, self.state, PROJECT / "data", token, thread, "native-service",
               "List products", model=model, middleware=[RuntimeContextMiddleware("read_only")])
        steps = inspect_flow(self.state, persona, thread)["runs"][0]["steps"]
        tool_steps = [step for step in steps if step["kind"] == "tool"]
        self.assertEqual(len(tool_steps), 1)
        self.assertFalse(tool_steps[0]["detail"].get("direct"))
        self.assertEqual(len(tool_steps[0]["changes"]["added"]), 1)
        self.assertTrue(tool_steps[0]["evidence"])
        self.assertEqual(len(steps[-1]["after"]), 4)


if __name__ == "__main__":
    unittest.main()
