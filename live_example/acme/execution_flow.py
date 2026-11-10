"""Present recorded agent boundaries once, retaining evidence and message provenance."""

import json
from copy import deepcopy
from pathlib import Path

from acme.dataset import connect
from acme.execution_inspector import snapshot


def merge_messages(before, updates):
    """Apply recorded message IDs without duplicating a tool call or response."""
    result = deepcopy(before)
    for message in updates:
        identifier = message.get("data", {}).get("id")
        index = next((i for i, item in enumerate(result)
                      if identifier and item.get("data", {}).get("id") == identifier), None)
        if message.get("type") == "remove":
            if identifier == "__remove_all__":
                result = []
            elif index is not None:
                result.pop(index)
        elif index is None:
            result.append(message)
        else:
            result[index] = message
    return result


def message_changes(before, after):
    """Keep additions, replacements and removals visible, including trimmed history."""
    def key(message, index):
        data = message.get("data", {})
        # The graph assigns ToolMessage.id after the tool's result was recorded.
        if message.get("type") == "tool" and data.get("tool_call_id"):
            return "tool-" + data["tool_call_id"]
        return data.get("id") or f"position-{index}"

    old = {key(m, i): m for i, m in enumerate(before)}
    new = {key(m, i): m for i, m in enumerate(after)}
    return {
        "added": [m for key, m in new.items() if key not in old],
        "changed": [m for key, m in new.items()
                    if key in old and visible_message(m) != visible_message(old[key])],
        "removed": [m for key, m in old.items() if key not in new],
    }


def visible_message(message):
    data = message.get("data", {})
    return (message.get("type"), data.get("content", ""), data.get("name"),
            data.get("tool_calls") or [], data.get("status") or "success")


