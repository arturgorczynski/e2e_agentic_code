"""Owned, paginated trace search, exact input comparisons and portable readable exports."""

import json
from difflib import unified_diff

from acme.app_store import RunContext, owned_thread
from acme.dataset import connect
from acme.tracing import difference, redact


def search(project, state, token, thread_id, *, after=0, limit=50, kind=None, run_id=None, text=""):
    owned_thread(project, state, token, thread_id)
    if not 1 <= limit <= 100 or after < 0 or len(text) > 200:
        raise ValueError("Use limit 1–100, nonnegative after, and search text up to 200 characters")
    context = RunContext(project, state, project / "data", token, thread_id, "trace-view")
    predicates, values = ["thread_id=?", "seq>?"], [thread_id, after]
    for column, value in [("kind", kind), ("run_id", run_id)]:
        if value:
            predicates.append(column + "=?")
            values.append(value)
    if text:
        predicates.append("instr(lower(payload_json),lower(?))>0")
        values.append(text)
    db = connect(state / "events.sqlite", readonly=True)
    try:
        rows = db.execute(
            "SELECT * FROM events WHERE " + " AND ".join(predicates) + " ORDER BY seq LIMIT ?",
            [*values, limit + 1],
        ).fetchall()
    finally:
        db.close()
    items = []
    for row in rows[:limit]:
        item = dict(row)
        payload, display_paths = redact(context, json.loads(item.pop("payload_json")))
        paths = json.loads(item.pop("redaction_paths_json")) + display_paths
        item.update(
            payload=payload,
            redacted=bool(item["redacted"] or paths),
            redaction_paths=sorted(set(paths)),
            capture="legacy" if item["trace_version"] < 2 else "boundary-v2",
        )
        items.append(item)
    return {
        "events": items,
        "has_more": len(rows) > limit,
        "next_cursor": items[-1]["seq"] if len(rows) > limit else None,
    }


def all_events(project, state, token, thread_id):
    after = 0
    while True:
        page = search(project, state, token, thread_id, after=after, limit=100)
        yield from page["events"]
        if not page["has_more"]:
            break
        after = page["next_cursor"]


def compare(events, before_id, after_id):
    selected = {row["id"]: row for row in events if row["id"] in {before_id, after_id}}
    if set(selected) != {before_id, after_id}:
        raise ValueError("Both event IDs must belong to this conversation")
    before, after = selected[before_id], selected[after_id]
    if before["kind"] != "model_request" or after["kind"] != "model_request":
        raise ValueError("Choose two model_request event IDs")
    left, right = before["payload"], after["payload"]
    return {
        "before_event_id": before_id,
        "after_event_id": after_id,
        "redacted": before["redacted"] or after["redacted"],
        "before": left,
        "after": right,
        "message_changes": difference(left["messages"], right["messages"]),
        "unified_diff": "\n".join(
            unified_diff(
                json.dumps(left, indent=2, ensure_ascii=False, sort_keys=True).splitlines(),
                json.dumps(right, indent=2, ensure_ascii=False, sort_keys=True).splitlines(),
                fromfile=before_id,
                tofile=after_id,
                lineterm="",
            )
        ),
    }


