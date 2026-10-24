"""Owned file catalog and supervised, bounded analysis workers. Workspaces are not sandboxes."""

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from uuid import uuid4

import psutil

from acme.analysis import MAX_INPUT, MAX_OUTPUT
from acme.app_store import AccessDenied, authorize, event, now
from acme.company_queries import query
from acme.dataset import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, thread_id TEXT NOT NULL, name TEXT NOT NULL,
 relative_path TEXT NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
 permission TEXT, created_at TEXT NOT NULL, source_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, thread_id TEXT NOT NULL, status TEXT NOT NULL,
 input_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 pid INTEGER, error TEXT, result_json TEXT, deadline_seconds REAL NOT NULL);
"""
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
PROCESSES = {}
PROCESS_LOCK = threading.RLock()
FILENAMES = {"input.csv", "result.json", "report.md", "python.txt", "code.py"}


def initialize_jobs(state):
    db = connect(state / "jobs.sqlite")
    try:
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
        for name, kind in (
            ("controller_pid", "INTEGER"),
            ("controller_started", "REAL"),
            ("worker_started", "REAL"),
        ):
            if name not in columns:
                db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {kind}")
        db.commit()
    finally:
        db.close()


def workspace(context, *parts):
    actor = authorize(context)
    segments = (actor["id"], context.thread_id, *parts)
    if any(not SAFE_ID.fullmatch(part) for part in segments):
        raise ValueError("Invalid workspace identifier")
    root = context.state / "workspaces"
    path = root
    for part in segments:
        if path.is_symlink() or path.is_junction():
            raise ValueError("Workspace links are not allowed")
        path = path / part
    if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Workspace path escapes its owner")
    path.mkdir(parents=True, exist_ok=True)
    return path


def register_file(context, name, content, *, permission=None, source=None):
    actor = authorize(context, permission)
    initialize_jobs(context.state)
    if name not in FILENAMES:
        raise ValueError("Unsupported controlled filename")
    limit = MAX_INPUT if name == "input.csv" else 65536 if name == "code.py" else MAX_OUTPUT
    if len(content) > limit:
        raise ValueError("File exceeds its size limit")
    identifier = "file-" + uuid4().hex
    folder = workspace(context, identifier)
    db = connect(context.state / "jobs.sqlite")
    try:
        db.execute("BEGIN IMMEDIATE")
        used = workspace_usage(db, actor["id"])
        if used + len(content) > 50 * MAX_OUTPUT:
            raise ValueError("Account workspace quota is 50 MiB")
        path = folder / name
        path.write_bytes(content)
        db.execute(
            "INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                actor["id"],
                context.thread_id,
                name,
                str(path.relative_to(context.state)),
                len(content),
                hashlib.sha256(content).hexdigest(),
                permission,
                now(),
                json.dumps(source or {}),
            ),
        )
        db.commit()
    finally:
        db.close()
    event(context, "artifact_created", {"file_id": identifier, "name": name, "bytes": len(content)})
    return identifier


def file_record(context, identifier):
    actor = authorize(context)
    initialize_jobs(context.state)
    db = connect(context.state / "jobs.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT * FROM files WHERE id=? AND owner_id=? AND thread_id=?",
            (identifier, actor["id"], context.thread_id),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("File unavailable to this account and conversation")
    authorize(context, row["permission"])
    source = json.loads(row["source_json"])
    if source.get("job_id") and job_record(context, source["job_id"])["status"] != "complete":
        raise AccessDenied("Job artifacts are available only after successful completion")
    return dict(row)


def read_file(context, identifier):
    row = file_record(context, identifier)
    folder = workspace(context, identifier)
    path = folder / row["name"]
    if row["name"] not in FILENAMES or path.is_symlink():
        raise ValueError("Invalid artifact path")
    if path.stat().st_size != row["bytes"] or row["bytes"] > MAX_INPUT:
        raise ValueError("Artifact size changed")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        raise ValueError("Artifact content changed")
    return row, content


def list_files(context):
    actor = authorize(context)
    initialize_jobs(context.state)
    db = connect(context.state / "jobs.sqlite", readonly=True)
    try:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,name,bytes,created_at FROM files WHERE owner_id=? AND thread_id=? "
                "AND (json_extract(source_json,'$.job_id') IS NULL OR "
                "json_extract(source_json,'$.job_id') IN "
                "(SELECT id FROM jobs WHERE status='complete')) "
                "AND (permission IS NULL OR permission IN ("
                + ",".join("?" for _ in actor["permissions"])
                + ")) ORDER BY created_at DESC LIMIT 100",
                (actor["id"], context.thread_id, *actor["permissions"]),
            )
        ]
    finally:
        db.close()


def prepare_sales_csv(context):
    rows, source = query(
        context,
        "analysis:sales_by_month",
        "SELECT substr(i.posted_on,1,7) AS month,COUNT(*) AS invoice_count,"
        "SUM(i.total_pence-COALESCE((SELECT SUM(c.amount_pence) FROM credit_notes c "
        "WHERE c.invoice_id=i.id),0)) AS sales_pence FROM invoices i GROUP BY month ORDER BY month",
        (),
        "analytics.read",
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["month", "invoice_count", "sales_pence"])
    writer.writeheader()
    writer.writerows(rows)
    return register_file(
        context,
        "input.csv",
        buffer.getvalue().encode(),
        permission="analytics.read",
        source={"query_event_id": source, "business_date": "2011-12-09"},
    )


def job_record(context, identifier):
    actor = authorize(context)
    initialize_jobs(context.state)
    db = connect(context.state / "jobs.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT j.*,f.permission FROM jobs j JOIN files f ON f.id=j.input_id "
            "WHERE j.id=? AND j.owner_id=? AND j.thread_id=?",
            (identifier, actor["id"], context.thread_id),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("Job unavailable to this account and conversation")
    authorize(context, row["permission"])
    return dict(row)


def update_job(state, identifier, status, *, error=None, result=None, pid=None):
    db = connect(state / "jobs.sqlite")
    try:
        db.execute(
            "UPDATE jobs SET status=?,updated_at=?,error=?,result_json=?,pid=COALESCE(?,pid) "
            "WHERE id=?",
            (status, now(), error, json.dumps(result) if result else None, pid, identifier),
        )
        db.commit()
    finally:
        db.close()


def cancel_job(context, identifier):
    job_record(context, identifier)
    db = connect(context.state / "jobs.sqlite")
    try:
        accepted = db.execute(
            "UPDATE jobs SET status='cancel_requested',updated_at=? "
            "WHERE id=? AND status IN ('queued','running')",
            (now(), identifier),
        ).rowcount
        db.commit()
    finally:
        db.close()
    event(context, "analysis_cancel_requested", {"job_id": identifier, "accepted": bool(accepted)})
    return job_record(context, identifier)


def claim_status(state, identifier, before, after, pid=None):
    db = connect(state / "jobs.sqlite")
    try:
        try:
            worker_started = psutil.Process(pid).create_time() if pid else None
        except psutil.NoSuchProcess:
            worker_started = None
        changed = db.execute(
            "UPDATE jobs SET status=?,updated_at=?,pid=COALESCE(?,pid),"
            "worker_started=COALESCE(?,worker_started) WHERE id=? AND status=?",
            (after, now(), pid, worker_started, identifier, before),
        ).rowcount
        db.commit()
        return bool(changed)
    finally:
        db.close()


def list_jobs(context):
    actor = authorize(context)
    initialize_jobs(context.state)
    db = connect(context.state / "jobs.sqlite", readonly=True)
    try:
        return [
            dict(row)
            for row in db.execute(
                "SELECT j.* FROM jobs j JOIN files f ON f.id=j.input_id "
                "WHERE j.owner_id=? AND j.thread_id=? AND "
                "(f.permission IS NULL OR f.permission IN ("
                + ",".join("?" for _ in actor["permissions"])
                + ")) ORDER BY j.created_at DESC LIMIT 50",
                (actor["id"], context.thread_id, *actor["permissions"]),
            )
        ]
    finally:
        db.close()


def workspace_usage(db, owner_id):
    files = db.execute(
        "SELECT COALESCE(SUM(bytes),0) FROM files WHERE owner_id=?", (owner_id,)
    ).fetchone()[0]
    scratch = db.execute(
        "SELECT COALESCE(SUM(f.bytes+?),0) FROM jobs j JOIN files f "
        "ON f.id=j.input_id WHERE j.owner_id=?",
        (MAX_OUTPUT, owner_id),
    ).fetchone()[0]
    return files + scratch


def reserve_job(context, input_id, deadline, reserved_bytes=0):
    """Atomically bound queued/running work and reserve its disk budget before spawning."""
    actor = authorize(context)
    if not 0.01 <= deadline <= 30:
        raise ValueError("Deadline must be between 0.01 and 30 seconds")
    initialize_jobs(context.state)
    identifier = "job-" + uuid4().hex
    db = connect(context.state / "jobs.sqlite")
    try:
        db.execute("BEGIN IMMEDIATE")
        active = db.execute(
            "SELECT owner_id FROM jobs WHERE status IN "
            "('queued','running','cancel_requested','publishing','recovery_required')"
        ).fetchall()
        if len(active) >= 4 or sum(r[0] == actor["id"] for r in active) >= 2:
            raise ValueError("Analysis capacity reached: two jobs per account, four in total")
        if workspace_usage(db, actor["id"]) + reserved_bytes + MAX_OUTPUT > 50 * MAX_OUTPUT:
            raise ValueError("Account workspace quota is 50 MiB including job scratch space")
        db.execute(
            "INSERT INTO jobs(id,owner_id,thread_id,status,input_id,created_at,updated_at,"
            "deadline_seconds,controller_pid,controller_started) "
            "VALUES(?,?,?,'queued',?,?,?,?,?,?)",
            (
                identifier,
                actor["id"],
                context.thread_id,
                input_id,
                now(),
                now(),
                deadline,
                os.getpid(),
                psutil.Process().create_time(),
            ),
        )
        db.commit()
    finally:
        db.close()
    return identifier


def start_csv_job(context, input_id, operation, value_column, group_column=None, deadline=5):
    row, content = read_file(context, input_id)
    if row["name"] != "input.csv":
        raise ValueError("Choose an input CSV file")
    identifier = reserve_job(context, input_id, deadline, len(content))
    try:
        folder = workspace(context, identifier)
        (folder / "input.csv").write_bytes(content)
        (folder / "request.json").write_text(
            json.dumps(
                {
                    "parent_pid": os.getpid(),
                    "deadline_seconds": deadline,
                    "analysis": {
                        "operation": operation,
                        "value_column": value_column,
                        "group_column": group_column,
                    },
                }
            ),
            encoding="utf-8",
        )
        thread = threading.Thread(
            target=supervise_csv, args=(context, identifier, folder, row, deadline), daemon=True
        )
        thread.start()
    except Exception as exc:
        update_job(context.state, identifier, "failed", error=str(exc)[:500])
        raise
    return identifier


def supervise_csv(context, identifier, folder, source, deadline):
    process = None
    started = time.monotonic()
    try:
        environment = {
            key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH") if key in os.environ
        }
        with PROCESS_LOCK:
            if job_record(context, identifier)["status"] == "cancel_requested":
                update_job(context.state, identifier, "cancelled")
                return
            process = subprocess.Popen(
                [sys.executable, "-I", "-B", "-m", "acme.worker", str(folder)],
                cwd=folder,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            PROCESSES[identifier] = process
            if not claim_status(context.state, identifier, "queued", "running", process.pid):
                process.kill()
                process.wait(timeout=5)
                update_job(context.state, identifier, "cancelled")
                return
        event(
            context,
            "analysis_started",
            {
                "job_id": identifier,
                "pid": process.pid,
                "deadline_seconds": deadline,
                "input_id": source["id"],
            },
        )
        while process.poll() is None:
            status = job_record(context, identifier)["status"]
            reason = (
                "cancelled"
                if status == "cancel_requested"
                else "timed_out"
                if time.monotonic() - started >= deadline
                else None
            )
            oversized = any(
                p.stat().st_size > MAX_OUTPUT
                for p in folder.iterdir()
                if p.name not in {"input.csv", "request.json"} and p.is_file()
            )
            if reason or oversized:
                process.kill()
                process.wait(timeout=5)
                status = reason or "failed"
                update_job(
                    context.state, identifier, status, error=reason or "Output exceeds 1 MiB"
                )
                event(
                    context,
                    "analysis_stopped",
                    {"job_id": identifier, "status": status, "worker_exited": True},
                )
                return
            time.sleep(0.02)
        process.wait()
        current = job_record(context, identifier)["status"]
        if (
            current == "cancel_requested"
            or time.monotonic() - started >= deadline
            or process.returncode == 124
        ):
            update_job(
                context.state,
                identifier,
                "cancelled" if current == "cancel_requested" else "timed_out",
            )
            return
        if process.returncode:
            error_path = folder / "error.json"
            error = (
                json.loads(error_path.read_text("utf-8"))["error"]
                if error_path.exists()
                else "Worker failed"
            )
            raise ValueError(error)
        result_bytes = (folder / "result.json").read_bytes()
        report_bytes = (folder / "report.md").read_bytes()
        if len(result_bytes) + len(report_bytes) > MAX_OUTPUT:
            raise ValueError("Worker output exceeds 1 MiB")
        with PROCESS_LOCK:
            if not claim_status(context.state, identifier, "running", "publishing"):
                update_job(context.state, identifier, "cancelled")
                return
            files = [
                register_file(
                    context,
                    name,
                    content,
                    permission=source["permission"],
                    source={"job_id": identifier, "input_id": source["id"]},
                )
                for name, content in [("result.json", result_bytes), ("report.md", report_bytes)]
            ]
            update_job(
                context.state,
                identifier,
                "complete",
                result={"files": files, "analysis": json.loads(result_bytes)},
            )
        event(
            context,
            "analysis_completed",
            {
                "job_id": identifier,
                "files": files,
                "duration_ms": (time.monotonic() - started) * 1000,
            },
        )
    except Exception as exc:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        update_job(context.state, identifier, "failed", error=str(exc)[:500])
        event(context, "analysis_failed", {"job_id": identifier, "error": str(exc)[:500]})
    finally:
        with PROCESS_LOCK:
            PROCESSES.pop(identifier, None)
