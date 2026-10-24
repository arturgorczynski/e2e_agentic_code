"""Bounded local workers and an isolated Docker alternative."""
import os
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from langchain.tools import tool
from langchain.agents.middleware import DockerExecutionPolicy

from .config import ARTIFACTS_DIR, DATA_DIR, settings

WORKERS = {"hello", "wait_forever", "spin_forever"}


def clean_environment():
    """Pass operating-system essentials, not the notebook's API credentials."""
    names = ("SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC")
    env = {name: os.environ[name] for name in names if name in os.environ}
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.defpath
    return env


def workspace():
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="workspace-", dir=ARTIFACTS_DIR))
    shutil.copy2(DATA_DIR / "handbook.txt", path / "handbook.txt")
    return path


def local_shell():
    if os.name == "nt":
        bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if not bash.exists():
            raise RuntimeError("Local ShellToolMiddleware needs Git Bash on Windows.")
        return [str(bash), "--noprofile", "--norc"]
    return ["/bin/bash", "--noprofile", "--norc"]


def docker_ready():
    if not shutil.which("docker"):
        print("DOCKER NOT READY: install Docker Desktop.")
        return False
    result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        print("DOCKER NOT READY: start Docker Desktop with Linux containers.")
        return False
    image = settings()["sandbox"]["image"]
    result = subprocess.run(["docker", "image", "inspect", image],
                            capture_output=True, timeout=15)
    if result.returncode:
        print(f"DOCKER IMAGE MISSING: run docker pull {image}")
        return False
    return True


def run_worker(worker="hello", mode="local"):
    """Only run our three trusted fixture files, never arbitrary host code."""
    if worker not in WORKERS:
        raise ValueError(f"Choose a worker from {sorted(WORKERS)}")
    limits = settings()["sandbox"]
    container_name = None
    if mode == "local":
        command = [sys.executable, "-u", str(DATA_DIR / "workers" / f"{worker}.py")]
        env = clean_environment()
    elif mode == "docker":
        if not docker_ready():
            raise RuntimeError("Docker prerequisites are not ready.")
        container_name = f"middleware-lab-{uuid4().hex[:12]}"
        command = [
            "docker", "run", "--rm", "--name", container_name,
            "--label", "agentic-ai.middleware-lab=true",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "32",
            "--memory", f"{limits['memory_mb']}m", "--cpus", limits["cpus"],
            "--user", "65534:65534",
            "--mount", f"type=bind,source={DATA_DIR / 'workers'},target=/workspace,readonly",
            "--workdir", "/workspace", limits["image"],
            "python", "-u", f"/workspace/{worker}.py",
        ]
        env = None  # Docker CLI uses host configuration; no env is passed to container.
    else:
        raise ValueError("mode must be local or docker")
    print(f"{mode.upper()} worker={worker}; timeout={limits['command_timeout']}s")
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=limits["command_timeout"], env=env,
                                cwd=DATA_DIR / "workers")
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return {"status": "completed", "stdout": result.stdout}
    except subprocess.TimeoutExpired:
        return {"status": "timed_out", "worker": worker}
    finally:
        if container_name:
            cleanup_container(container_name)


def cleanup_container(name):
    """Remove only the exact container name generated for this invocation."""
    removed = subprocess.run(["docker", "rm", "-f", name],
                             capture_output=True, text=True, timeout=15)
    expected = ("No such container", "removal of container")
    if removed.returncode and not any(message in removed.stderr for message in expected):
        raise RuntimeError(f"Container cleanup failed for {name}: {removed.stderr}")
    # --rm may already be removing it; verify disappearance instead of racing it.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        remaining = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"name=^/{name}$"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        if not remaining.stdout.strip():
            print("Docker session cleaned:", name)
            return
        time.sleep(0.1)
    raise RuntimeError(f"Container cleanup did not finish: {name}")


@contextmanager
def managed_docker_policy():
    """The finally block also cleans up after a shell timeout or an exception."""
    limits = settings()["sandbox"]
    name = f"middleware-shell-{uuid4().hex[:12]}"
    policy = DockerExecutionPolicy(
        image=limits["image"], command_timeout=limits["command_timeout"],
        network_enabled=False, memory_bytes=limits["memory_mb"] * 1024 * 1024,
        cpus=limits["cpus"], read_only_rootfs=True, user="65534:65534",
        extra_run_args=[
            "--name", name, "--label=agentic-ai.middleware-lab=true",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=32",
        ],
    )
    try:
        yield policy
    finally:
        cleanup_container(name)


@tool
def bounded_job(worker: str = "wait_forever") -> dict:
    """Run a known demo worker locally; stop it after the configured timeout."""
    return run_worker(worker, mode="local")
