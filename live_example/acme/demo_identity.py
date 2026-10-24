"""Demo persona identity shared by the agent runtime and the web portal."""

import hashlib
import json
import sqlite3

from acme.app_store import (
    ACCESS_PROFILES,
    SCOPE_DEFINITIONS,
    AccessDenied,
    authenticate,
    initialize_app,
    login,
    provision,
)
from acme.dataset import connect

DEPARTMENT_SCOPE = {
    "DEP-FINANCE": "finance",
    "DEP-WAREHOUSE": "operations",
    "DEP-PURCHASE": "operations",
    "DEP-LOGISTICS": "operations",
    "DEP-ANALYTICS": "analytics",
    "DEP-SUPPORT": "support",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS portal_personas (
 user_id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject_id TEXT NOT NULL,
 access_profile TEXT NOT NULL);
"""


def initialize(state):
    initialize_app(state)
    db = connect(state / "app.sqlite")
    try:
        db.executescript(SCHEMA)
    finally:
        db.close()


def select(project, state, kind: str, subject_id: str = "") -> tuple[str, dict]:
    if kind not in {"customer", "employee", "super_user"}:
        raise ValueError("Choose customer, employee or super user")
    if kind == "customer":
        company = connect(state / "company.sqlite", readonly=True)
        try:
            subject = company.execute(
                "SELECT name FROM customers WHERE id=?", (subject_id,)
            ).fetchone()
        finally:
            company.close()
        if subject is None:
            raise ValueError("Unknown customer ID")
        title = subject["name"]
        profile = "client"
        scopes = None
    elif kind == "employee":
        company = connect(state / "company.sqlite", readonly=True)
        try:
            subject = company.execute(
                "SELECT e.id,e.name,e.job_title,a.department_id FROM employees e "
                "LEFT JOIN employee_assignments a ON a.employee_id=e.id "
                "AND a.valid_until IS NULL WHERE e.id=?",
                (subject_id,),
            ).fetchone()
        finally:
            company.close()
        if subject is None:
            raise ValueError("Unknown employee ID")
        title = subject["name"]
        profile = "custom"
        scopes = ["company_data", "reports"]
        department_scope = DEPARTMENT_SCOPE.get(subject["department_id"])
        if department_scope:
            scopes.append(department_scope)
    else:
        subject_id = subject_id or "all"
        if subject_id == "all":
            title = "Superuser"
        else:
            company = connect(state / "company.sqlite", readonly=True)
            try:
                focus = company.execute(
                    "SELECT name FROM departments WHERE id=?", (subject_id,)
                ).fetchone()
            finally:
                company.close()
            if focus is None:
                raise ValueError("Unknown superuser department focus")
            title = f"Superuser · {focus['name']}"
        profile = "super_user"
        scopes = None
    digest = hashlib.sha256(f"{kind}:{subject_id}".encode()).hexdigest()[:24]
    username = f"portal.{kind}.{digest}"
    initialize(state)
    db = connect(state / "app.sqlite", readonly=True)
    try:
        account = db.execute("SELECT id FROM accounts WHERE username=?", (username,)).fetchone()
    finally:
        db.close()
    if account is None:
        created = provision(
            project, state, username, display_name=title, access_profile=profile, scopes=scopes
        )
        user_id = created["user_id"]
    else:
        user_id = account["id"]
    db = connect(state / "app.sqlite")
    try:
        effective_scopes = scopes or ACCESS_PROFILES[profile]["scopes"]
        permissions = sorted(
            {
                permission
                for scope in effective_scopes
                for permission in SCOPE_DEFINITIONS[scope]["permissions"]
            }
        )
        db.execute(
            "UPDATE account_profiles SET display_name=?,access_profile=?,scopes_json=? "
            "WHERE user_id=?",
            (title, profile, json.dumps(permissions), user_id),
        )
        db.execute(
            "INSERT INTO portal_personas VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE "
            "SET kind=excluded.kind,subject_id=excluded.subject_id,"
            "access_profile=excluded.access_profile",
            (user_id, kind, subject_id, profile),
        )
        db.commit()
    finally:
        db.close()
    token = login(state, username)
    return token, persona(project, state, token)


def persona(project, state, token: str) -> dict:
    actor = authenticate(project, state, token)
    db = connect(state / "app.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT kind,subject_id,access_profile FROM portal_personas WHERE user_id=?",
            (actor["id"],),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("Choose a demo persona")
    selected = {
        **dict(row),
        "actor_id": actor["id"],
        "display_name": actor["display_name"],
        "permissions": actor["permissions"],
    }
    if selected["kind"] == "employee":
        company = connect(state / "company.sqlite", readonly=True)
        try:
            employee = company.execute(
                "SELECT e.job_title,d.name AS department FROM employees e "
                "LEFT JOIN employee_assignments a ON a.employee_id=e.id AND a.valid_until IS NULL "
                "LEFT JOIN departments d ON d.id=a.department_id WHERE e.id=?",
                (selected["subject_id"],),
            ).fetchone()
            if employee:
                selected.update(dict(employee))
        finally:
            company.close()
    elif selected["kind"] == "super_user":
        selected["focus_department_id"] = (
            selected["subject_id"] if selected["subject_id"] != "all" else None
        )
    return selected


def kind_for_actor(state, user_id: str) -> str | None:
    db = connect(state / "app.sqlite", readonly=True)
    try:
        try:
            row = db.execute(
                "SELECT kind FROM portal_personas WHERE user_id=?", (user_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return row[0] if row else None
    finally:
        db.close()
