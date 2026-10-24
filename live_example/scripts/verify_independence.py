"""Install an allowlisted clean copy outside the source project and verify G01.

Run from the project root: uv run --locked python scripts/verify_independence.py
The temporary copy is retained for inspection; its path is printed at the end.
Dependencies must already be cached by uv sync --locked. No model is invoked.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".env.example",
    "models.toml",
    "README.md",
    ".gitignore",
    "serve.py",
]
DIRECTORIES = ["acme", "tests", "scripts", "docs", "data", "evals"]


def main():
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv and run uv sync --locked before this check.")
    destination = Path(tempfile.mkdtemp(prefix="acme-g01-")).resolve()
    if destination.is_relative_to(ROOT):
        raise RuntimeError("Use a system TEMP directory outside the source project.")
    print(f"Clean verification copy: {destination}", flush=True)
    for name in FILES:
        shutil.copy2(ROOT / name, destination / name)
    for name in DIRECTORIES:
        shutil.copytree(
            ROOT / name,
            destination / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env", ".venv", ".git", "raw"),
        )
    assert not (destination / ".env").exists()
    assert not (destination / ".venv").exists()
    assert not (destination / "data/sources/raw").exists()
    environment = dict(os.environ)
    for key in (
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "PYTHONHOME",
        "UV_PROJECT",
        "UV_PROJECT_ENVIRONMENT",
        "UV_WORKING_DIRECTORY",
    ):
        environment.pop(key, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    lock_before = (destination / "uv.lock").read_bytes()
    commands = [
        ["sync", "--locked", "--offline"],
        ["run", "--locked", "--offline", "acme", "--help"],
        ["run", "--locked", "--offline", "acme", "--version"],
        ["run", "--locked", "--offline", "acme", "data", "verify"],
        ["run", "--locked", "--offline", "acme", "company", "verify"],
        ["run", "--locked", "--offline", "acme", "company", "init"],
        ["run", "--locked", "--offline", "acme", "company", "init"],
        [
            "run",
            "--locked",
            "--offline",
            "python",
            "scripts/verify_trace_export.py",
            "docs/examples/g08_invoice_trace.json",
        ],
        [
            "run",
            "--locked",
            "--offline",
            "python",
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
        ["run", "--locked", "--offline", "ruff", "check", "."],
    ]
    for command in commands:
        print("Running: uv " + " ".join(command), flush=True)
        subprocess.run([uv, *command], cwd=destination, env=environment, check=True, timeout=240)
    python = destination / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    result = subprocess.run(
        [str(python), "-I", "-B", "-c", "import acme; print(acme.__file__)"],
        cwd=destination,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    installed_path = Path(result.stdout.strip()).resolve()
    if not installed_path.is_relative_to(destination):
        raise AssertionError(f"Package imported from outside clean copy: {installed_path}")
    assert lock_before == (destination / "uv.lock").read_bytes(), "Lockfile changed"
    print(f"Verified package path: {installed_path}")
    print(f"G01 clean-copy verification passed. Retained copy: {destination}")


if __name__ == "__main__":
    main()
