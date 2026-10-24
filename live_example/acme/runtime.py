"""Serialized, durable single-agent execution with idempotent accepted submissions."""

import json
from time import perf_counter
from uuid import uuid4

from langchain_core.messages import AIMessageChunk, HumanMessage, message_to_dict

from acme.agent import build_agent
from acme.app_store import RunContext, event, execution_lock, json_text, now, owned_thread
from acme.dataset import connect
from acme.demo_identity import kind_for_actor
from acme.memory_tools import open_memory
from acme.middleware import build_middleware, configuration
from acme.model_config import get_model
from acme.trace_hooks import TraceCallbacks, TracedSqliteSaver, model_catalog


def persist_messages(context, messages):
    db = connect(context.state / "app.sqlite")
    try:
        for message in messages:
            # User text is appended exactly once at acceptance. Summarization and
            # PII middleware may create/replace HumanMessages in model context;
            # those are not new messages written by the user.
            if isinstance(message, HumanMessage):
                continue
            if not message.id:
                raise ValueError("Checkpoint message must have a stable ID")
            db.execute(
                "INSERT OR IGNORE INTO "
                "transcript(thread_id,message_id,run_id,message_json,created_at) "
                "VALUES(?,?,?,?,?)",
                (
                    context.thread_id,
                    message.id,
                    context.run_id,
                    json_text(message_to_dict(message)),
                    now(),
                ),
            )
        db.commit()
    finally:
        db.close()


def _run_reply(state, run_id):
    db = connect(state / "app.sqlite", readonly=True)
    try:
        run = dict(db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())
        messages = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT message_json FROM transcript WHERE run_id=? ORDER BY seq", (run_id,)
            )
        ]
    finally:
        db.close()
    answers = [
        m["data"]["content"]
        for m in messages
        if m["type"] == "ai" and not m["data"].get("tool_calls")
    ]
    return {
        "run_id": run_id,
        "thread_id": run["thread_id"],
        "submission_id": run["submission_id"],
        "status": run["status"],
        "answer": answers[-1] if answers else None,
        "integrations": [
            "simulated_company_sqlite",
            "mock_rag_text_search",
            "local_report_store",
            "local_memory_store",
        ],
    }


