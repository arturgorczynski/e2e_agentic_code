"""Conversation-first execution inspection, using owned persisted evidence only."""

import html
import json
from datetime import UTC, datetime, timedelta

from acme.app_store import owned_thread
from acme.dataset import connect
from acme.trace_view import all_events


def filter_chats(service, token, words="", mode="all", period="all", start="", end=""):
    """Search owned titles and accepted messages, with UTC date boundaries."""
    rows = service.threads(token, None if mode == "all" else mode)
    if mode not in {"all", "free", "company"} or period not in {"all", "1", "7", "30"}:
        raise ValueError("Choose a valid mode and time filter")
    cutoff = (
        (datetime.now(UTC) - timedelta(days=int(period))).isoformat() if period != "all" else ""
    )
    for value in (start, end):
        if value:
            datetime.strptime(value, "%Y-%m-%d")
    if start and end and start > end:
        raise ValueError("The start date must not be later than the end date")
    db = connect(service.state / "app.sqlite", readonly=True)
    try:
        result = []
        for row in rows:
            if cutoff and row["updated_at"] < cutoff:
                continue
            if start and row["updated_at"][:10] < start:
                continue
            if end and row["updated_at"][:10] > end:
                continue
            if words.strip():
                messages = db.execute(
                    "SELECT user_text FROM runs WHERE thread_id=? UNION "
                    "SELECT user_text FROM ui_requests WHERE thread_id=?",
                    (row["id"], row["id"]),
                ).fetchall()
                content = [r[0] or "" for r in messages]
                for stored in db.execute(
                    "SELECT message_json FROM transcript WHERE thread_id=?", (row["id"],)
                ):
                    message = json.loads(stored[0])
                    if message["type"] in {"human", "ai"}:
                        value = message["data"].get("content", "")
                        content.append(
                            value
                            if isinstance(value, str)
                            else " ".join(b.get("text", "") for b in value if isinstance(b, dict))
                        )
                haystack = (row["title"] + " " + " ".join(content)).casefold()
                if not all(word in haystack for word in words.casefold().split()):
                    continue
            result.append(row)
        return result
    finally:
        db.close()


def conversation_graph(project, state, token, thread, selected_run=None, selected_step=None):
    if not thread or thread.startswith("draft:"):
        return "<p>Choose a populated chat to see its conversation graph.</p>"
    items = runs(project, state, token, thread)
    graph = [
        '<div class="graph-legend"><span>🟢 Message</span><span>🟣 Model</span>'
        "<span>🔵 Tool / data</span><span>🟠 Context / approval</span></div>",
        '<div class="execution-graph" aria-label="Conversation execution graph">',
    ]
    for run in reversed(items):
        run_id = html.escape(run["id"], quote=True)
        graph.append('<div class="graph-run">')
        graph.append(
            f'<button class="graph-node run" data-run="{run_id}" '
            f'aria-pressed="{str(run["id"] == selected_run).lower()}">'
            f"{html.escape(run['user_text'][:160])}"
            f"<small>{html.escape(run['created_at'])} · "
            f"{html.escape(run['status'])}</small></button>"
        )
        if run["id"] == selected_run:
            for row in steps(project, state, token, thread, run["id"]):
                kind = row["kind"]
                category = (
                    "error"
                    if "error" in kind or "failed" in kind
                    else "model"
                    if kind.startswith("model")
                    else "context"
                    if "context" in kind or "approval" in kind
                    else "tool"
                )
                graph.append('<div class="graph-edge" aria-hidden="true"></div>')
                graph.append(
                    f'<button class="graph-node {category}" data-run="{run_id}" '
                    f'data-step="{html.escape(row["id"], quote=True)}" '
                    f'aria-pressed="{str(row["id"] == selected_step).lower()}">'
                    f"{html.escape(describe(row))}<small>{row['created_at'][11:19]} UTC"
                    "</small></button>"
                )
        graph.append(
            '</div><div class="graph-edge" style="align-self:center" aria-hidden="true"></div>'
        )
    return "".join(graph) + "</div>"


STEP_NAMES = {
    "request_accepted": "Your message",
    "request_resumed": "Resume",
    "middleware_configured": "Middleware settings",
    "runtime_context": "Identity and tools",
    "model_request": "Model input",
    "model_response": "Model output",
    "tool_attempt": "Tool call",
    "tool_result": "Tool result",
    "tool_error": "Tool error",
    "workspace_tool_result": "Workspace result",
    "context_change": "Context changed",
    "retrieval": "Document search",
    "document_read": "Document content",
    "sql": "Database query",
    "approval_requested": "Approval requested",
    "approval_decided": "Approval decision",
    "run_failed": "Execution failed",
    "run_completed": "Execution completed",
    "provider_error": "Model error",
    "retry": "Retry",
    "checkpoint_saved": "Context saved",
    "artifact_created": "File created",
    "analysis_started": "Analysis started",
    "analysis_completed": "Analysis completed",
    "analysis_failed": "Analysis failed",
}


