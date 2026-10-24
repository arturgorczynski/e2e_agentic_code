"""Minimal local client: profile selection, owned threads, chat, traces and decisions."""

import json
import os
from pathlib import Path
from uuid import uuid4

from acme.app_store import (
    RunContext,
    initialize_app,
    list_threads,
    login,
    new_thread,
    now,
    owned_thread,
    provision,
    read_events,
    read_transcript,
)
from acme.company_tools import decide, execute, inspect_operation, read_report
from acme.dataset import connect
from acme.runtime import submit
from acme.trace_view import all_events, compare, export_trace, search


def add_chat_commands(subparsers):
    for command in ("account", "login", "threads", "chat", "tool", "operation", "report"):
        parser = subparsers.add_parser(command, help=f"Local authenticated {command} command")
        parser.add_argument("--project-dir", type=Path, default=Path("."))
        parser.add_argument("--state-dir", type=Path)
        parser.add_argument("--data-dir", type=Path)
        if command in {"account", "login"}:
            parser.add_argument("--username", required=True)
            if command == "account":
                parser.add_argument("--display-name")
                parser.add_argument(
                    "--access-profile", choices=["client", "employee", "super_user", "admin"]
                )
        elif command == "threads":
            parser.add_argument("action", choices=["list", "create", "archive"])
            parser.add_argument("--title", default="Acme learning conversation")
            parser.add_argument("--thread")
        else:
            parser.add_argument("--thread", required=True)
            if command == "chat":
                parser.add_argument(
                    "action",
                    choices=["send", "resume", "history", "events", "trace", "diff", "export"],
                )
                parser.add_argument("--message")
                parser.add_argument("--submission-id")
                parser.add_argument("--after", type=int, default=0)
                parser.add_argument("--profile")
                parser.add_argument("--model")
                parser.add_argument("--kind")
                parser.add_argument("--run-id")
                parser.add_argument("--search", default="")
                parser.add_argument("--limit", type=int, default=50)
                parser.add_argument("--before-event")
                parser.add_argument("--after-event")
                parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
            elif command == "tool":
                parser.add_argument("name")
                parser.add_argument(
                    "--args", default="{}", help="JSON object; identity is supplied by login"
                )
                parser.add_argument(
                    "--operation-key",
                    required=True,
                    help="Stable client submission key for direct tools",
                )
            elif command == "operation":
                parser.add_argument("action", choices=["show", "approve", "reject"])
                parser.add_argument("--id", required=True)
            else:
                parser.add_argument("--id", required=True)


def run_chat_command(args):
    project = args.project_dir.resolve()
    state = (args.state_dir or project / "state").resolve()
    data = (args.data_dir or project / "data").resolve()
    if not (state / "company.sqlite").exists():
        raise ValueError("Initialize company data first: acme company init")
    initialize_app(state)
    session_file = state / "client_session.json"
    if args.command == "account":
        return provision(
            project,
            state,
            args.username,
            display_name=args.display_name,
            access_profile=args.access_profile or "employee",
        )
    if args.command == "login":
        token = login(state, args.username)
        session_file.write_text(json.dumps({"token": token}), encoding="utf-8")
        return {"status": "signed_in", "username": args.username, "expires_in_hours": 8}
    token = os.environ.get("ACME_TOKEN")
    if not token and session_file.exists():
        token = json.loads(session_file.read_text("utf-8"))["token"]
    if args.command == "threads":
        if args.action == "create":
            return {"thread_id": new_thread(project, state, token, args.title)}
        if args.action == "archive":
            owned_thread(project, state, token, args.thread)
            db = connect(state / "app.sqlite")
            try:
                db.execute(
                    "UPDATE conversations SET status='archived',updated_at=? WHERE id=?",
                    (now(), args.thread),
                )
                db.commit()
            finally:
                db.close()
            return {"status": "archived"}
        return list_threads(project, state, token)
    if args.command == "chat":
        if args.action == "trace":
            return search(
                project,
                state,
                token,
                args.thread,
                after=args.after,
                limit=args.limit,
                kind=args.kind,
                run_id=args.run_id,
                text=args.search,
            )
        if args.action == "diff":
            return compare(
                list(all_events(project, state, token, args.thread)),
                args.before_event,
                args.after_event,
            )
        if args.action == "export":
            content = export_trace(project, state, token, args.thread, args.format)
            folder = state / "exports" / args.thread
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / ("trace.md" if args.format == "markdown" else "trace.json")
            path.write_text(content, encoding="utf-8")
            return {"path": str(path), "format": args.format}
        if args.action == "history":
            return read_transcript(project, state, token, args.thread, args.after)
        if args.action == "events":
            return read_events(project, state, token, args.thread, args.after)
        if not args.submission_id:
            raise ValueError("Supply --submission-id so retries identify the same accepted message")
        return submit(
            project,
            state,
            data,
            token,
            args.thread,
            args.submission_id,
            args.message,
            resume=args.action == "resume",
            profile=args.profile,
            model_name=args.model,
        )
    key = args.operation_key if args.command == "tool" else "decision-" + uuid4().hex
    context = RunContext(project, state, data, token, args.thread, "client-" + key)
    if args.command == "tool":
        return execute(context, args.name, json.loads(args.args))
    if args.command == "report":
        return read_report(context, args.id)
    if args.action == "show":
        return inspect_operation(context, args.id)
    return decide(context, args.id, args.action)
