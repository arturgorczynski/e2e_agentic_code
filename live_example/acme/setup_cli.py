"""Predictable setup and read-only diagnostics with explicit optional capabilities."""

import json
import os
import socket
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import httpx
from dotenv import dotenv_values

from acme.app_store import initialize_app, local_accounts, provision
from acme.dataset import baseline_manifest, connect, initialize_state, verify_dataset
from acme.docker_jobs import availability
from acme.jobs import initialize_jobs
from acme.middleware import configuration
from acme.model_config import get_model, settings


def add_setup_commands(subparsers):
    for name in ("setup", "doctor", "serve"):
        parser = subparsers.add_parser(
            name,
            help={
                "setup": "Initialize prepared company data, local configuration and a login",
                "doctor": "Check configuration, model availability, data and optional Docker",
                "serve": "Start the local Acme Wholesale website",
            }[name],
        )
        parser.add_argument("--project-dir", type=Path, default=Path("."))
        parser.add_argument("--state-dir", type=Path)
        parser.add_argument("--data-dir", type=Path)
        if name == "setup":
            parser.add_argument("--username", help="Choose your own local username")
            parser.add_argument("--display-name", help="Name shown in the UI")
            parser.add_argument(
                "--access-profile",
                choices=["client", "employee", "super_user", "admin"],
                help="Access profile for a new local workspace",
            )
            parser.add_argument(
                "--model", help="Installed local Ollama model for newly created .env"
            )
            parser.add_argument("--non-interactive", action="store_true")
        else:
            parser.add_argument("--port", type=int, default=7860)
        if name == "doctor":
            parser.add_argument(
                "--inference",
                action="store_true",
                help="Explicitly make a model/tool capability probe",
            )
            parser.add_argument(
                "--full-data", action="store_true", help="Also run full dataset consistency checks"
            )


def setup(
    project,
    state,
    data,
    username="taylor.analyst",
    password=None,
    model=None,
    interactive=True,
    role=None,
    display_name=None,
    access_profile=None,
):
    if not (project / "models.toml").exists():
        raise ValueError(
            "Run from the live_example directory containing models.toml, or set --project-dir"
        )
    env_path = project / ".env"
    created = not env_path.exists()
    if created:
        text = (project / ".env.example").read_text("utf-8")
        if model is None and interactive:
            model = input(
                "Installed tool-capable Ollama model (e.g. qwen3:8b; blank to configure later): "
            ).strip()
        if model:
            if any(c in model for c in "\r\n\"' ") or len(model) > 200:
                raise ValueError("Use an Ollama model tag without spaces or quotes")
            text = text.replace("OLLAMA_MODEL=\n", f"OLLAMA_MODEL={model}\n")
        with env_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    dataset = initialize_state(project, state, data=data)
    initialize_app(state)
    initialize_jobs(state)
    if username is None:
        if interactive:
            accounts = local_accounts(state)
            if accounts:
                print("Existing local users: " + ", ".join(row["username"] for row in accounts))
            username = input("Choose an existing username or create your own: ").strip()
        else:
            username = "taylor.analyst"
    username = username.strip().lower()
    db = connect(state / "app.sqlite", readonly=True)
    try:
        exists = db.execute("SELECT 1 FROM accounts WHERE username=?", (username,)).fetchone()
    finally:
        db.close()
    if not exists:
        if interactive:
            if display_name is None:
                display_name = (
                    input("Your display name (blank uses username): ").strip() or username
                )
            if access_profile is None and role is None:
                access_profile = (
                    input(
                        "Access profile: client, employee, super_user, admin [employee]: "
                    ).strip()
                    or "employee"
                )
        provision(
            project,
            state,
            username,
            password,
            role=role,
            display_name=display_name,
            access_profile=access_profile or "employee",
        )
    return {
        "configuration": "created" if created else "preserved",
        "company": dataset["status"],
        "account": "preserved" if exists else "created",
        "username": username,
        "next": "Run acme doctor, then acme serve. Existing configuration and exercises "
        "are preserved.",
    }


def port_available(port):
    if not 1024 <= port <= 65535:
        raise ValueError("Choose a local port between 1024 and 65535")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))


