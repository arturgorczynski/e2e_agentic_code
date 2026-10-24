"""Local profile, ownership, append-only transcript and event stores."""

import hashlib
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from acme.dataset import connect
from acme.tracing import migrate_events, record

APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, employee_id TEXT NOT NULL,
 role TEXT NOT NULL, active INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES accounts(id),
 expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account_profiles(
 user_id TEXT PRIMARY KEY REFERENCES accounts(id), display_name TEXT NOT NULL,
 access_profile TEXT, scopes_json TEXT);
CREATE TABLE IF NOT EXISTS conversations(
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES accounts(id), title TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','archived')));
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES conversations(id),
 submission_id TEXT NOT NULL, user_text TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT,
 UNIQUE(thread_id,submission_id));
CREATE TABLE IF NOT EXISTS transcript(
 seq INTEGER PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES conversations(id),
 message_id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(id),
 message_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(thread_id,message_id));
CREATE TABLE IF NOT EXISTS run_configurations(
 run_id TEXT PRIMARY KEY REFERENCES runs(id), configuration_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations(
 id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES conversations(id), owner_id TEXT NOT NULL,
 run_id TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL, decided_at TEXT, result_json TEXT);
CREATE TABLE IF NOT EXISTS reports(
 id TEXT PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL REFERENCES operations(id),
 thread_id TEXT NOT NULL REFERENCES conversations(id), owner_id TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, sources_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS owned_threads ON conversations(owner_id,updated_at);
CREATE INDEX IF NOT EXISTS thread_transcript ON transcript(thread_id,seq);
CREATE TABLE IF NOT EXISTS conversation_preferences(
 thread_id TEXT PRIMARY KEY REFERENCES conversations(id),
 mode TEXT NOT NULL CHECK(mode IN ('free','company')));
"""
EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
 seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, thread_id TEXT NOT NULL,
 run_id TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS thread_events ON events(thread_id,seq);
"""


class AccessDenied(PermissionError):
    """A session, role or ownership check failed; do not disclose private existence."""


SCOPE_DEFINITIONS = {
    "company_data": {
        "label": "Company data",
        "description": "Customers, products, orders and general documents.",
        "permissions": ["commercial.read", "documents.general"],
    },
    "finance": {
        "label": "Finance",
        "description": "Invoices, payments, credit notes and finance documents.",
        "permissions": ["finance.read", "documents.finance"],
    },
    "operations": {
        "label": "Operations",
        "description": "Stock, purchasing, shipments and operations documents.",
        "permissions": ["operations.read", "documents.operations"],
    },
    "analytics": {
        "label": "Analytics",
        "description": "Forecasts, planning data and analytics documents.",
        "permissions": ["analytics.read", "documents.analytics"],
    },
    "support": {
        "label": "Support",
        "description": "Support cases and documents; may propose ticket updates.",
        "permissions": ["support.read", "support.update", "documents.support"],
    },
    "reports": {
        "label": "Reports",
        "description": "Create report proposals; saving still needs explicit approval.",
        "permissions": ["report.save"],
    },
}

ACCESS_PROFILES = {
    "client": {
        "label": "Client",
        "description": "A narrow external view of general company data.",
        "scopes": ["company_data"],
    },
    "employee": {
        "label": "Employee",
        "description": "Everyday internal data, planning and report proposals.",
        "scopes": ["company_data", "analytics", "reports"],
    },
    "super_user": {
        "label": "Super-user",
        "description": "Full learning-data access and all available company actions.",
        "scopes": ["company_data", "finance", "operations", "analytics", "support", "reports"],
    },
    "admin": {
        "label": "Admin",
        "description": "Full current learning access; reserved for future local administration.",
        "scopes": ["company_data", "finance", "operations", "analytics", "support", "reports"],
    },
}


def now():
    return datetime.now(UTC).isoformat()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def initialize_app(state):
    state.mkdir(parents=True, exist_ok=True)
    for filename, schema in [("app.sqlite", APP_SCHEMA), ("events.sqlite", EVENT_SCHEMA)]:
        db = connect(state / filename)
        try:
            db.executescript(schema)
            if filename == "app.sqlite":
                columns = {row[1] for row in db.execute("PRAGMA table_info(account_profiles)")}
                if "access_profile" not in columns:
                    db.execute("ALTER TABLE account_profiles ADD COLUMN access_profile TEXT")
                if "scopes_json" not in columns:
                    db.execute("ALTER TABLE account_profiles ADD COLUMN scopes_json TEXT")
                account_columns = {row[1] for row in db.execute("PRAGMA table_info(accounts)")}
                for retired_column in ("salt", "password_hash"):
                    if retired_column in account_columns:
                        db.execute(f"ALTER TABLE accounts DROP COLUMN {retired_column}")
                db.commit()
            if filename == "events.sqlite":
                migrate_events(db)
        finally:
            db.close()


@dataclass(frozen=True)
class RunContext:
    """Trusted runtime paths and session; never part of a model-facing tool schema."""

    project: Path
    state: Path
    data: Path
    session_token: str
    thread_id: str
    run_id: str
    execution_id: str = ""


def scope_options():
    """Public labels for the profile picker; permission strings stay server-side."""
    return SCOPE_DEFINITIONS


def profile_options():
    """The four ready-to-use profiles shown during local profile creation."""
    return ACCESS_PROFILES


def _permissions_for(profile, scopes, contract, legacy_role=None):
    if profile == "legacy":
        return contract["roles"].get(legacy_role, [])
    if profile in ACCESS_PROFILES:
        scopes = ACCESS_PROFILES[profile]["scopes"]
    elif profile != "custom":
        raise ValueError("Choose a predefined access profile or Custom scope")
    if not scopes:
        raise ValueError("Choose at least one scope for a Custom scope profile")
    invalid = sorted(set(scopes) - set(SCOPE_DEFINITIONS))
    if invalid:
        raise ValueError("Unknown scope: " + ", ".join(invalid))
    return sorted(
        {permission for scope in scopes for permission in SCOPE_DEFINITIONS[scope]["permissions"]}
    )


def local_accounts(state):
    """Local profile picker; never includes credentials or private conversation data."""
    db = connect(state / "app.sqlite", readonly=True)
    try:
        return [
            dict(row)
            for row in db.execute(
                "SELECT a.username,a.role,COALESCE(p.display_name,a.username) AS display_name,"
                "COALESCE(p.access_profile,'legacy') AS access_profile "
                "FROM accounts a LEFT JOIN account_profiles p ON p.user_id=a.id "
                "WHERE a.active=1 ORDER BY display_name,a.username"
            )
        ]
    finally:
        db.close()


def provision(
    project,
    state,
    username,
    password=None,
    role=None,
    display_name=None,
    access_profile="employee",
    scopes=None,
):
    """Create a password-free local profile; never exposed to agent tools.

    ``password`` and ``role`` remain accepted only for old callers. A legacy role
    becomes an equivalent custom scope; it is never used to authenticate.
    """
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,49}", username):
        raise ValueError("Username: 3–50 lowercase letters, numbers, dots, underscores or hyphens")
    display_name = (display_name or username).strip()
    if not 1 <= len(display_name) <= 80:
        raise ValueError("Display name must contain 1–80 characters")
    contract = json.loads((project / "data/company/company.json").read_text("utf-8"))
    scopes = list(scopes or [])
    # Compatibility for old direct test/lesson callers. The value is not checked or stored.
    if role is None and password is not None:
        design_account = next(
            (item for item in contract["accounts"] if item["username"] == username), None
        )
        role = design_account["role"] if design_account else None
    if role is not None and access_profile == "employee":
        if role not in contract["roles"]:
            raise ValueError("Unknown legacy role: " + role)
        access_profile, scopes = "custom", []
        permissions = contract["roles"][role]
    else:
        permissions = _permissions_for(access_profile, scopes, contract)
    account = {
        "id": "USR-" + uuid4().hex,
        "username": username,
        "employee_id": "LOCAL-" + uuid4().hex[:12],
        "role": access_profile if role is None else role,
    }
    initialize_app(state)
    db = connect(state / "app.sqlite")
    try:
        if db.execute("SELECT 1 FROM accounts WHERE username=?", (username,)).fetchone():
            raise ValueError("That username already exists. Choose it on the sign-in page.")
        db.execute(
            "INSERT INTO accounts(id,username,employee_id,role,active) VALUES(?,?,?,?,1)",
            (account["id"], username, account["employee_id"], account["role"]),
        )
        db.execute(
            "INSERT INTO account_profiles(user_id,display_name,access_profile,scopes_json) "
            "VALUES(?,?,?,?)",
            (account["id"], display_name, access_profile, json_text(sorted(set(permissions)))),
        )
        db.commit()
    finally:
        db.close()
    return {"user_id": account["id"], "username": username}


def login(state, username, password=None):
    """Open a local profile. Local profile selection is deliberately password-free."""
    db = connect(state / "app.sqlite")
    try:
        row = db.execute(
            "SELECT * FROM accounts WHERE username=? AND active=1", (username.strip().lower(),)
        ).fetchone()
        if row is None:
            raise AccessDenied("Unknown local profile")
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        expires = (datetime.now(UTC) + timedelta(hours=8)).isoformat()
        db.execute("INSERT INTO sessions VALUES(?,?,?)", (digest, row["id"], expires))
        db.commit()
        return token
    finally:
        db.close()


def authenticate(project, state, token):
    if not token or len(token) > 200:
        raise AccessDenied("Sign in with acme login")
    db = connect(state / "app.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT a.id,a.username,a.employee_id,a.role,COALESCE(p.display_name,a.username) "
            "AS display_name,p.access_profile,p.scopes_json FROM accounts a "
            "LEFT JOIN account_profiles p ON p.user_id=a.id "
            "JOIN sessions s ON s.user_id=a.id "
            "WHERE s.token_hash=? AND s.expires_at>? AND a.active=1",
            (hashlib.sha256(token.encode()).hexdigest(), now()),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("Session expired or invalid; sign in again")
    actor = dict(row)
    contract = json.loads((project / "data/company/company.json").read_text("utf-8"))
    actor["access_profile"] = actor["access_profile"] or "legacy"
    try:
        saved_permissions = json.loads(actor["scopes_json"]) if actor["scopes_json"] else None
    except json.JSONDecodeError as exc:
        raise AccessDenied("Profile scopes are invalid") from exc
    actor["permissions"] = (
        saved_permissions
        if isinstance(saved_permissions, list)
        else _permissions_for("legacy", [], contract, legacy_role=actor["role"])
    )
    return actor


def owned_thread(project, state, token, thread_id, active=False):
    actor = authenticate(project, state, token)
    db = connect(state / "app.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT c.*,COALESCE(p.mode,'company') AS mode FROM conversations c "
            "LEFT JOIN conversation_preferences p ON p.thread_id=c.id "
            "WHERE c.id=? AND c.owner_id=?",
            (thread_id, actor["id"]),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("Conversation unavailable to this account")
    if active and row["status"] != "active":
        raise ValueError("Conversation is archived")
    return actor, dict(row)


def authorize(context, permission=None):
    actor, _ = owned_thread(
        context.project, context.state, context.session_token, context.thread_id, active=True
    )
    if permission and permission not in actor["permissions"]:
        raise AccessDenied(f"Required permission: {permission}")
    return actor


def new_thread(project, state, token, title, mode="company"):
    if mode not in {"free", "company"}:
        raise ValueError("Choose free chat or company assistant")
    if not 1 <= len(title.strip()) <= 120:
        raise ValueError("Title must contain 1–120 characters")
    actor = authenticate(project, state, token)
    identifier = "thread-" + uuid4().hex
    db = connect(state / "app.sqlite")
    try:
        stamp = now()
        db.execute(
            "INSERT INTO conversations VALUES(?,?,?,?,?,'active')",
            (identifier, actor["id"], title.strip(), stamp, stamp),
        )
        db.execute("INSERT INTO conversation_preferences VALUES(?,?)", (identifier, mode))
        db.commit()
    finally:
        db.close()
    return identifier


def list_threads(project, state, token):
    actor = authenticate(project, state, token)
    db = connect(state / "app.sqlite", readonly=True)
    try:
        return [
            dict(row)
            for row in db.execute(
                (
                    "SELECT c.*,COALESCE(p.mode,'company') AS mode FROM conversations c "
                    "LEFT JOIN conversation_preferences p ON p.thread_id=c.id "
                    "WHERE c.owner_id=? ORDER BY c.updated_at DESC,c.id "
                ),
                (actor["id"],),
            )
        ]
    finally:
        db.close()


def read_transcript(project, state, token, thread_id, after=0):
    owned_thread(project, state, token, thread_id)
    db = connect(state / "app.sqlite", readonly=True)
    try:
        return [
            {**dict(row), "message": json.loads(row["message_json"])}
            for row in db.execute(
                "SELECT seq,message_id,run_id,message_json,created_at FROM transcript "
                "WHERE thread_id=? AND seq>? ORDER BY seq LIMIT 100",
                (thread_id, after),
            )
        ]
    finally:
        db.close()


def event(context, kind, payload, **metadata):
    return record(context, kind, payload, **metadata)


def read_events(project, state, token, thread_id, after=0):
    owned_thread(project, state, token, thread_id)
    db = connect(state / "events.sqlite", readonly=True)
    try:
        return [
            {**dict(row), "payload": json.loads(row["payload_json"])}
            for row in db.execute(
                "SELECT * FROM events WHERE thread_id=? AND seq>? ORDER BY seq LIMIT 100",
                (thread_id, after),
            )
        ]
    finally:
        db.close()


@contextmanager
def execution_lock(state):
    """One active agent/approval per state directory, including across processes.

    SQLite releases this OS-backed transaction lock after a crash; no stale PID lease.
    A competing caller receives a useful busy error rather than queuing duplicate work.
    """
    db = sqlite3.connect(state / "runner.sqlite", timeout=0)
    try:
        try:
            db.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            raise RuntimeError(
                "Runtime busy: another conversation or approval is executing"
            ) from exc
        yield
    finally:
        db.rollback()
        db.close()
