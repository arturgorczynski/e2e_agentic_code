"""Optional generated Python execution. Never fall back to executing this code on the host."""

import os
import subprocess
import threading
import time

from acme.analysis import MAX_OUTPUT
from acme.app_store import authorize, event
from acme.jobs import (
    PROCESS_LOCK,
    PROCESSES,
    claim_status,
    job_record,
    read_file,
    register_file,
    reserve_job,
    update_job,
    workspace,
)

IMAGE = "python:3.12-slim"
LOCAL_ENGINE = (
    "npipe:////./pipe/dockerDesktopLinuxEngine"
    if os.name == "nt"
    else "unix:///var/run/docker.sock"
)


def docker_environment():
    # Deliberately ignore DOCKER_HOST/context and all provider credentials.
    return {
        k: os.environ[k]
        for k in ("SYSTEMROOT", "WINDIR", "PATH", "HOME", "USERPROFILE")
        if k in os.environ
    }


def docker_call(arguments, timeout=10):
    return subprocess.run(
        ["docker", "--host", LOCAL_ENGINE, *arguments],
        capture_output=True,
        timeout=timeout,
        env=docker_environment(),
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def availability():
    """Read-only local engine/image checks; never pull images or start an engine implicitly."""
    try:
        engine = docker_call(["info", "--format", "{{.ServerVersion}}"])
        if engine.returncode:
            return False, "Docker engine unavailable; start Docker Desktop for optional execution."
        image = docker_call(["image", "inspect", IMAGE, "--format", "{{.Id}}"])
        if image.returncode:
            return False, f"Optional image missing. Run: docker pull {IMAGE}"
        return True, f"Local Docker engine and {IMAGE} available. Runtime checks are separate."
    except (OSError, subprocess.TimeoutExpired):
        return False, "Docker CLI/engine unavailable. Default CSV analysis works without Docker."


def command(name, code_path, csv_path, deadline):
    """Mount individual approved files read-only. No repository, home or secret mounts."""
    arguments = [
        "docker",
        "--host",
        LOCAL_ENGINE,
        "run",
        "--rm",
        "--pull",
        "never",
        "--name",
        name,
        "--init",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "128m",
        "--memory-swap",
        "128m",
        "--cpus",
        "1",
        "--pids-limit",
        "32",
        "--user",
        "65534:65534",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "--log-driver",
        "none",
        "--mount",
        f"type=bind,source={code_path},target=/input/code.py,readonly",
    ]
    if csv_path is not None:
        arguments.extend(
            [
                "--mount",
                f"type=bind,source={csv_path},target=/input/data.csv,readonly",
            ]
        )
    arguments.extend(
        [
            IMAGE,
            "timeout",
            "--signal=KILL",
            f"{deadline}s",
            "python",
            "-I",
            "-B",
            "/input/code.py",
        ]
    )
    return arguments


def remove_container(name):
    """Remove our exact container and verify absence. Never prune other containers."""
    for _ in range(3):
        docker_call(["rm", "--force", name])
        check = docker_call(
            ["container", "ls", "-a", "--filter", f"name=^{name}$", "--format", "{{.ID}}"]
        )
        if check.returncode == 0 and not check.stdout.strip():
            return
        time.sleep(0.1)
    raise RuntimeError(f"Container cleanup unverified. Run: docker rm --force {name}")


def start_python_job(context, code, input_id=None, deadline=5):
    authorize(context)
    if not isinstance(code, str) or not code.strip() or len(code.encode()) > 65536:
        raise ValueError("Python source must contain 1–65536 UTF-8 bytes")
    if not 0.1 <= deadline <= 30:
        raise ValueError("Docker execution deadline must be 0.1–30 seconds")
    csv_path, permission = None, None
    if input_id:
        row, _ = read_file(context, input_id)
        if row["name"] != "input.csv":
            raise ValueError("Optional input must be a permitted CSV")
        csv_path = workspace(context, input_id) / "input.csv"
        permission = row["permission"]
    ready, explanation = availability()
    if not ready:
        raise ValueError(explanation)
    code_id = register_file(context, "code.py", code.encode(), permission=permission)
    identifier = reserve_job(context, code_id, deadline, len(code.encode()))
    try:
        code_path = workspace(context, code_id) / "code.py"
        thread = threading.Thread(
            target=supervise_python,
            args=(context, identifier, code_path, csv_path, permission, deadline),
            daemon=True,
        )
        thread.start()
    except Exception as exc:
        update_job(context.state, identifier, "failed", error=str(exc)[:500])
        raise
    return identifier


def collect_output(pipe, output, oversized):
    """Keep at most 1 MiB while draining the pipe so termination cannot deadlock."""
    try:
        while block := pipe.read(4096):
            remaining = MAX_OUTPUT - len(output)
            output.extend(block[:remaining])
            if len(block) > remaining:
                oversized.set()
    finally:
        pipe.close()


def supervise_python(context, identifier, code_path, csv_path, permission, deadline):
    name = "acme-" + identifier
    process, reader = None, None
    cleanup_verified = False
    created = False
    started = time.monotonic()
    output, oversized = bytearray(), threading.Event()
    try:
        if job_record(context, identifier)["status"] == "cancel_requested":
            update_job(context.state, identifier, "cancelled")
            return
        # Separate creation from execution: cancellation cannot race a still-arriving
        # 'docker run' creation request and falsely report a container already removed.
        create_args = command(name, code_path, csv_path, deadline)[3:]
        create_args[0] = "create"
        creation = docker_call(create_args, timeout=15)
        if creation.returncode:
            raise RuntimeError("Docker could not create the bounded container")
        created = True
        if job_record(context, identifier)["status"] == "cancel_requested":
            remove_container(name)
            cleanup_verified = True
            update_job(context.state, identifier, "cancelled")
            return
        started = time.monotonic()
        process = subprocess.Popen(
            ["docker", "--host", LOCAL_ENGINE, "start", "--attach", name],
            env=docker_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        with PROCESS_LOCK:
            PROCESSES[identifier] = process
        reader = threading.Thread(target=collect_output, args=(process.stdout, output, oversized))
        reader.start()
        accepted = claim_status(context.state, identifier, "queued", "running", process.pid)
        event(
            context,
            "analysis_started",
            {
                "job_id": identifier,
                "backend": "optional_docker",
                "container": name,
                "deadline_seconds": deadline,
                "input_file": str(csv_path.name) if csv_path else None,
            },
        )
        reason = None if accepted else "cancelled"
        while process.poll() is None and reason is None:
            current = job_record(context, identifier)["status"]
            if current == "cancel_requested":
                reason = "cancelled"
            elif time.monotonic() - started >= deadline + 5:
                # Up to five seconds for container creation; internal timeout bounds code itself.
                reason = "timed_out"
            elif oversized.is_set():
                reason = "output_limit"
            else:
                time.sleep(0.03)
        if reason:
            # CLI termination alone would leave its container running.
            remove_container(name)
            if process.poll() is None:
                process.kill()
        process.wait(timeout=5)
        reader.join(timeout=5)
        if reader.is_alive():
            raise RuntimeError("Docker output reader did not stop")
        # Repeat after the CLI exits to cover a create/remove race.
        remove_container(name)
        cleanup_verified = True
        current = job_record(context, identifier)["status"]
        if current == "cancel_requested":
            reason = "cancelled"
        if oversized.is_set():
            reason = "output_limit"
        if reason or process.returncode:
            terminal = reason if reason in {"cancelled", "timed_out"} else "failed"
            if (
                not reason
                and process.returncode in {124, 137}
                and time.monotonic() - started >= deadline
            ):
                terminal = "timed_out"
            update_job(context.state, identifier, terminal, error=reason or "Python failed")
            event(
                context,
                "analysis_stopped",
                {
                    "job_id": identifier,
                    "status": terminal,
                    "container_removed": True,
                    "output_excerpt": output[:4000].decode("utf-8", errors="replace"),
                },
            )
            return
        if not claim_status(context.state, identifier, "running", "publishing"):
            update_job(context.state, identifier, "cancelled")
            return
        file_id = register_file(
            context,
            "python.txt",
            bytes(output),
            permission=permission,
            source={"job_id": identifier, "backend": "optional_docker"},
        )
        update_job(context.state, identifier, "complete", result={"files": [file_id]})
        event(
            context,
            "analysis_completed",
            {
                "job_id": identifier,
                "files": [file_id],
                "container_removed": True,
            },
        )
    except Exception as exc:
        if process:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        if created or isinstance(exc, subprocess.TimeoutExpired):
            try:
                remove_container(name)
                cleanup_verified = True
            except Exception as cleanup:
                exc = RuntimeError(f"{exc}; {cleanup}")
        update_job(context.state, identifier, "failed", error=str(exc)[:500])
        event(
            context,
            "analysis_failed",
            {
                "job_id": identifier,
                "error": str(exc)[:500],
                "container_removed": cleanup_verified,
            },
        )
    finally:
        if reader:
            reader.join(timeout=5)
        with PROCESS_LOCK:
            PROCESSES.pop(identifier, None)