def submit(
    project,
    state,
    data,
    token,
    thread_id,
    submission_id,
    text=None,
    *,
    resume=False,
    model=None,
    profile=None,
    model_name=None,
    middleware=None,
):
    """One client submission is one accepted user message and one application run.

    A retry returns a completed result. A failed/crashed run requires explicit resume;
    a checkpoint with pending work resumes without adding another human message.
    """
    if not 1 <= len(submission_id) <= 120:
        raise ValueError("submission_id must contain 1–120 characters")
    actor, conversation = owned_thread(project, state, token, thread_id, active=True)
    options = (
        None
        if middleware is None
        else {
            "preset": "python_override",
            "graph_steps": 30,
            "middleware": [type(item).__name__ for item in middleware],
        }
    )
    with execution_lock(state):
        db = connect(state / "app.sqlite")
        try:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM runs WHERE thread_id=? AND submission_id=?",
                (thread_id, submission_id),
            ).fetchone()
            if existing:
                if text is not None and text != existing["user_text"]:
                    raise ValueError("Submission ID already belongs to different text")
                run_id = existing["id"]
                if existing["status"] == "complete":
                    db.rollback()
                    return _run_reply(state, run_id)
                if not resume:
                    raise ValueError("Submission already accepted; use explicit resume")
                text = existing["user_text"]
                saved = db.execute(
                    "SELECT configuration_json FROM run_configurations WHERE run_id=?", (run_id,)
                ).fetchone()
                if saved:
                    previous = json.loads(saved[0])
                    if (previous["preset"] == "python_override") != (middleware is not None):
                        raise ValueError(
                            "Resume requires the original middleware configuration kind"
                        )
                    options = previous
                elif options is None:
                    options = configuration(project)
                db.execute(
                    "UPDATE runs SET status='running',updated_at=?,error=NULL WHERE id=?",
                    (now(), run_id),
                )
            else:
                if resume:
                    raise ValueError("No accepted submission with this ID")
                if not text or not 1 <= len(text.strip()) <= 8000:
                    raise ValueError("Message must contain 1–8000 characters")
                if db.execute(
                    "SELECT 1 FROM runs WHERE thread_id=? AND status!='complete'", (thread_id,)
                ).fetchone():
                    raise ValueError(
                        "Resume the unfinished submission before sending another message"
                    )
                if options is None:
                    options = configuration(project)
                run_id = "run-" + uuid4().hex
                db.execute(
                    "INSERT INTO runs VALUES(?,?,?,?,'running',?,?,NULL)",
                    (run_id, thread_id, submission_id, text, now(), now()),
                )
                human = HumanMessage(content=text, id="user-" + run_id)
                db.execute(
                    (
                        "INSERT INTO "
                        "transcript(thread_id,message_id,run_id,message_json,created_at) "
                        "VALUES(?,?,?,?,?)"
                    ),
                    (thread_id, human.id, run_id, json_text(message_to_dict(human)), now()),
                )
            db.execute(
                "INSERT OR IGNORE INTO run_configurations VALUES(?,?)",
                (run_id, json_text(options)),
            )
            db.commit()
        finally:
            db.close()
        context = RunContext(
            project, state, data, token, thread_id, run_id, "execution-" + uuid4().hex
        )
        started = perf_counter()
        event(
            context,
            "request_resumed" if resume else "request_accepted",
            {
                "submission_id": submission_id,
                "message_id": "user-" + run_id,
                "message": text,
                "previous_run_id": run_id if resume else None,
            },
        )
        event(
            context,
            "run_started",
            {
                "resume": resume,
                "submission_id": submission_id,
                "middleware_configuration": options,
                "recursion_limit": options["graph_steps"],
                "max_concurrency": 2,
            },
            span_id=context.execution_id,
            parent_id=run_id,
        )
        status, error = "failed", "Interrupted"
        try:
            selected = (
                model
                if model is not None
                else get_model(project_dir=project, profile=profile, model=model_name)
            )
            if middleware is None:
                middleware = build_middleware(selected, options)
            event(
                context,
                "middleware_configured",
                {
                    "configuration": options,
                    "order": [type(item).__name__ for item in middleware]
                    + ["VisibilityMiddleware"],
                    "approval": (
                        "persisted proposals; separate decision by selected local demo profile"
                    ),
                    "tool_retries": "disabled; writes require explicit idempotent approval",
                },
            )
            with (
                TracedSqliteSaver.from_conn_string(str(state / "checkpoints.sqlite")) as saver,
                open_memory(state) as memory_store,
            ):
                saver.trace_context = context
                mode = (
                    "customer"
                    if kind_for_actor(state, actor["id"]) == "customer"
                    else conversation["mode"]
                )
                agent = build_agent(selected, saver, middleware, mode=mode, store=memory_store)
                config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": options["graph_steps"],
                    # Streaming needs a waiter plus an execution worker. The outer
                    # execution_lock still serializes application runs and approvals.
                    "max_concurrency": 2,
                    "callbacks": [TraceCallbacks(context, model_catalog(selected, middleware))],
                }
                snapshot = agent.get_state(config)
                event(
                    context,
                    "checkpoint_loaded",
                    {
                        "checkpoint_id": (snapshot.config or {})
                        .get("configurable", {})
                        .get("checkpoint_id"),
                        "next": list(snapshot.next),
                        "messages": [
                            message_to_dict(m) for m in snapshot.values.get("messages", [])
                        ],
                    },
                )
                messages = snapshot.values.get("messages", [])
                accepted = any(m.id == "user-" + run_id for m in messages)
                if accepted and not snapshot.next:
                    persist_messages(context, messages)
                else:
                    inputs = (
                        None
                        if accepted
                        else {"messages": [HumanMessage(content=text, id="user-" + run_id)]}
                    )
                    preview, preview_id, published = "", None, 0
                    for channel, value in agent.stream(
                        inputs, config, context=context, stream_mode=["messages", "values"]
                    ):
                        if channel == "values":
                            persist_messages(context, value.get("messages", []))
                        else:
                            chunk, metadata = value
                            if (
                                isinstance(chunk, AIMessageChunk)
                                and isinstance(chunk.content, str)
                                and metadata.get("langgraph_node") == "model"
                            ):
                                if preview_id != chunk.id:
                                    preview, preview_id, published = "", chunk.id, 0
                                preview = (preview + chunk.content)[-32000:]
                                is_tool = bool(chunk.tool_call_chunks or chunk.tool_calls)
                                if (preview or is_tool) and (
                                    is_tool or perf_counter() - published >= 0.2
                                ):
                                    event(
                                        context,
                                        "model_stream",
                                        {
                                            "message_id": preview_id,
                                            "content": preview,
                                            "preview": True,
                                            "tool_call": is_tool,
                                        },
                                    )
                                    published = perf_counter()
                final = agent.get_state(config)
                if final.next:
                    raise RuntimeError("Run still has pending checkpoint work; resume is required")
            status, error = "complete", None
        except BaseException as exc:
            status, error = "failed", type(exc).__name__
            event(
                context,
                "run_failed",
                {"error_type": error, "message": str(exc)},
                span_id=context.execution_id,
                parent_id=run_id,
                duration_ms=(perf_counter() - started) * 1000,
            )
            raise
        finally:
            db = connect(state / "app.sqlite")
            try:
                db.execute(
                    "UPDATE runs SET status=?,updated_at=?,error=? WHERE id=?",
                    (status, now(), error, run_id),
                )
                db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), thread_id))
                db.commit()
            finally:
                db.close()
        event(
            context,
            "run_completed",
            {"run_id": run_id},
            span_id=context.execution_id,
            parent_id=run_id,
            duration_ms=(perf_counter() - started) * 1000,
        )
        return _run_reply(state, run_id)
