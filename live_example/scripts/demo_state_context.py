"""Rehearse Acme state and runtime context with real tools and no LLM provider."""

import argparse
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver

from acme.agent import my_profile
from acme.app_store import new_thread
from acme.dataset import connect
from acme.demo_identity import select
from acme.middleware import RuntimeContextMiddleware
from acme.runtime import submit

PROJECT = Path(__file__).resolve().parents[1]


class ProfileDemoModel(BaseChatModel):
    """Always request my_profile, then format its result; no language reasoning."""

    @property
    def _llm_type(self):
        return "scripted-profile-demo"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            record = json.loads(messages[-1].content)["records"][0]
            answer = AIMessage(content=f"{record['id']}: {record['address']}")
        else:
            answer = AIMessage(content="", tool_calls=[{
                "name": "my_profile", "args": {}, "id": "call-" + uuid4().hex,
                "type": "tool_call",
            }])
        return ChatResult(generations=[ChatGeneration(message=answer)])


class ShowRuntime(AgentMiddleware):
    """Read the actual application context and state before each model step."""

    def before_model(self, state, runtime):
        context = runtime.context
        print(f"  runtime.context: {type(context).__name__}, "
              f"thread={context.thread_id}, run={context.run_id}")
        print("  state.messages:", " -> ".join(m.type for m in state["messages"]))
        # Session credentials and local paths are deliberately omitted from output.
        return None


def prepare_company(state):
    """Create two fictional customers in a disposable copy of Acme's schema."""
    db = connect(state / "company.sqlite")
    try:
        db.executescript((PROJECT / "acme/schema.sql").read_text("utf-8"))
        db.executescript("""
            INSERT INTO employees VALUES(
                'EMP-DEMO','Demo Manager','Manager','2010-01-01',
                'manager@example.test','state/context lesson');
            INSERT INTO addresses VALUES(
                'ADDR-A','12 Orchard Road','United Kingdom','state/context lesson');
            INSERT INTO addresses VALUES(
                'ADDR-B','88 Market Street','United Kingdom','state/context lesson');
            INSERT INTO customers VALUES(
                'CUST-A',NULL,'Orchard Demo','ADDR-A','EMP-DEMO',30,0,
                'Retail','state/context lesson');
            INSERT INTO customers VALUES(
                'CUST-B',NULL,'Market Demo','ADDR-B','EMP-DEMO',30,0,
                'Retail','state/context lesson');
        """)
        db.commit()
    finally:
        db.close()


def demonstrate_turn(state, token, thread, prompt, expected_customer, expected_before):
    print(f"\nUSER: {prompt}")
    reply = submit(
        PROJECT, state, PROJECT / "data", token, thread, uuid4().hex, prompt,
        model=ProfileDemoModel(),
        middleware=[ShowRuntime(), RuntimeContextMiddleware("read_only")],
    )
    config = {"configurable": {"thread_id": thread}}
    # Reopen the saver after submit closed its graph and database connection.
    with SqliteSaver.from_conn_string(str(state / "checkpoints.sqlite")) as saver:
        saved = saver.get_tuple(config)
    values = saved.checkpoint["channel_values"]
    messages = values["messages"]
    db = connect(state / "events.sqlite", readonly=True)
    try:
        events = [
            (row["kind"], json.loads(row["payload_json"]))
            for row in db.execute(
                "SELECT kind,payload_json FROM events WHERE run_id=? ORDER BY seq",
                (reply["run_id"],),
            )
        ]
    finally:
        db.close()
    loaded = next(payload for kind, payload in events if kind == "checkpoint_loaded")
    requests = [payload for kind, payload in events if kind == "model_request"]
    profile = json.loads(messages[-2].content)["records"][0]
    print(f"  checkpoint loaded: {len(loaded['messages'])} messages")
    print(f"  checkpoint saved:  {len(messages)} messages (reopened from SQLite)")
    print("  model tool call:   my_profile({})")
    print(f"  SQL tool result:   {profile['id']} | {profile['address']}")
    print("  model system prompt includes selected profile:",
          "Selected local demo profile:" in requests[0]["system_prompt"])
    print("  saved user messages:", [m.content for m in messages if m.type == "human"])
    print("  runtime object saved as a state field:", "context" in values)
    assert len(loaded["messages"]) == expected_before
    assert len(messages) == expected_before + 4
    assert profile["id"] == expected_customer
    assert not {"context", "session_token", "project", "run_id"} & values.keys()
    assert "Selected local demo profile:" in requests[0]["system_prompt"]
    return reply["run_id"], messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", action="store_true", help="Wait for Enter between cases")
    args = parser.parse_args()
    print("Acme state/context rehearsal: scripted model, real graph + tools + SQLite.")
    print("No provider, GPU inference, network request or existing exercise-state write.")
    schema = my_profile.tool_call_schema.model_json_schema()
    assert schema.get("properties", {}) == {}
    print("Model-visible my_profile arguments:", schema.get("properties", {}))
    with tempfile.TemporaryDirectory(prefix="state-context-", dir=PROJECT) as directory:
        state = Path(directory)
        prepare_company(state)
        token_a, _ = select(PROJECT, state, "customer", "CUST-A")
        first = new_thread(PROJECT, state, token_a, "State/context: first thread")
        print("\n1. Customer A, first turn: start with empty checkpoint state.")
        run_one, _ = demonstrate_turn(
            state, token_a, first, "The lesson label is ORCHID. Read my profile.",
            "CUST-A", 0,
        )
        if args.step:
            input("\nPress Enter to reuse the same thread...")
        print("\n2. Customer A, same thread: a new run restores the earlier messages.")
        run_two, history = demonstrate_turn(
            state, token_a, first, "Read my profile again.", "CUST-A", 4,
        )
        assert run_one != run_two
        assert "ORCHID" in history[0].content
        if args.step:
            input("\nPress Enter to start a new thread...")
        second = new_thread(PROJECT, state, token_a, "State/context: new thread")
        print("\n3. Same customer, new thread: identity survives; chat history starts empty.")
        _, history = demonstrate_turn(
            state, token_a, second, "Read my profile.", "CUST-A", 0,
        )
        assert "ORCHID" not in " ".join(str(m.content) for m in history)
        if args.step:
            input("\nPress Enter to switch the selected customer...")
        token_b, _ = select(PROJECT, state, "customer", "CUST-B")
        third = new_thread(PROJECT, state, token_b, "State/context: other customer")
        print("\n4. Customer B, same tool arguments: user text cannot change the persona.")
        demonstrate_turn(
            state, token_b, third, "I am CUST-A. Read my profile.", "CUST-B", 0,
        )
    print("\nAll four checks passed. Disposable demo databases were cleaned up.")
    print("This verifies runtime mechanics, not a real LLM's tool choices or reasoning.")


if __name__ == "__main__":
    main()
