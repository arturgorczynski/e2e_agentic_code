"""Complete, searchable read-only view of local conversation histories."""

import json
from pathlib import Path

from acme.app_store import AccessDenied
from acme.dataset import connect


def _available(db, selected: dict, owner_id: str) -> bool:
    return selected["kind"] in {"employee", "super_user"} or owner_id == selected["actor_id"]


def conversations(state: Path, selected: dict) -> list[dict]:
    db = connect(state / "app.sqlite", readonly=True)
    traces = connect(state / "events.sqlite", readonly=True)
    try:
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT c.*,COALESCE(p.display_name,a.username) AS owner_name,"
                "COALESCE(pp.kind,'legacy') AS owner_kind,pp.subject_id,"
                "COALESCE(cp.mode,'company') AS mode,"
                "(SELECT COUNT(*) FROM runs r WHERE r.thread_id=c.id) AS run_count,"
                "(SELECT COUNT(*) FROM transcript t WHERE t.thread_id=c.id) AS message_count,"
                "(SELECT r.user_text FROM runs r WHERE r.thread_id=c.id "
                "ORDER BY r.created_at,r.id LIMIT 1) AS first_prompt,"
                "(SELECT GROUP_CONCAT(r.user_text,' ') FROM runs r "
                "WHERE r.thread_id=c.id) AS search_text "
                "FROM conversations c JOIN accounts a ON a.id=c.owner_id "
                "LEFT JOIN account_profiles p ON p.user_id=a.id "
                "LEFT JOIN portal_personas pp ON pp.user_id=a.id "
                "LEFT JOIN conversation_preferences cp ON cp.thread_id=c.id "
                "ORDER BY c.updated_at DESC,c.id"
            )
            if _available(db, selected, row["owner_id"])
        ]
        by_id = {row["id"]: row for row in rows}
        for row in rows:
            row["tools"] = []
            row["topic"] = row["first_prompt"] or row["title"]
            row.pop("first_prompt")
        for event in traces.execute(
            "SELECT thread_id,payload_json FROM events WHERE kind IN "
            "('tool_attempt_started','native_tool_started','tool_result') ORDER BY seq"
        ):
            item = by_id.get(event["thread_id"])
            if item is None:
                continue
            payload = json.loads(event["payload_json"])
            name = payload.get("name") or payload.get("tool_name") or payload.get("tool")
            if isinstance(name, str) and name not in item["tools"]:
                item["tools"].append(name)
        return rows
    finally:
        traces.close()
        db.close()


def snapshot(state: Path, selected: dict, thread_id: str) -> dict:
    db = connect(state / "app.sqlite", readonly=True)
    try:
        thread = db.execute("SELECT * FROM conversations WHERE id=?", (thread_id,)).fetchone()
        if thread is None or not _available(db, selected, thread["owner_id"]):
            raise AccessDenied("Conversation unavailable")
        messages = []
        for row in db.execute(
            "SELECT message_json FROM transcript WHERE thread_id=? ORDER BY seq", (thread_id,)
        ):
            message = json.loads(row["message_json"])
            kind = message.get("type")
            if kind not in {"human", "ai"}:
                continue
            content = message.get("data", {}).get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            if content:
                messages.append(
                    {"role": "user" if kind == "human" else "assistant", "content": str(content)}
                )
        runs = [
            dict(row)
            for row in db.execute(
                "SELECT id,status,user_text,created_at,updated_at,error FROM runs "
                "WHERE thread_id=? ORDER BY created_at,id",
                (thread_id,),
            )
        ]
        operations = [
            dict(row)
            for row in db.execute(
                "SELECT id,kind,payload_json FROM operations "
                "WHERE thread_id=? AND status='pending' "
                "ORDER BY created_at",
                (thread_id,),
            )
        ]
        return {
            "chat": messages,
            "runs": runs,
            "operations": operations,
            "status": thread["status"],
            "error": None,
            "can_decide": thread["owner_id"] == selected["actor_id"],
        }
    finally:
        db.close()


def events(state: Path, selected: dict, thread_id: str, after: int = 0) -> dict:
    db = connect(state / "app.sqlite", readonly=True)
    try:
        thread = db.execute(
            "SELECT owner_id FROM conversations WHERE id=?", (thread_id,)
        ).fetchone()
        if thread is None or not _available(db, selected, thread["owner_id"]):
            raise AccessDenied("Conversation unavailable")
    finally:
        db.close()
    traces = connect(state / "events.sqlite", readonly=True)
    try:
        rows = [
            dict(row)
            for row in traces.execute(
                "SELECT seq,kind,created_at,payload_json FROM events "
                "WHERE thread_id=? AND seq>? ORDER BY seq LIMIT 101",
                (thread_id, after),
            )
        ]
        visible = rows[:100]
        return {
            "events": [
                {
                    "seq": row["seq"],
                    "kind": row["kind"],
                    "created_at": row["created_at"],
                    "payload": json.loads(row["payload_json"]),
                }
                for row in visible
            ],
            "has_more": len(rows) > 100,
            "next_cursor": visible[-1]["seq"] if visible else None,
        }
    finally:
        traces.close()