def build_flow(events):
    runs = {}
    for event in events:
        runs.setdefault(event["run_id"], []).append(event)
    result = []
    for run_id, rows in runs.items():
        loaded = next((r["payload"] for r in rows if r["kind"] == "checkpoint_loaded"), {})
        state = deepcopy(loaded.get("messages", []))
        steps, requests, tools, parents = [], {}, {}, {}
        context, fields = {}, {}

        def add(row, kind, title, origin, detail):
            step = {
                "id": row["id"], "run_id": run_id, "kind": kind, "title": title,
                "origin": origin, "detail": detail, "seq": row["seq"],
                "created_at": row["created_at"], "sources": [row["id"]],
                "evidence": [], "before": deepcopy(state), "after": deepcopy(state),
                "context": deepcopy(context), "state_fields": deepcopy(fields),
                "state_basis": "Recorded message updates",
            }
            steps.append(step)
            return step

        def tool_parent(row):
            parent = row.get("parent_id")
            visited = set()
            while parent and parent not in visited:
                visited.add(parent)
                if parent in tools:
                    return tools[parent]
                parent = parents.get(parent)
            return None

        for row in rows:
            kind, payload = row["kind"], row["payload"]
            if row.get("span_id"):
                parents[row["span_id"]] = row.get("parent_id")
            if kind in {"request_accepted", "request_resumed"}:
                step = add(row, "input", "User message", "User", {
                    "text": payload.get("message", ""),
                })
                message = {"type": "human", "data": {
                    "id": payload.get("message_id"), "content": payload.get("message", ""),
                }}
                # A resumed submission may already be present in the loaded checkpoint.
                existing = any(m.get("data", {}).get("id") == payload.get("message_id")
                               for m in state)
                if not existing:
                    state = merge_messages(state, [message])
                step["after"] = deepcopy(state)
                step["detail"]["restored_messages"] = len(loaded.get("messages", []))
            elif kind == "runtime_context":
                context = {**deepcopy(payload), **{
                    k: v for k, v in context.items() if k == "resolved_customer"
                }}
            elif kind == "customer_context_resolved":
                context["resolved_customer"] = deepcopy(payload)
                step = tool_parent(row)
                if step:
                    step["context"] = deepcopy(context)
                    step["sources"].append(row["id"])
            elif kind == "model_request":
                raw_state = payload.get("state")
                edits = {"added": [], "changed": [], "removed": []}
                if isinstance(raw_state, dict):
                    captured = deepcopy(raw_state.get("messages", state))
                    edits = message_changes(state, captured)
                    state = captured
                previous_fields = fields
                if isinstance(raw_state, dict):
                    fields = {k: v for k, v in raw_state.items() if k != "messages"}
                step = add(row, "model", "Model call", "Agent → model", {
                    "system_prompt": payload.get("system_prompt", ""),
                    "input_messages": payload.get("messages", []),
                    "tools": payload.get("tools", []), "settings": payload.get("settings", {}),
                    "input_state_changes": edits,
                })
                step["state_basis"] = (
                    "Captured graph state" if raw_state else "Recorded message updates"
                )
                step["detail"]["state_field_changes"] = {
                    "values": {k: v for k, v in fields.items()
                               if k not in previous_fields or v != previous_fields[k]},
                    "removed": [k for k in previous_fields if k not in fields],
                }
                requests[row["id"]] = step
            elif kind in {"model_response", "model_error"}:
                step = requests.get(payload.get("request_event_id"))
                if step is None:
                    step = add(row, "error" if kind == "model_error" else "model",
                               "Model response", "Model", {})
                step["sources"].append(row["id"])
                if kind == "model_error":
                    step["error"] = payload
                else:
                    messages = payload.get("messages", [])
                    step["detail"]["output_messages"] = messages
                    step["before"] = deepcopy(state)
                    state = merge_messages(state, messages)
                    step["after"] = deepcopy(state)
                    step["seq"] = row["seq"]
                    if step["state_basis"] == "Captured graph state":
                        step["state_basis"] = "Captured model-input state + recorded response"
                    calls = [c for m in messages for c in m.get("data", {}).get("tool_calls", [])]
                    step["title"] = "Model requests tools" if calls else "Model answer"
            elif kind == "tool_attempt_started":
                call = payload.get("tool_call", {})
                step = add(row, "tool", call.get("name", "Tool"), "Model request → Python tool", {
                    "arguments": call.get("args", {}), "tool_call_id": call.get("id"),
                })
                tools[call.get("id", row["id"])] = step
                tools[row.get("span_id") or row["id"]] = step
            elif kind == "tool_started":
                step = tool_parent(row)
                if step is None:
                    step = add(row, "tool", payload.get("tool", "Tool"),
                               "Application → Python tool", {"direct": True})
                tools[row.get("span_id") or row["id"]] = step
            elif kind == "tool_result":
                step = tool_parent(row)
                if step is None:
                    step = add(row, "tool", payload.get("tool", "Tool result"),
                               "Application → Python tool", {"direct": True})
                step["sources"].append(row["id"])
                if step["detail"].get("direct"):
                    step["detail"]["arguments"] = payload.get("arguments", {})
                    step["detail"]["result"] = payload.get("result")
                    step["seq"] = row["seq"]
                # Native calls expose the same result once through their ToolMessage.
                if payload.get("result", {}).get("status") == "error":
                    step["error"] = payload["result"].get("error")
            elif kind == "tool_message":
                step = tools.get(payload.get("tool_call_id"))
                if step is None:
                    step = add(row, "tool", "Tool result", "Python tool", {})
                messages = payload.get("messages", [])
                step["detail"]["output_messages"] = messages
                step["sources"].append(row["id"])
                # Concurrent tools finish independently. Only this result is its delta.
                step["before"] = deepcopy(state)
                state = merge_messages(state, messages)
                step["after"] = deepcopy(state)
                step["seq"] = row["seq"]
                if any(m.get("data", {}).get("status") == "error" for m in messages):
                    step["error"] = {"message": "The tool returned an error. Inspect its result."}
            elif kind in {"sql", "retrieval", "document_read", "memory_saved", "memory_recalled",
                          "customer_terms_lookup", "approval_requested", "tool_selection_denied"}:
                step = tool_parent(row)
                evidence = {"id": row["id"], "kind": kind, "payload": payload}
                if step:
                    step["evidence"].append(evidence)
                    step["sources"].append(row["id"])
                else:
                    step = add(row, "evidence", kind.replace("_", " "), "Application service", {})
                    step["evidence"].append(evidence)
            elif kind == "context_change" and payload.get("stage") == "effective_model_request":
                step = requests.get(payload.get("request_event_id"))
                if step:
                    step["detail"]["input_changes"] = payload.get("changes", [])
            elif kind in {"run_failed", "native_tool_error", "tool_error", "retry",
                          "approval_decided", "business_decision", "tool_attempt_error"}:
                step = tool_parent(row)
                if step and "error" in kind:
                    step["error"] = payload
                    step["sources"].append(row["id"])
                else:
                    add(row, "error" if "error" in kind or "failed" in kind else "notice",
                        kind.replace("_", " "), "Runtime", payload)
            elif kind == "checkpoint_committed" and payload.get("namespace", "") == "":
                # Checkpoints verify the retained state without creating technical graph nodes.
                if steps:
                    steps[-1]["checkpoint_messages"] = payload.get("messages", [])
        steps.sort(key=lambda step: step["seq"])
        for index, step in enumerate(steps):
            step["number"] = index + 1
            step["changes"] = message_changes(step["before"], step["after"])
        result.append({
            "id": run_id, "steps": steps,
            "restored_messages": len(loaded.get("messages", [])),
        })
    return result


def inspect_flow(state: Path, selected: dict, thread_id: str) -> dict:
    conversation = snapshot(state, selected, thread_id)
    db = connect(state / "events.sqlite", readonly=True)
    try:
        rows = [dict(row) for row in db.execute(
            "SELECT id,seq,run_id,span_id,parent_id,kind,created_at,payload_json "
            "FROM events WHERE thread_id=? ORDER BY seq", (thread_id,),
        )]
    finally:
        db.close()
    for row in rows:
        row["payload"] = json.loads(row.pop("payload_json"))
    return {"runs": build_flow(rows), "event_count": len(rows), "conversation": conversation}
