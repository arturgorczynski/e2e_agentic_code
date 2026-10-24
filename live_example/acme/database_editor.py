"""Metadata-driven, audited row editing for the local exercise database."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from acme.app_store import now
from acme.dataset import connect
from acme.portal_data import _identifier, objects

DOCUMENT_TABLES = frozenset({"documents", "document_versions", "document_links"})
MAX_VALUE_LENGTH = 10000


class RecordConflict(ValueError):
    """A row changed after the editor loaded it."""


def _metadata(db: sqlite3.Connection, name: str, database: str = "main") -> dict:
    _identifier(name)
    item = db.execute(
        f"SELECT type FROM {database}.sqlite_master WHERE name=? "
        "AND type IN ('table','view') AND name NOT LIKE 'sqlite_%'",
        (name,),
    ).fetchone()
    if item is None:
        raise ValueError("Unknown database table or view")
    columns = [
        {
            "name": row["name"],
            "type": row["type"],
            "required": bool(row["notnull"] or row["pk"]),
            "primary_key": bool(row["pk"]),
            "default": row["dflt_value"],
        }
        for row in db.execute(f"PRAGMA {database}.table_info({_identifier(name)})")
    ]
    foreign_keys = [
        {"column": row["from"], "table": row["table"], "target_column": row["to"] or "id"}
        for row in db.execute(f"PRAGMA {database}.foreign_key_list({_identifier(name)})")
    ]
    editable = item["type"] == "table" and name not in DOCUMENT_TABLES
    reason = (
        "SQL views are calculated and read-only"
        if item["type"] == "view"
        else "Document metadata must stay synchronized with the Markdown corpus"
        if name in DOCUMENT_TABLES
        else None
    )
    return {
        "name": name,
        "type": item["type"],
        "editable": editable,
        "reason": reason,
        "columns": columns,
        "foreign_keys": foreign_keys,
    }


def table_schema(state: Path, name: str) -> dict:
    db = connect(state / "company.sqlite", readonly=True)
    try:
        metadata = _metadata(db, name)
        suggestions = {}
        if metadata["editable"]:
            for column in metadata["columns"]:
                key = column["name"]
                if key not in {"status", "kind", "currency", "segment", "price_kind", "category"}:
                    continue
                if name == "company_expenses" and key == "category":
                    suggestions[key] = [
                        "supplier_payment", "logistics", "packaging", "marketing", "software"
                    ]
                    continue
                values = [
                    row[0]
                    for row in db.execute(
                        f"SELECT DISTINCT {_identifier(key)} FROM {_identifier(name)} "
                        f"WHERE {_identifier(key)} IS NOT NULL ORDER BY 1 LIMIT 21"
                    )
                ]
                if len(values) <= 20:
                    suggestions[key] = values
        metadata["suggestions"] = suggestions
        return metadata
    finally:
        db.close()


def row_dependencies(state: Path, name: str, identifier: str) -> dict:
    """Show direct foreign-key references before a row deletion is attempted."""
    db = connect(state / "company.sqlite", readonly=True)
    try:
        metadata = _metadata(db, name)
        if metadata["type"] != "table":
            raise ValueError("Choose a table row")
        target = db.execute(
            f"SELECT * FROM {_identifier(name)} WHERE id=?", (identifier,)
        ).fetchone()
        if target is None:
            raise ValueError("Record no longer exists")
        dependencies = []
        for item in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ):
            child = item["name"]
            for key in db.execute(f"PRAGMA foreign_key_list({_identifier(child)})"):
                if key["table"] != name:
                    continue
                target_column = key["to"] or "id"
                value = target[target_column]
                column = _identifier(key["from"])
                table = _identifier(child)
                count = db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (value,)
                ).fetchone()[0]
                if not count:
                    continue
                samples = [
                    row[0]
                    for row in db.execute(
                        f"SELECT id FROM {table} WHERE {column}=? ORDER BY id LIMIT 5", (value,)
                    )
                ]
                dependencies.append(
                    {"table": child, "column": key["from"], "count": count, "sample_ids": samples}
                )
        return {
            "table": name,
            "id": identifier,
            "can_delete": not dependencies,
            "dependencies": dependencies,
        }
    finally:
        db.close()


def relationships(state: Path, visible_names: set[str]) -> dict:
    db = connect(state / "company.sqlite", readonly=True)
    try:
        tables = []
        edges = []
        for item in objects(state):
            if item["name"] not in visible_names:
                continue
            metadata = _metadata(db, item["name"])
            tables.append({"name": item["name"], "type": item["type"]})
            for key in metadata["foreign_keys"]:
                if key["table"] in visible_names:
                    edges.append({"source": item["name"], "target": key["table"], **key})
        return {"tables": tables, "edges": edges}
    finally:
        db.close()


def _normalise(values: dict, columns: list[dict], *, creating: bool) -> dict:
    if not isinstance(values, dict) or len(values) > 100:
        raise ValueError("Submit an object with at most 100 columns")
    allowed = {column["name"]: column for column in columns}
    if set(values) - set(allowed):
        raise ValueError("Submitted field is not a column in this table")
    if not creating and "id" in values:
        raise ValueError("Record ID cannot be changed")
    result = {}
    for key, value in values.items():
        column = allowed[key]
        if isinstance(value, bool) or isinstance(value, (list, dict)):
            raise ValueError(f"{key}: enter a plain text or numeric value")
        if value is None or value == "":
            if column["required"] and not (creating and key == "id"):
                raise ValueError(f"{key} is required")
            result[key] = None
            continue
        if len(str(value)) > MAX_VALUE_LENGTH:
            raise ValueError(f"{key} is too long")
        if "INT" in column["type"].upper():
            try:
                result[key] = int(str(value))
            except ValueError as exc:
                raise ValueError(f"{key} must be a whole number") from exc
        else:
            result[key] = str(value)
    if creating:
        if not result.get("id"):
            result["id"] = "EDIT-" + uuid4().hex[:16].upper()
        if "provenance" in allowed and not result.get("provenance"):
            result["provenance"] = "portal_demo_edit"
        for column in columns:
            key = column["name"]
            if column["required"] and key not in result and column["default"] is None:
                raise ValueError(f"{key} is required")
    elif not result:
        raise ValueError("Change at least one field")
    return result


def save_row(
    state: Path,
    name: str,
    values: dict,
    actor: str,
    *,
    identifier: str | None = None,
    expected: dict | None = None,
) -> dict:
    """Insert or update one row and its audit record in a single transaction."""
    if len(json.dumps(values, ensure_ascii=False)) > 64000:
        raise ValueError("Submitted row is too large")
    audit = connect(state / "app.sqlite")
    try:
        audit.execute(
            "CREATE TABLE IF NOT EXISTS portal_edits (id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
            "entity TEXT NOT NULL, record_id TEXT NOT NULL, before_json TEXT NOT NULL, "
            "after_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        audit.execute("ATTACH DATABASE ? AS company", (str((state / "company.sqlite").resolve()),))
        audit.execute("BEGIN IMMEDIATE")
        metadata = _metadata(audit, name, "company")
        if not metadata["editable"]:
            raise ValueError(metadata["reason"] or "This object is read-only")
        columns = metadata["columns"]
        if not any(column["name"] == "id" and column["primary_key"] for column in columns):
            raise ValueError("This table has no editable ID column")
        table = f"company.{_identifier(name)}"
        before = None
        if identifier is None:
            submitted = dict(values)
            if name == "company_expenses":
                submitted.setdefault("currency", "GBP")
                submitted.setdefault("provenance", "fictional_contemporary_expense")
                if submitted.get("purchase_order_id") and not submitted.get("supplier_id"):
                    supplier = audit.execute(
                        "SELECT supplier_id FROM company.purchase_orders WHERE id=?",
                        (submitted["purchase_order_id"],),
                    ).fetchone()
                    if supplier is not None:
                        submitted["supplier_id"] = supplier[0]
            clean = _normalise(submitted, columns, creating=True)
            keys = list(clean)
            audit.execute(
                f"INSERT INTO {table} ({','.join(_identifier(key) for key in keys)}) "
                f"VALUES ({','.join('?' for _ in keys)})",
                tuple(clean[key] for key in keys),
            )
            identifier = str(clean["id"])
        else:
            if not isinstance(expected, dict):
                raise ValueError("The original row is required to prevent overwriting another edit")
            current = audit.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
            if current is None:
                raise RecordConflict("This record no longer exists; refresh the table")
            before = dict(current)
            if before != expected:
                raise RecordConflict(
                    "This record changed since you opened it; refresh and try again"
                )
            clean = _normalise(values, columns, creating=False)
            changed = {key: value for key, value in clean.items() if before[key] != value}
            if not changed:
                raise ValueError("No field changed")
            audit.execute(
                f"UPDATE {table} SET {','.join(_identifier(key) + '=?' for key in changed)} "
                "WHERE id=?",
                (*changed.values(), identifier),
            )
        after = dict(audit.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone())
        edit_id = "edit-" + uuid4().hex
        audit.execute(
            "INSERT INTO portal_edits VALUES(?,?,?,?,?,?,?)",
            (
                edit_id,
                actor,
                name,
                identifier,
                json.dumps(before, ensure_ascii=False),
                json.dumps(after, ensure_ascii=False),
                now(),
            ),
        )
        audit.commit()
        return {"id": edit_id, "record": after, "created": before is None}
    except sqlite3.IntegrityError as exc:
        audit.rollback()
        raise ValueError(f"Database constraint rejected this row: {exc}") from exc
    except Exception:
        audit.rollback()
        raise
    finally:
        audit.close()


def delete_row(state: Path, name: str, identifier: str, expected: dict, actor: str) -> dict:
    """Delete one unreferenced row after checking its current value and auditing it."""
    audit = connect(state / "app.sqlite")
    try:
        audit.execute(
            "CREATE TABLE IF NOT EXISTS portal_edits (id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
            "entity TEXT NOT NULL, record_id TEXT NOT NULL, before_json TEXT NOT NULL, "
            "after_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        audit.execute("ATTACH DATABASE ? AS company", (str((state / "company.sqlite").resolve()),))
        audit.execute("BEGIN IMMEDIATE")
        metadata = _metadata(audit, name, "company")
        if not metadata["editable"]:
            raise ValueError(metadata["reason"] or "This object is read-only")
        table = f"company.{_identifier(name)}"
        row = audit.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
        if row is None or dict(row) != expected:
            raise RecordConflict("This record changed or disappeared; refresh the table")
        audit.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))
        edit_id = "edit-" + uuid4().hex
        audit.execute(
            "INSERT INTO portal_edits VALUES(?,?,?,?,?,?,?)",
            (
                edit_id,
                actor,
                name,
                identifier,
                json.dumps(dict(row), ensure_ascii=False),
                "null",
                now(),
            ),
        )
        audit.commit()
        return {"id": edit_id, "deleted": identifier}
    except sqlite3.IntegrityError as exc:
        audit.rollback()
        raise ValueError(f"Cannot delete a row referenced by other records: {exc}") from exc
    except Exception:
        audit.rollback()
        raise
    finally:
        audit.close()