def runs(project, state, token, thread):
    owned_thread(project, state, token, thread)
    db = connect(state / "app.sqlite", readonly=True)
    try:
        accepted = [
            dict(row)
            for row in db.execute(
                "SELECT id,user_text,status,created_at FROM runs WHERE thread_id=? "
                "ORDER BY created_at DESC LIMIT 200",
                (thread,),
            )
        ]
    finally:
        db.close()
    events = connect(state / "events.sqlite", readonly=True)
    try:
        direct = events.execute(
            "SELECT run_id,MIN(created_at) AS created_at FROM events WHERE thread_id=? "
            "GROUP BY run_id ORDER BY created_at DESC LIMIT 200",
            (thread,),
        ).fetchall()
        known = {row["id"] for row in accepted}
        for row in direct:
            if row["run_id"] in known:
                continue
            tool = events.execute(
                "SELECT kind,payload_json FROM events WHERE thread_id=? AND run_id=? "
                "AND kind IN ('tool_result','tool_error',"
                "'workspace_tool_result','analysis_started') "
                "ORDER BY seq LIMIT 1",
                (thread, row["run_id"]),
            ).fetchone()
            if tool:
                payload = json.loads(tool["payload_json"])
                outcome = payload.get("result", {}).get("status")
                status = (
                    "error"
                    if tool["kind"] == "tool_error" or outcome == "error"
                    else "pending approval"
                    if outcome == "pending_approval"
                    else "complete"
                    if tool["kind"] == "tool_result"
                    else "recorded"
                )
                accepted.append(
                    {
                        "id": row["run_id"],
                        "created_at": row["created_at"],
                        "user_text": "Direct tool: " + payload.get("tool", tool["kind"]),
                        "status": status,
                    }
                )
        return sorted(accepted, key=lambda row: (row["created_at"], row["id"]), reverse=True)[:200]
    finally:
        events.close()


def steps(project, state, token, thread, run_id):
    """Filter by owned conversation before selecting a run supplied by the browser."""
    return [
        row
        for row in all_events(project, state, token, thread)
        if row["run_id"] == run_id and row["kind"] in STEP_NAMES
    ]


def describe(row):
    payload = row["payload"]
    name = STEP_NAMES.get(row["kind"], row["kind"].replace("_", " ").title())
    detail = payload.get("tool") or payload.get("label") or payload.get("stage") or ""
    return name + (": " + str(detail) if detail else "")


def detail(row):
    payload, kind = row["payload"], row["kind"]
    if kind in {"request_accepted", "request_resumed"}:
        incoming, outgoing = payload, None
        explanation = "The application accepted this user message for the selected execution."
    elif kind == "model_request":
        incoming = {k: payload.get(k) for k in ["system_prompt", "messages", "tools", "settings"]}
        outgoing = None
        explanation = (
            "This is the effective prompt, conversation and tool schemas sent to the model."
        )
    elif kind == "model_response":
        incoming, outgoing = {"request_event_id": payload.get("request_event_id")}, payload
        explanation = "The model returned these messages and requested tool calls, if any."
    elif kind == "tool_result":
        incoming, outgoing = payload.get("arguments"), payload.get("result")
        explanation = "These validated arguments produced this recorded tool result."
    elif kind == "context_change":
        incoming, outgoing = payload.get("before"), payload.get("after")
        explanation = "Compare what was in model context before and after this change."
    elif kind == "sql":
        incoming = {k: payload.get(k) for k in ["sql", "parameters", "permission"]}
        outgoing = {"row_count": payload.get("row_count")}
        explanation = "This prepared database query actually ran; the row count is recorded."
    else:
        incoming, outgoing, explanation = (
            None,
            payload,
            "Recorded application activity for this execution.",
        )
    summary = (
        f"### {describe(row)}\n{explanation}\n\n"
        f"Time: **{row['created_at'][11:19]} UTC** · Event **{row['seq']}**"
        + (" · Payload redacted" if row["redacted"] else "")
    )
    return summary, incoming, outgoing, row


def run_summary(rows, run):
    model = sum(row["kind"] == "model_request" for row in rows)
    tools = sum(row["kind"] == "tool_result" for row in rows)
    changes = sum(row["kind"] == "context_change" for row in rows)
    return (
        f"**{run['status'].title()}** · {model} model calls · {tools} company tool results · "
        f"{changes} context changes\n\nSelect a step below to see its input and output. "
        "Intermediate assistant messages remain here even when Chat shows only the final answer."
    )
