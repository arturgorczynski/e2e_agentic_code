"""Owned UI actions and a persisted queue; browser connections do not own agent jobs."""

import hashlib
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
from uuid import uuid4

from acme.app_store import (
    RunContext,
    authenticate,
    initialize_app,
    list_threads,
    new_thread,
    now,
    owned_thread,
    read_transcript,
)
from acme.company_tools import decide, execute, inspect_operation
from acme.dataset import connect
from acme.job_recovery import recover_jobs, shutdown_jobs
from acme.jobs import initialize_jobs, list_files, list_jobs
from acme.trace_view import all_events, compare, search

SCHEMA = """
CREATE TABLE IF NOT EXISTS ui_requests(
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, thread_id TEXT NOT NULL,
 submission_id TEXT NOT NULL, user_text TEXT, resume INTEGER NOT NULL,
 status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(thread_id, submission_id, resume));
CREATE TABLE IF NOT EXISTS ui_selection(owner_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ui_workspaces(owner_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL);
"""


class LearningService:
    """One server, one queue consumer, explicit owned subprocess handles."""

    def __init__(self, project, state, data):
        self.project, self.state, self.data = project, state, data
        initialize_app(state)
        initialize_jobs(state)
        db = connect(state / "app.sqlite")
        try:
            db.executescript(SCHEMA)
        finally:
            db.close()
        self.queue = queue.Queue(maxsize=20)
        self.worker = None
        self.process = None
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.server_lease = None

    def start(self):
        # Called only by the single server's lifespan, never by importing the module.
        self.server_lease = sqlite3.connect(
            self.state / "webserver.sqlite", timeout=0, check_same_thread=False
        )
        try:
            self.server_lease.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            self.server_lease.close()
            self.server_lease = None
            raise RuntimeError("Another Acme UI already uses this state directory") from exc
        db = connect(self.state / "app.sqlite")
        try:
            db.execute(
                "UPDATE ui_requests SET status='interrupted',error=? "
                "WHERE status IN ('queued','running')",
                ("Server restarted. Use Resume unfinished message.",),
            )
            db.commit()
        finally:
            db.close()
        self.worker = threading.Thread(target=self.consume, name="acme-agent-queue", daemon=True)
        recover_jobs(self.state)
        self.worker.start()

    def close(self):
        self.stopping.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
        while not self.queue.empty():
            self.queue.get_nowait()
        self.queue.put_nowait(None)
        if self.worker:
            self.worker.join(timeout=10)
        shutdown_jobs(self.state)
        if self.server_lease:
            self.server_lease.close()
            self.server_lease = None

    def context(self, token, thread_id):
        context = RunContext(
            self.project, self.state, self.data, token, thread_id, "ui-" + uuid4().hex
        )
        owned_thread(self.project, self.state, token, thread_id, active=True)
        return context

    def threads(self, token, mode=None):
        return [r for r in self.history(token, mode) if r["status"] == "active"]

    def history(self, token, mode=None):
        """Only populated conversations belong in history; playgrounds have their own home."""
        rows = list_threads(self.project, self.state, token)
        db = connect(self.state / "app.sqlite", readonly=True)
        try:
            populated = {
                r[0]
                for r in db.execute(
                    "SELECT thread_id FROM ui_requests UNION SELECT thread_id FROM runs"
                )
            }
            workspaces = {r[0] for r in db.execute("SELECT thread_id FROM ui_workspaces")}
        finally:
            db.close()
        events_db = connect(self.state / "events.sqlite", readonly=True)
        try:
            populated.update(
                r[0] for r in events_db.execute("SELECT DISTINCT thread_id FROM events")
            )
        finally:
            events_db.close()
        return [
            r
            for r in rows
            if r["id"] not in workspaces
            and r["id"] in populated
            and (mode is None or r["mode"] == mode)
        ]

    def chat_mode(self, token, thread_id):
        authenticate(self.project, self.state, token)
        if thread_id in {"draft:free", "draft:company"}:
            return thread_id.split(":")[1]
        return owned_thread(self.project, self.state, token, thread_id)[1]["mode"]

    def playground(self, token):
        actor = authenticate(self.project, self.state, token)
        with self.lock:
            db = connect(self.state / "app.sqlite")
            try:
                row = db.execute(
                    "SELECT thread_id FROM ui_workspaces WHERE owner_id=?", (actor["id"],)
                ).fetchone()
                if row:
                    return row[0]
                identifier = new_thread(
                    self.project, self.state, token, "Tools playground", mode="company"
                )
                db.execute("INSERT INTO ui_workspaces VALUES(?,?)", (actor["id"], identifier))
                db.commit()
                return identifier
            finally:
                db.close()

    def submit_chat(self, token, thread_id, text, submission_id):
        """Materialize a draft only on a valid first submission, including double-click replay."""
        if not text or not 1 <= len(text.strip()) <= 8000:
            raise ValueError("Message must contain 1–8000 characters")
        if not 1 <= len(submission_id) <= 120:
            raise ValueError("Invalid submission ID")
        with self.lock:
            created = False
            if thread_id in {"draft:free", "draft:company"}:
                actor = authenticate(self.project, self.state, token)
                db = connect(self.state / "app.sqlite", readonly=True)
                try:
                    existing = db.execute(
                        "SELECT thread_id FROM ui_requests WHERE owner_id=? AND submission_id=?",
                        (actor["id"], submission_id),
                    ).fetchone()
                finally:
                    db.close()
                created = not existing
                thread_id = (
                    existing[0]
                    if existing
                    else new_thread(
                        self.project, self.state, token, "New chat", mode=thread_id.split(":")[1]
                    )
                )
            try:
                self.enqueue(token, thread_id, text, submission_id)
            except Exception:
                if created:
                    db = connect(self.state / "app.sqlite")
                    try:
                        # Roll back only this newly allocated draft if no request was accepted.
                        if not db.execute(
                            "SELECT 1 FROM ui_requests WHERE thread_id=?", (thread_id,)
                        ).fetchone():
                            db.execute(
                                "DELETE FROM conversation_preferences WHERE thread_id=?",
                                (thread_id,),
                            )
                            db.execute("DELETE FROM conversations WHERE id=?", (thread_id,))
                            db.commit()
                    finally:
                        db.close()
                raise
            self.select(token, thread_id)
            return thread_id

    def company_context(self, token, thread_id):
        if not thread_id:
            thread_id = self.playground(token)
        context = self.context(token, thread_id)
        _, row = owned_thread(self.project, self.state, token, thread_id, active=True)
        if row["mode"] != "company":
            raise ValueError("Choose a Company chat or create a tools workspace first")
        return context

    def has_activity(self, thread_id):
        db = connect(self.state / "events.sqlite", readonly=True)
        try:
            return (
                db.execute(
                    "SELECT 1 FROM events WHERE thread_id=? LIMIT 1", (thread_id,)
                ).fetchone()
                is not None
            )
        finally:
            db.close()

    def switch_mode(self, token, thread_id, mode):
        """Navigate between mode-specific conversations; never rewrite accepted history."""
        if thread_id in {"draft:free", "draft:company"}:
            authenticate(self.project, self.state, token)
            if mode not in {"free", "company"}:
                raise ValueError("Choose Free chat or Company assistant")
            choices = self.threads(token, mode)
            return self.select(token, choices[0]["id"] if choices else "draft:" + mode)
        _, current = owned_thread(self.project, self.state, token, thread_id, active=True)
        if mode not in {"free", "company"}:
            raise ValueError("Choose Free chat or Company assistant")
        if current["mode"] == mode:
            return thread_id
        db = connect(self.state / "app.sqlite", readonly=True)
        try:
            used = db.execute(
                "SELECT 1 FROM ui_requests WHERE thread_id=?", (thread_id,)
            ).fetchone()
            used = (
                used or db.execute("SELECT 1 FROM runs WHERE thread_id=?", (thread_id,)).fetchone()
            )
        finally:
            db.close()
        if not used and not self.has_activity(thread_id):
            self.set_mode(token, thread_id, mode)
            return self.select(token, thread_id)
        choices = self.threads(token, mode)
        selected = choices[0]["id"] if choices else "draft:" + mode
        return self.select(token, selected)

    def select(self, token, thread_id=None):
        actor = authenticate(self.project, self.state, token)
        db = connect(self.state / "app.sqlite")
        try:
            if thread_id is None:
                row = db.execute(
                    "SELECT thread_id FROM ui_selection WHERE owner_id=?", (actor["id"],)
                ).fetchone()
                choices = self.threads(token)
                permitted = {r["id"] for r in choices}
                thread_id = (
                    row[0]
                    if row and row[0] in permitted
                    else (choices[0]["id"] if choices else "draft:free")
                )
            if thread_id in {"draft:free", "draft:company"}:
                return thread_id
            self.context(token, thread_id)
            db.execute(
                "INSERT INTO ui_selection VALUES(?,?) ON CONFLICT(owner_id) "
                "DO UPDATE SET thread_id=excluded.thread_id",
                (actor["id"], thread_id),
            )
            db.commit()
        finally:
            db.close()
        return thread_id

    def edit_thread(self, token, thread_id, title=None, archive=False):
        self.context(token, thread_id)
        if title is not None and not 1 <= len(title.strip()) <= 120:
            raise ValueError("Title must contain 1–120 characters")
        db = connect(self.state / "app.sqlite")
        try:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM ui_requests WHERE thread_id=? AND status IN ('queued','running')",
                (thread_id,),
            ).fetchone():
                raise ValueError("Wait for the active conversation job before changing this thread")
            if any(
                r["status"] in {"queued", "running", "cancel_requested", "publishing"}
                for r in list_jobs(self.context(token, thread_id))
            ):
                raise ValueError(
                    "Wait for or cancel the active analysis before changing this thread"
                )
            db.execute(
                "UPDATE conversations SET title=COALESCE(?,title),status=?,updated_at=? WHERE id=?",
                (
                    title.strip() if title else None,
                    "archived" if archive else "active",
                    now(),
                    thread_id,
                ),
            )
            db.commit()
        finally:
            db.close()
        return self.select(token) if archive else thread_id

    def set_mode(self, token, thread_id, mode):
        self.context(token, thread_id)
        if mode not in {"free", "company"}:
            raise ValueError("Choose free chat or company assistant")
        db = connect(self.state / "app.sqlite")
        try:
            db.execute("BEGIN IMMEDIATE")
            if (
                self.has_activity(thread_id)
                or db.execute("SELECT 1 FROM runs WHERE thread_id=?", (thread_id,)).fetchone()
                or db.execute(
                    "SELECT 1 FROM ui_requests WHERE thread_id=?", (thread_id,)
                ).fetchone()
            ):
                raise ValueError(
                    "Start a new chat to choose a different mode. Your history stays here."
                )
            db.execute(
                "INSERT INTO conversation_preferences VALUES(?,?) "
                "ON CONFLICT(thread_id) DO UPDATE SET mode=excluded.mode",
                (thread_id, mode),
            )
            db.commit()
        finally:
            db.close()

    def restore_thread(self, token, thread_id):
        owned_thread(self.project, self.state, token, thread_id)
        db = connect(self.state / "app.sqlite")
        try:
            db.execute(
                "UPDATE conversations SET status='active',updated_at=? WHERE id=?",
                (now(), thread_id),
            )
            db.commit()
        finally:
            db.close()
        return self.select(token, thread_id)

    def enqueue(self, token, thread_id, text, submission_id, resume=False):
        if self.stopping.is_set():
            raise ValueError("Server is stopping. Reload after restarting it.")
        actor, _ = owned_thread(self.project, self.state, token, thread_id, active=True)
        if not 1 <= len(submission_id) <= 120:
            raise ValueError("Invalid submission ID")
        if not resume and (not text or not 1 <= len(text.strip()) <= 8000):
            raise ValueError("Message must contain 1–8000 characters")
        db = connect(self.state / "app.sqlite")
        try:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM ui_requests WHERE thread_id=? AND submission_id=? AND resume=?",
                (thread_id, submission_id, int(resume)),
            ).fetchone()
            if existing and existing["status"] not in {"failed", "interrupted"}:
                if existing["user_text"] != text:
                    raise ValueError("Submission ID belongs to a different message")
                return existing["id"]
            if db.execute(
                "SELECT 1 FROM ui_requests WHERE thread_id=? AND status IN ('queued','running')",
                (thread_id,),
            ).fetchone():
                raise ValueError("This conversation already has a queued or running message")
            if (
                db.execute(
                    "SELECT COUNT(*) FROM ui_requests WHERE status IN ('queued','running')"
                ).fetchone()[0]
                >= 20
            ):
                raise ValueError("The local queue is full; wait for a running message to finish")
            identifier = existing["id"] if existing else "request-" + uuid4().hex
            if existing:
                db.execute(
                    "UPDATE ui_requests SET status='queued',error=NULL,updated_at=? WHERE id=?",
                    (now(), identifier),
                )
            else:
                # A readable title appears after the first message, without another model call.
                db.execute(
                    "UPDATE conversations SET title=?,updated_at=? WHERE id=? AND title='New chat'",
                    (" ".join(text.split())[:70] if text else "New chat", now(), thread_id),
                )
                db.execute(
                    "INSERT INTO ui_requests VALUES(?,?,?,?,?,?,'queued',NULL,?,?)",
                    (
                        identifier,
                        actor["id"],
                        thread_id,
                        submission_id,
                        text,
                        int(resume),
                        now(),
                        now(),
                    ),
                )
            db.commit()
            # Token travels in memory and a private stdin pipe, never command arguments or disk.
            self.queue.put_nowait((identifier, token))
            return identifier
        finally:
            db.close()

    def resume(self, token, thread_id):
        self.context(token, thread_id)
        db = connect(self.state / "app.sqlite", readonly=True)
        try:
            row = db.execute(
                "SELECT submission_id FROM runs WHERE thread_id=? "
                "AND status!='complete' ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
            queued = db.execute(
                "SELECT * FROM ui_requests WHERE thread_id=? "
                "AND status IN ('failed','interrupted') ORDER BY created_at DESC "
                "LIMIT 1",
                (thread_id,),
            ).fetchone()
        finally:
            db.close()
        if row:
            return self.enqueue(token, thread_id, None, row[0], resume=True)
        if queued:
            return self.enqueue(token, thread_id, queued["user_text"], queued["submission_id"])
        raise ValueError("No unfinished message in this conversation")

    def consume(self):
        while item := self.queue.get():
            if self.stopping.is_set():
                break
            identifier, token = item
            db = connect(self.state / "app.sqlite")
            try:
                row = dict(
                    db.execute("SELECT * FROM ui_requests WHERE id=?", (identifier,)).fetchone()
                )
                db.execute(
                    "UPDATE ui_requests SET status='running',updated_at=? WHERE id=?",
                    (now(), identifier),
                )
                db.commit()
            finally:
                db.close()
            status, error = "failed", None
            try:
                payload = {
                    "project": str(self.project),
                    "state": str(self.state),
                    "data": str(self.data),
                    "token": token,
                    "request": row,
                }
                with self.lock:
                    if self.stopping.is_set():
                        raise RuntimeError("Server is stopping")
                    self.process = subprocess.Popen(
                        [sys.executable, "-I", "-B", "-m", "acme.ui_worker"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                self.process.communicate(json.dumps(payload).encode(), timeout=300)
                status = "complete" if self.process.returncode == 0 else "failed"
                if status == "failed":
                    error = "Agent failed. Inspect the timeline, fix configuration, then Resume."
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
                error = "Agent exceeded 300 seconds and its process was stopped. Resume to retry."
            except Exception:
                error = (
                    "Unable to start the agent worker. Run acme doctor and inspect the timeline."
                )
            finally:
                with self.lock:
                    self.process = None
                db = connect(self.state / "app.sqlite")
                try:
                    db.execute(
                        "UPDATE ui_requests SET status=?,error=?,updated_at=? WHERE id=?",
                        (status, error, now(), identifier),
                    )
                    db.commit()
                finally:
                    db.close()

    def snapshot(self, token, thread_id):
        if thread_id in {"draft:free", "draft:company"}:
            authenticate(self.project, self.state, token)
            return {
                "chat": [],
                "chat_runs": [],
                "status": "ready",
                "error": None,
                **{
                    key: []
                    for key in [
                        "events",
                        "operations",
                        "runs",
                        "files",
                        "jobs",
                        "sources",
                        "reports",
                    ]
                },
                "history_note": "",
            }
        context = self.context(token, thread_id)
        messages, after = [], 0
        while True:
            page = read_transcript(self.project, self.state, token, thread_id, after)
            messages.extend(page)
            if len(page) < 100:
                break
            after = page[-1]["seq"]
        display, chat_runs = [], []
        # A tool-calling model can narrate every attempt. Preserve that full
        # transcript for inspection, but show one final answer per accepted run.
        final_answers = {}
        for row in messages:
            message = row["message"]
            if (
                message["type"] == "ai"
                and message["data"]["content"]
                and not message["data"].get("tool_calls")
            ):
                final_answers[row["run_id"]] = row["message_id"]
        for row in messages[-200:]:
            message = row["message"]
            if message["type"] == "ai" and final_answers.get(row["run_id"]) != row["message_id"]:
                continue
            if message["type"] in {"human", "ai"} and message["data"]["content"]:
                content = message["data"]["content"]
                if not isinstance(content, str):
                    content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
                display.append(
                    {
                        "role": "user" if message["type"] == "human" else "assistant",
                        "content": content,
                    }
                )
                chat_runs.append(row["run_id"])
        db = connect(self.state / "app.sqlite", readonly=True)
        try:
            request = db.execute(
                "SELECT * FROM ui_requests WHERE thread_id=? ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
            operations = [
                dict(r)
                for r in db.execute(
                    "SELECT id,kind,payload_json FROM operations "
                    "WHERE thread_id=? AND status='pending' "
                    "ORDER BY created_at",
                    (thread_id,),
                )
            ]
            runs = [
                dict(r)
                for r in db.execute(
                    "SELECT id,status,submission_id,error FROM runs "
                    "WHERE thread_id=? ORDER BY created_at DESC LIMIT 5",
                    (thread_id,),
                )
            ]
            reports = [
                dict(r)
                for r in db.execute(
                    "SELECT id,title FROM reports WHERE thread_id=? "
                    "ORDER BY created_at DESC LIMIT 20",
                    (thread_id,),
                )
            ]
        finally:
            db.close()
        status = request["status"] if request else "ready"
        # The queue is durable before the worker has written a transcript. Show the
        # accepted prompt now, and stop adding it once that submission has a human row.
        if request and request["user_text"] and not request["resume"]:
            accepted = next(
                (r for r in runs if r["submission_id"] == request["submission_id"]), None
            )
            saved = accepted and any(
                r["run_id"] == accepted["id"] and r["message"]["type"] == "human" for r in messages
            )
            if not saved:
                display.append({"role": "user", "content": request["user_text"]})
                chat_runs.append(accepted["id"] if accepted else None)
        events_db = connect(self.state / "events.sqlite", readonly=True)
        try:
            recent = events_db.execute(
                "SELECT seq FROM events WHERE thread_id=? ORDER BY seq DESC LIMIT 30", (thread_id,)
            ).fetchall()
            source_events = events_db.execute(
                "SELECT payload_json FROM events WHERE thread_id=? AND kind='tool_result' "
                "ORDER BY seq DESC LIMIT 20",
                (thread_id,),
            ).fetchall()
        finally:
            events_db.close()
        events = search(
            self.project,
            self.state,
            token,
            thread_id,
            after=max(0, recent[-1][0] - 1) if recent else 0,
            limit=30,
        )["events"]
        if status == "running":
            previews = [e for e in events if e["kind"] == "model_stream"]
            latest = previews[-1] if previews else None
            # Once a tool starts, its preceding narration is no longer a live answer.
            tool_after = latest and any(
                e["seq"] > latest["seq"]
                and e["kind"]
                in {"tool_attempt_started", "tool_attempt", "native_tool_started", "tool_result"}
                for e in events
            )
            if (
                latest
                and not tool_after
                and not latest["payload"].get("tool_call")
                and latest["payload"]["message_id"] not in {m["message_id"] for m in messages}
            ):
                display.append({"role": "assistant", "content": latest["payload"]["content"]})
                chat_runs.append(latest["run_id"])
        return {
            "chat": display,
            "chat_runs": chat_runs,
            "status": status,
            "error": request["error"] if request else None,
            "events": events,
            "operations": operations,
            "runs": runs,
            "files": list_files(context),
            "jobs": list_jobs(context),
            "sources": [
                source
                for row in source_events
                for source in json.loads(row[0]).get("result", {}).get("sources", [])
            ],
            "reports": reports,
            "history_note": "Showing latest 200 stored messages" if len(messages) > 200 else "",
        }

    def inspect(self, token, thread_id, kind="", text="", after=0):
        return search(
            self.project,
            self.state,
            token,
            thread_id,
            kind=kind or None,
            text=text,
            after=int(after),
            limit=50,
        )

    def diff(self, token, thread_id, before, after):
        return compare(list(all_events(self.project, self.state, token, thread_id)), before, after)

    def operation(self, token, thread_id, identifier):
        return inspect_operation(self.context(token, thread_id), identifier)

    def decision(self, token, thread_id, identifier, decision, arguments=None):
        return decide(self.context(token, thread_id), identifier, decision, arguments)

    def explore(self, token, thread_id, entity, identifier="", text=""):
        context = self.context(token, thread_id)
        if entity == "documents":
            return execute(context, "search_documents", {"query": text or "policy"})
        if identifier:
            return execute(context, "lookup_record", {"entity": entity, "record_id": identifier})
        return execute(
            context, "list_records", {"entity": entity, "query": text or None, "limit": 10}
        )

    def logout(self, token):
        db = connect(self.state / "app.sqlite")
        try:
            db.execute(
                "DELETE FROM sessions WHERE token_hash=?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            )
            db.commit()
        finally:
            db.close()
