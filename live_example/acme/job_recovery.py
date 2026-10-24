"""Recover only workers whose owning controller has demonstrably stopped, never by age alone."""

import os
import time

import psutil

from acme.dataset import connect
from acme.docker_jobs import remove_container
from acme.jobs import SAFE_ID, initialize_jobs, update_job

ACTIVE = ("queued", "running", "cancel_requested", "publishing", "recovery_required")


def matching_process(pid, created):
    """Return the exact live process or None; unknown identity is an explicit error."""
    if pid is None:
        return None
    if created is None:
        raise ValueError("Legacy worker has no creation-time identity; cleanup needs manual review")
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - created) > 0.001:
            return None  # PID was reused; never signal its new owner.
        return process if process.is_running() else None
    except psutil.NoSuchProcess:
        return None


def active_jobs(state):
    initialize_jobs(state)
    db = connect(state / "jobs.sqlite", readonly=True)
    try:
        return [
            dict(r)
            for r in db.execute(
                "SELECT j.*,f.name FROM jobs j JOIN files f ON f.id=j.input_id "
                "WHERE j.status IN (?,?,?,?,?)",
                ACTIVE,
            )
        ]
    finally:
        db.close()


def recover_jobs(state):
    results = []
    for row in active_jobs(state):
        try:
            if row["controller_pid"] is None:
                raise ValueError(
                    "Legacy job has no controller identity; cleanup needs manual review"
                )
            if matching_process(row["controller_pid"], row["controller_started"]):
                continue
            worker = matching_process(row["pid"], row["worker_started"])
            if worker:
                worker.kill()  # psutil also guards against PID reuse before signaling.
                worker.wait(timeout=5)
            if row["name"] == "code.py":
                if not SAFE_ID.fullmatch(row["id"]):
                    raise ValueError("Invalid owned container identifier")
                remove_container("acme-" + row["id"])
            update_job(
                state,
                row["id"],
                "interrupted",
                error="Controller stopped; cleanup verified. Start a new analysis.",
            )
            results.append({"job_id": row["id"], "status": "interrupted", "cleanup_verified": True})
        except (ValueError, RuntimeError, OSError, psutil.Error) as exc:
            update_job(state, row["id"], "recovery_required", error=str(exc)[:500])
            results.append(
                {
                    "job_id": row["id"],
                    "status": "recovery_required",
                    "cleanup_verified": False,
                    "error": str(exc)[:500],
                }
            )
    return results


def shutdown_jobs(state, timeout=45):
    """Cancel this server's jobs and recover children of agent processes already stopped."""
    owner = psutil.Process()
    db = connect(state / "jobs.sqlite")
    try:
        db.execute(
            "UPDATE jobs SET status='cancel_requested' WHERE controller_pid=? "
            "AND controller_started=? AND status IN ('queued','running')",
            (os.getpid(), owner.create_time()),
        )
        db.commit()
    finally:
        db.close()
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        own = [
            r
            for r in active_jobs(state)
            if r["controller_pid"] == owner.pid
            and r["controller_started"] == owner.create_time()
            and r["status"] != "recovery_required"
        ]
        if not own:
            break
        time.sleep(0.05)
    results = recover_jobs(state)
    # A stuck supervisor is not evidence of successful cancellation. Preserve the
    # capacity reservation and make unresolved cleanup visible after the deadline.
    db = connect(state / "jobs.sqlite")
    try:
        rows = db.execute(
            "UPDATE jobs SET status='recovery_required',error=? "
            "WHERE controller_pid=? AND controller_started=? "
            "AND status IN ('queued','running','cancel_requested','publishing') RETURNING id",
            (
                "Shutdown deadline exceeded; cleanup is unverified. Restart for recovery.",
                owner.pid,
                owner.create_time(),
            ),
        ).fetchall()
        db.commit()
        results.extend(
            {"job_id": row[0], "status": "recovery_required", "cleanup_verified": False}
            for row in rows
        )
    finally:
        db.close()
    return results