def provenance(events):
    """Link every main-model message to earlier recorded evidence without invented attribution."""
    origins = {}
    tool_origins = {}
    unassigned_origins = {}
    requests = []
    for row in events:
        payload = row["payload"]
        if row["kind"] == "request_accepted":
            origins[payload["message_id"]] = {"event_id": row["id"], "kind": row["kind"]}
        if row["kind"] in {"model_response", "tool_message", "context_change", "checkpoint_loaded"}:
            messages = payload.get("after", payload.get("messages", []))
            before = {m.get("data", {}).get("id"): m for m in payload.get("before", [])}
            for message in messages:
                data = message.get("data", {})
                identifier = data.get("id")
                origin = {
                    "event_id": row["id"],
                    "kind": row["kind"],
                    "stage": payload.get("stage"),
                    "tool_call_id": data.get("tool_call_id"),
                    "span_id": row["parent_id"],
                }
                tool_key = (row["run_id"], data.get("tool_call_id"))
                if row["kind"] == "tool_message":
                    tool_origins[tool_key] = origin
                if identifier is None:
                    unassigned_origins[(row["run_id"], message_content_key(message))] = origin
                changed = (
                    row["kind"] == "context_change"
                    and identifier in before
                    and before[identifier] != message
                )
                if identifier and (identifier not in origins or changed):
                    content_key = (row["run_id"], message_content_key(message))
                    source = unassigned_origins.get(content_key)
                    if identifier not in before and source:
                        origin = {**source, "matched_by": "exact content before ID assignment"}
                    origins[identifier] = tool_origins.get(tool_key, origin)
        if row["kind"] == "model_request":
            for message in payload["messages"]:
                data = message.get("data", {})
                tool_key = (row["run_id"], data.get("tool_call_id"))
                if data.get("id") not in origins and tool_key in tool_origins:
                    origins[data["id"]] = tool_origins[tool_key]
                content_key = (row["run_id"], message_content_key(message))
                if data.get("id") not in origins and content_key in unassigned_origins:
                    origins[data["id"]] = {
                        **unassigned_origins[content_key],
                        "matched_by": "exact content before ID assignment",
                    }
            requests.append(
                {
                    "request_event_id": row["id"],
                    "system_source": {"event_id": row["id"], "field": "system_prompt"},
                    "messages": [
                        {
                            "index": i,
                            "message_id": m.get("data", {}).get("id"),
                            "source": origins.get(
                                m.get("data", {}).get("id"),
                                {
                                    "event_id": row["id"],
                                    "kind": "effective_request_only",
                                    "note": "Inspect context_change and parent spans",
                                },
                            ),
                        }
                        for i, m in enumerate(payload["messages"])
                    ],
                }
            )
    return requests


def message_content_key(message):
    return json.dumps(
        {**message, "data": {**message.get("data", {}), "id": None}},
        sort_keys=True,
        ensure_ascii=False,
    )


def export_trace(project, state, token, thread_id, format="markdown"):
    if format not in {"markdown", "json"}:
        raise ValueError("Export format must be markdown or json")
    events = list(all_events(project, state, token, thread_id))
    requests = [row for row in events if row["kind"] == "model_request"]
    comparisons = [compare(events, a["id"], b["id"]) for a, b in zip(requests, requests[1:])]
    report = {
        "thread_id": thread_id,
        "boundary": "Observable LangChain/application inputs and outputs",
        "hidden_reasoning": False,
        "http_wire_dump": False,
        "redacted": any(row["redacted"] for row in events),
        "events": events,
        "model_input_diffs": comparisons,
        "provenance": provenance(events),
    }
    if format == "json":
        return json.dumps(report, indent=2, ensure_ascii=False)
    lines = [
        f"# Execution trace: {thread_id}",
        "",
        "Observable LangChain/application inputs and outputs. "
        "Not hidden reasoning or an HTTP wire dump.",
        "",
        f"Redacted payloads: **{report['redacted']}**. Each event lists its redaction paths.",
        "",
        "## Timeline",
        "",
        "| Seq | Event | Run | Parent | Duration ms | Redacted |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in events:
        lines.append(
            f"| {row['seq']} | {row['kind']} | {row['run_id']} | {row['parent_id']} | "
            f"{row['duration_ms']} | {row['redacted']} |"
        )
    lines.extend(
        [
            "",
            "## Context provenance",
            "",
            "````json",
            json.dumps(report["provenance"], indent=2, ensure_ascii=False),
            "````",
        ]
    )
    for diff in comparisons:
        lines.extend(
            ["", "## Consecutive model inputs", "", "````diff", diff["unified_diff"], "````"]
        )
    for row in events:
        lines.extend(
            [
                "",
                f"## {row['seq']}: {row['kind']} ({row['id']})",
                "",
                "````json",
                json.dumps(row, indent=2, ensure_ascii=False),
                "````",
            ]
        )
    return "\n".join(lines) + "\n"