def doctor(project, state, data, port=7860, inference=False, full_data=False):
    checks = []

    def record(name, operation, optional=False):
        try:
            detail = operation()
            checks.append({"check": name, "status": "pass", "detail": detail})
        except Exception as exc:
            # Configuration errors may name missing variables; never dump client objects/headers.
            safe = (
                str(exc)
                if isinstance(exc, (ValueError, RuntimeError, FileNotFoundError))
                else type(exc).__name__
            )
            checks.append(
                {
                    "check": name,
                    "status": "optional_unavailable" if optional else "fail",
                    "detail": safe[:500],
                }
            )

    def writable():
        if not state.is_dir():
            raise ValueError("State directory missing. Run acme setup.")
        with tempfile.TemporaryFile(dir=state) as file:
            file.write(b"acme writable probe")
        return "State directory supports temporary writes"

    def database():
        manifest = baseline_manifest(data)
        receipt = json.loads((state / "baseline.json").read_text("utf-8"))
        if receipt.get("content_sha256") != manifest["content_sha256"]:
            raise ValueError(
                "Database baseline version differs. Preserve your work; review acme company reset."
            )
        db = connect(state / "company.sqlite", readonly=True)
        try:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Company database integrity check failed")
        finally:
            db.close()
        return {"dataset_version": manifest["dataset_version"], "profile": manifest["profile"]}

    def account():
        db = connect(state / "app.sqlite", readonly=True)
        try:
            count = db.execute("SELECT COUNT(*) FROM accounts WHERE active=1").fetchone()[0]
        finally:
            db.close()
        if count == 0:
            raise ValueError("No active login account. Run acme setup.")
        return f"{count} active local account(s)"

    def model():
        config = settings(project)
        profile = config["selection"]["main"]
        spec = config["profiles"][profile]
        selected = get_model(project_dir=project)
        name = getattr(selected, "model", getattr(selected, "model_name", "configured deployment"))
        if spec["provider"] == "ollama":
            file_env = dotenv_values(project / ".env", interpolate=False)
            endpoint = os.environ.get(
                spec.get("base_url_env", ""), file_env.get(spec.get("base_url_env", ""))
            )
            endpoint = endpoint or spec.get("base_url", "http://localhost:11434")
            try:
                with httpx.Client(base_url=endpoint, timeout=10) as client:
                    response = client.post("/api/show", json={"model": name})
                if response.status_code == 404:
                    raise ValueError(f"Model not installed. Run: ollama pull {name}")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ValueError(
                    "Ollama is unavailable. Start Ollama and check OLLAMA_BASE_URL."
                ) from exc
            if "tools" not in response.json().get("capabilities", []):
                raise ValueError(
                    "Selected model lacks advertised tool support. Choose a tool-capable model."
                )
        detail = {
            "profile": profile,
            "provider": spec["provider"],
            "model": name,
            "inference": "not requested; availability/configuration checks only",
        }
        if inference:
            probe_tool = {
                "name": "acme_probe",
                "description": "Return the supplied word.",
                "parameters": {
                    "type": "object",
                    "properties": {"word": {"type": "string"}},
                    "required": ["word"],
                },
            }
            reply = selected.bind_tools([probe_tool]).invoke(
                "Call acme_probe with word ready. Do not answer with prose."
            )
            if not any(
                t["name"] == "acme_probe" and t["args"].get("word") == "ready"
                for t in reply.tool_calls
            ):
                raise ValueError(
                    "Model responded without the expected tool call; select a tool-capable model"
                )
            detail["inference"] = "actual tool-call probe passed"
        return detail

    def optional_docker():
        ready, detail = availability()
        if not ready:
            raise ValueError(detail)
        return detail

    def port_probe():
        try:
            port_available(port)
        except OSError as exc:
            raise ValueError(
                f"Port {port} is occupied. Stop the existing server or use --port 7861."
            ) from exc
        return f"127.0.0.1:{port} available"

    record("writable state", writable)
    record("dataset and database version", database)
    record("local login", account)
    record("middleware configuration", lambda: configuration(project))
    record("model/provider", model)
    record("UI port", port_probe)
    record("optional Docker", optional_docker, optional=True)
    if full_data:
        record("full dataset consistency", lambda: verify_dataset(project, data)["status"])
    return {
        "ready": all(c["status"] != "fail" for c in checks),
        "checks": checks,
        "versions": {
            name: version(name) for name in ("langchain", "fastapi", "langgraph-checkpoint-sqlite")
        },
        "python": sys.version.split()[0],
    }


def run_setup_command(args):
    project = args.project_dir.resolve()
    state = (args.state_dir or project / "state").resolve()
    data = (args.data_dir or project / "data").resolve()
    if args.command == "setup":
        print(
            json.dumps(
                setup(
                    project,
                    state,
                    data,
                    args.username,
                    None,
                    args.model,
                    interactive=not args.non_interactive,
                    display_name=args.display_name,
                    access_profile=args.access_profile,
                ),
                indent=2,
            )
        )
    elif args.command == "doctor":
        result = doctor(project, state, data, args.port, args.inference, args.full_data)
        print(json.dumps(result, indent=2))
        if not result["ready"]:
            raise SystemExit(1)
    else:
        if not (state / "app.sqlite").exists() or not (state / "company.sqlite").exists():
            raise ValueError("Run acme setup before starting the website")
        port_available(args.port)
        environment = {**os.environ, "HF_HUB_OFFLINE": "1"}
        print(f"Open http://127.0.0.1:{args.port} — Ctrl+C stops the server.", flush=True)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(project / "serve.py"),
                    "--project-dir",
                    str(project),
                    "--state-dir",
                    str(state),
                    "--data-dir",
                    str(data),
                    "--port",
                    str(args.port),
                ],
                env=environment,
            )
        except KeyboardInterrupt:
            return
        if result.returncode:
            raise SystemExit(result.returncode)
