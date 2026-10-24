"""Project-local persisted trace primitives, explicit spans and credential redaction.

This records observable application/LangChain boundaries, never hidden reasoning.
"""

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from difflib import SequenceMatcher
from time import perf_counter
from uuid import uuid4

from dotenv import dotenv_values

from acme.dataset import connect

PARENT = ContextVar("acme_trace_parent", default=None)
SECRET_KEY = re.compile(
    r"api[_-]?key|secret|password|authorization|credential|session_token|^token$", re.I
)
INLINE_SECRET = re.compile(
    r"(?i)(\b(?:api[_-]?key|password|secret|access_token|session_token)\s*[=:]\s*)[^\s,;]+"
    r"|(\bBearer\s+)[A-Za-z0-9._~+/=-]+"
)
TRACE_COLUMNS = {
    "execution_id": "TEXT NOT NULL DEFAULT ''",
    "span_id": "TEXT",
    "parent_id": "TEXT",
    "duration_ms": "REAL",
    "redacted": "INTEGER NOT NULL DEFAULT 0",
    "redaction_paths_json": "TEXT NOT NULL DEFAULT '[]'",
    "trace_version": "INTEGER NOT NULL DEFAULT 1",
}


def migrate_events(db):
    present = {row[1] for row in db.execute("PRAGMA table_info(events)")}
    for name, definition in TRACE_COLUMNS.items():
        if name not in present:
            db.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")
    db.execute("CREATE INDEX IF NOT EXISTS event_runs ON events(thread_id,run_id,seq)")
    db.execute("CREATE INDEX IF NOT EXISTS event_spans ON events(thread_id,span_id)")
    db.commit()


def redact(context, value):
    """Never mutate model inputs; redact the persisted/displayed copy only."""
    config = [
        *dotenv_values(context.project / ".env", interpolate=False).items(),
        *os.environ.items(),
    ]
    secrets = {str(v) for k, v in config if v and SECRET_KEY.search(k)}
    secrets.add(context.session_token or "")
    secrets.discard("")
    paths = []

    def visit(item, path):
        if isinstance(item, dict):
            clean = {}
            for key, child in item.items():
                child_path = f"{path}.{key}"
                if SECRET_KEY.search(str(key)) and child not in (None, ""):
                    clean[str(key)] = "[REDACTED]"
                    paths.append(child_path)
                else:
                    clean[str(key)] = visit(child, child_path)
            return clean
        if isinstance(item, (list, tuple)):
            return [visit(child, f"{path}[{i}]") for i, child in enumerate(item)]
        if isinstance(item, str):
            clean = item
            for secret in sorted(secrets, key=len, reverse=True):
                clean = clean.replace(secret, "[REDACTED]")
            clean = INLINE_SECRET.sub(lambda m: (m[1] or m[2]) + "[REDACTED]", clean)
            if clean != item:
                paths.append(path)
            return clean
        if item is None or isinstance(item, (int, float, bool)):
            return item
        return f"[unsupported {type(item).__name__}]"

    return visit(value, "$"), sorted(set(paths))


def record(
    context,
    kind,
    payload,
    *,
    span_id=None,
    parent_id=None,
    duration_ms=None,
    inherited_redaction=False,
):
    identifier = "event-" + uuid4().hex
    cleaned, paths = redact(context, payload)
    if inherited_redaction:
        paths.append("$ (contains previously redacted source event)")
    db = connect(context.state / "events.sqlite")
    try:
        db.execute(
            "INSERT INTO events(id,thread_id,run_id,kind,created_at,payload_json,execution_id,"
            "span_id,parent_id,duration_ms,redacted,redaction_paths_json,trace_version) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,2)",
            (
                identifier,
                context.thread_id,
                context.run_id,
                kind,
                datetime.now(UTC).isoformat(),
                json.dumps(cleaned, ensure_ascii=False, sort_keys=True),
                context.execution_id or context.run_id,
                span_id,
                parent_id or PARENT.get() or context.execution_id or context.run_id,
                duration_ms,
                bool(paths),
                json.dumps(paths),
            ),
        )
        db.commit()
    finally:
        db.close()
    return identifier


@contextmanager
def span(context, name, payload, *, identifier=None, parent_id=None):
    identifier = identifier or "span-" + uuid4().hex
    parent = parent_id or PARENT.get() or context.execution_id or context.run_id
    record(context, name + "_started", payload, span_id=identifier, parent_id=parent)
    token = PARENT.set(identifier)
    started = perf_counter()
    outcome = {"status": "complete"}
    try:
        yield identifier
    except BaseException as exc:
        outcome = {"status": "error", "error_type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        PARENT.reset(token)
        record(
            context,
            name + "_finished",
            outcome,
            span_id=identifier,
            parent_id=parent,
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )


def difference(before, after):
    """Lossless list edits: unchanged ranges omitted, exact removed/inserted values retained."""
    left = [json.dumps(m, sort_keys=True, ensure_ascii=False) for m in before]
    right = [json.dumps(m, sort_keys=True, ensure_ascii=False) for m in after]
    return [
        {
            "operation": op,
            "before_range": [a, b],
            "after_range": [c, d],
            "removed": before[a:b],
            "inserted": after[c:d],
        }
        for op, a, b, c, d in SequenceMatcher(a=left, b=right, autojunk=False).get_opcodes()
        if op != "equal"
    ]
